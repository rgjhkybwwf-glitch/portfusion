"""WHAT LEAVES NAMES NOTHING OF THE BOOK IT IS DEVELOPED BESIDE: none of its people, accounts,
holdings, references, figures or brand, in any file of the checkout, the commits not yet on main,
or the branch's name. The names are read from the loaded book. On the demo or a practice book
the names are the examples, so there is nothing to check; CI runs there, and the pre-push hook
runs this on the book `PORTFUSION_BOOK` names (CONTRIBUTING.md)."""
import datetime as dt
import re
import subprocess

import pytest

#: The trade and sale id shape. Ids run in sequence, so the demo's and a test's coincide with a
#: book's and say nothing; outside the tests and the demo, any id is the book's.
_ID_SHAPE = r"(?<![A-Za-z0-9-])[TE]-\d{3}[A-Z0-9]*(?![A-Za-z0-9])"
#: The files read as text; a PDF is read for its text, any other file is not the code's.
_TEXT = {".py", ".js", ".css", ".html", ".json", ".ini", ".txt", ".md", ".toml", ".yml", ".csv",
         ".svg", ""}


def _rows(schema, table):
    names = [f.name for f in schema.TABLES[table].fields]
    return [dict(zip(names, r)) for r in schema.load(table)]


def _figures(schema):
    """Each figure of five or more significant digits that is not a round hundred, as the store
    writes it and as a page prints it."""
    forms = set()
    for table in schema.TABLES:
        for row in schema.load(table):
            for v in row:
                if isinstance(v, float) and v % 100 and "e" not in repr(v):
                    whole, frac = repr(abs(v)).split(".")
                    forms |= {f"{whole}.{frac}", f"{int(whole):,}.{frac}",
                              f"{abs(v):.2f}", f"{abs(v):,.2f}"}
    return {f for f in forms if len(f.replace(",", "").replace(".", "").strip("0")) >= 5}


def _instants(schema):
    """The minute each filed document was pulled, in the shapes a document or a fixture writes it."""
    forms = set()
    for name in schema.filed_statements():
        if m := re.match(r"(\d{2} \w{3} \d{4}) (\d{2})\.(\d{2}) ", name):
            t = dt.datetime.strptime(f"{m[1]} {m[2]}:{m[3]}", "%d %b %Y %H:%M")
            forms |= {f"{t.day} {t:%b %Y %H:%M}", f"{t:%d %b %Y %H:%M}", f"{t:%d-%m-%Y %H:%M}",
                      f"{t:%Y-%m-%d %H:%M}", f"{t:%Y-%m-%dT%H:%M}", f"{t:%d %b %Y %H.%M}"}
    return forms


def _brand(schema):
    """The book's own name and wordmark as code spells them, and its repository's name; none
    when the book wears the app's."""
    from portfusion import brand
    if brand.DIR is None:
        return set()
    forms = set()
    for words in {brand.NAME, brand.WORDMARK[0]}:
        parts = words.split()
        forms |= {sep.join(parts) for sep in (" ", "-", "_", "")}
    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                            text=True, cwd=schema.BOOK).stdout.strip()
    if remote:
        forms.add(remote.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1])
    return {f for f in forms if len(f) >= 5}


def _either(alternatives):
    return "|".join(sorted(map(re.escape, alternatives), key=len, reverse=True)) if alternatives \
        else r"(?!x)x"


@pytest.fixture
def named(D, book_names):
    """One pattern for everything of the loaded book, and one for the id shape."""
    schema = D.schema
    if schema.BOOK == schema.DEMO or dict(schema.load("settings")).get("practice"):
        pytest.skip("the loaded book is the demo's, whose names are the examples")
    if not book_names["words"]:
        pytest.skip("the loaded book names nobody yet")
    exact = (book_names["exact"] | set(D.ACCOUNT_ORDER) | set(schema.filed_statements())
             | {r["code"] for r in _rows(schema, "securities")}
             | {r["company"] for r in _rows(schema, "issuers")}
             | {v for r in _rows(schema, "contracts") for v in (r["contract"], r["epic"]) if v}
             | {r[k] for t, k in (("trades", "broker_ref"), ("exits", "broker_ref"),
                                  ("cash-observations", "reference"),
                                  ("account-observations", "reference"))
                for r in _rows(schema, t) if r[k] and len(r[k]) >= 5 and " " not in r[k]})
    return re.compile(
        r"(?i:(?<![A-Za-z])(" + _either(book_names["words"]) + r")(?![A-Za-z]))"
        r"|(?i:" + _either(book_names["joined"] | _brand(schema)) + ")"
        r"|(?<![A-Za-z0-9-])(" + _either({str(e) for e in exact if e}) + r")(?![A-Za-z0-9])"
        r"|(" + _either(book_names["numbers"]) + ")"
        r"|(" + _either(_instants(schema)) + r")(?!\d)"
        r"|(?<![\d.,])(" + _either(_figures(schema)) + r")(?!\d)")


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def test_what_leaves_names_nothing_of_the_loaded_book(named, repo_root, project_files):
    from portfusion.desk.intake import read_document
    shape = re.compile(_ID_SHAPE)
    found = []
    for p in project_files(*_TEXT, ".pdf"):
        rel = p.relative_to(repo_root).as_posix()
        text = (read_document.extract_file(p)["text"] if p.suffix == ".pdf"
                else p.read_text(encoding="utf-8", errors="replace"))
        ids_allowed = "/tests/" in rel or "/demo/" in rel or rel == "tools/make_demo.py"
        found += [f"{rel}:{i}: {m.group(0)!r}" for i, line in enumerate(text.splitlines(), 1)
                  for m in [named.search(line) or (None if ids_allowed else shape.search(line))]
                  if m]
    ahead = _git(repo_root, "log", "--format=%B", "origin/main..HEAD")
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    found += [f"{where}: {m.group(0)!r}" for where, text in
              (("a commit not yet on main", ahead), ("the branch's name", branch))
              for m in named.finditer(text)]
    assert not found, ("what leaves names the loaded book — use the demo's names or invent "
                       "one:\n  " + "\n  ".join(found[:50]))
