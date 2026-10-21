"""THE DEMO BOOK NAMES NOBODY HERE, AND ITS GENERATOR WRITES ALL OF IT.

`demo/` is a small invented book, written whole by `tools/make_demo.py`; every name and figure in
it is made up and every source says so. It ships with the code, so nothing of THIS book — no
holder, account, number, feed label, realisation, ticker, contract or archived document — may
appear anywhere in its files.

THIS FILE ONCE BUILT EVERY PAGE FROM THE DEMO in a child process, because the suite refused to
run with PORTFUSION_BOOK set. Q5 (decided 9 Oct 2026) retired that: the suite itself now runs on any
book — `PORTFUSION_BOOK=demo python3 -m pytest` IS the demo build, every door and page test included —
and only one assertion, the one that needs both books in hand at once, stayed behind. It reads
this book's names from the loaded record and scans the demo's files, so it is this book's own
check, in `checks/test_book_demo.py`: on another book the "real names" would be the demo's own.

What a PAGE could add beyond the files is code-baked text, and that is held separately, on both
books, by test_record.py::test_the_code_names_nobody_in_the_book_it_reads.

THE TWO TESTS HERE RUN ON ANY BOOK, since they read `demo/` whichever is loaded: a fresh run of
the generator writes exactly the files tracked there, and the demo's one bench record is what the
bench gives its filed note today.
"""
import importlib.util
import json
import shutil
import subprocess

import pytest

from harness import NO_CHECKOUT, ROOT
from portfusion.record.schema import DEMO      # inside the app, which ships it

if ROOT is None:                  # the whole module reads the checkout's tools/
    pytest.skip(NO_CHECKOUT, allow_module_level=True)


#: Surfaces worth reading as text. Everything else under demo/ still has its NAME scanned.
_TEXT = {".csv", ".json", ".md", ".txt", ".html"}  # and a PDF, through the bench's own reader


@pytest.fixture(scope="module")
def make_demo():
    """tools/make_demo.py, loaded from its file: a tool beside the app, not a module of it."""
    spec = importlib.util.spec_from_file_location("make_demo", ROOT / "tools" / "make_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_fresh_run_of_the_generator_writes_the_demo_exactly(tmp_path, make_demo):
    """THE GENERATOR IS THE DEMO'S SOURCE, so the demo is what it writes and nothing else. A row
    edited by hand under `demo/`, or a schema change the generator never saw, shows here as a
    file that differs: run `python3 tools/make_demo.py`, read the diff, and commit both."""
    written = make_demo.build(tmp_path)
    tracked = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                              "--", "store", "_archive"],
                             cwd=ROOT / DEMO, capture_output=True, text=True,
                             check=True).stdout.split("\0")
    tracked = sorted(p for p in tracked if p and (ROOT / DEMO / p).is_file())
    assert written == tracked, (
        f"the generator writes {sorted(set(written) - set(tracked))} that demo/ does not hold, "
        f"and demo/ holds {sorted(set(tracked) - set(written))} that it does not write")
    differ = [p for p in written if (tmp_path / p).read_bytes() != (ROOT / DEMO / p).read_bytes()]
    assert not differ, f"a fresh run differs from demo/ in {differ}: run tools/make_demo.py"


def test_the_demos_bench_record_is_what_the_bench_gives_its_note_today(tmp_path, monkeypatch):
    """THE BENCH RECORD IN THE CURRENT SHAPE, held rather than asserted. Its filed note is opened
    on a bench under the name it arrived as; what the bench recognises, the class and the three
    limbs must be the record's own, and every key the bench gives an item must be on it. A bench
    that starts writing another shape fails here, and the generator follows."""
    from portfusion.desk.intake import bench, read_document
    from portfusion.desk.doors import commit
    archived = [json.loads(p.read_text()) for p in sorted((ROOT / DEMO / "_archive" / "bench").glob("*.json"))]
    assert len(archived) == 1, "the demo keeps one bench record"
    item = archived[0]
    inbox = tmp_path / "_inbox"
    (inbox / ".bench").mkdir(parents=True)
    shutil.copy(ROOT / DEMO / item["document_archived_to"], inbox / item["document"]["name"])
    monkeypatch.setattr(read_document, "INBOX", str(inbox))
    monkeypatch.setattr(bench, "BENCH_DIR", inbox / ".bench")
    monkeypatch.setattr(commit, "BOOK", tmp_path)

    fresh = bench.for_document(item["document"]["name"])
    for key in ("evidence_class", "evidence", "recognised", "origin", "title", "document"):
        assert item[key] == fresh[key], f"{key}: the record has {item[key]}, the bench {fresh[key]}"
    assert not set(fresh) - set(item), f"the record lacks {sorted(set(fresh) - set(item))}"
    assert item["document_archived_to"].endswith(commit._archive_name(item, item["document"]["name"]))


def test_the_generator_loads_no_book(tmp_path, repo_root):
    """IT RUNS TO WRITE A BOOK, so it must not need one. It imported the histories, which import
    the record, which loads a store on import — so after a schema change, with no book yet in the
    new shape, the demo could not be rebuilt (the review of 21 Oct 2026). Loaded here with the
    book pointed at an empty folder: it imports, and the record is never loaded."""
    import subprocess
    import sys
    probe = (f"import importlib.util, sys\n"
             f"spec = importlib.util.spec_from_file_location('make_demo', {str(repo_root / 'tools' / 'make_demo.py')!r})\n"
             f"spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
             f"assert 'portfusion.record.rules' not in sys.modules, 'the record was loaded'\n")
    env = {**__import__("os").environ, "PORTFUSION_BOOK": str(tmp_path)}
    run = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
