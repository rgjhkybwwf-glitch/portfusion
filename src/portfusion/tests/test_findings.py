"""
WHAT THE RECORD NEEDS TODAY — `Book.findings()` and the judgement owed beside each position.

The findings are the engine's, read from the record, and `portfusion record` and the desk's
Dashboard both show them. Nothing
here hardcodes a figure from the book: each rule is fired at a state built for the test, because
a book that holds no problem today cannot show that the check would find one.
"""
import datetime as dt

import pandas as pd
import pytest

from portfusion.engine import Book
from portfusion.record import rules as D
from harness import needs, write_rows


@pytest.fixture(scope="module")
def book():
    return Book()


# ---- the judgement ---------------------------------------------------------------------------

def test_each_half_of_the_judgement_is_owed_from_its_own_date(book):
    """The thesis is owed from the ENTRY date and the exit reason from the EXIT date, so a holding
    bought years ago and sold after the cut-off owes why it was sold and not why it was bought.
    Nothing in the record is in scope today, so the rows are built here."""
    before = pd.Timestamp(D.REVIEW_FROM - dt.timedelta(days=30))
    after = pd.Timestamp(D.REVIEW_FROM + dt.timedelta(days=1))
    frame = pd.DataFrame([("A", before, after), ("B", after, after), ("C", before, before)],
                         columns=["ticker", "opened", "closed"])
    out = book.with_reasoning(frame, opened="opened", closed="closed")
    got = out[["why_entered_owed", "why_exited_owed"]].values.tolist()
    assert got == [[False, True], [True, True], [False, False]], got


def test_a_written_judgement_is_not_owed(book, monkeypatch):
    after = pd.Timestamp(D.REVIEW_FROM + dt.timedelta(days=1))
    monkeypatch.setitem(book.D.REASONING, "ZZZ",
                        [D.Reasoning("ZZZ", after.date(), "a thesis", "  ")])
    out = book.with_reasoning(pd.DataFrame([("ZZZ", after, after)],
                                           columns=["ticker", "opened", "closed"]),
                              opened="opened", closed="closed")
    assert not out.loc[0, "why_entered_owed"]
    assert out.loc[0, "why_exited_owed"], "whitespace is not a written reason"


def test_a_why_belongs_to_the_life_it_was_written_in(book, monkeypatch):
    """A name bought again after a full exit starts a new life, and the old life's whys stay
    with the round trip they explain. Without the window, the new position would show a thesis
    and an exit reason from a holding that no longer exists."""
    old, new = dt.date(2025, 3, 1), dt.date(2026, 3, 1)
    monkeypatch.setitem(book.D.REASONING, "ZZZ", [
        D.Reasoning("ZZZ", old, "the first thesis", None),
        D.Reasoning("ZZZ", old + dt.timedelta(days=30), None, "the first exit"),
        D.Reasoning("ZZZ", new, "the second thesis", None)])
    held = book.with_reasoning(pd.DataFrame([("ZZZ", pd.Timestamp(new))],
                                            columns=["ticker", "opened"]))
    assert [w["text"] for w in held.loc[0, "whys"]] == ["the second thesis"]
    trip = book.with_reasoning(pd.DataFrame([("ZZZ", pd.Timestamp(old),
                                              pd.Timestamp(old + dt.timedelta(days=30)))],
                                            columns=["ticker", "opened", "closed"]),
                               opened="opened", closed="closed")
    assert [(w["half"], w["text"]) for w in trip.loc[0, "whys"]] == [
        ("why_entered", "the first thesis"), ("why_exited", "the first exit")]


def test_a_research_note_is_never_owed(book):
    """Research notes cover a subset of the book, so none is an empty list and never a flag."""
    out = book.with_reasoning(book.holdings(by="ticker"))
    assert not [c for c in out.columns if c.startswith("research") and c.endswith("_owed")]
    assert all(isinstance(n, list) for n in out["research_notes"])


def test_the_reasoning_is_the_records(book):
    """The text beside a position is store/reasoning.csv's, by ticker — the engine joins, and a
    renderer reads the joined frame rather than the record. Every why dated since the position
    opened is there, in date order, and none from before it."""
    out = book.with_reasoning(book.holdings(by="ticker"))
    for r in out.to_dict("records"):
        opened = pd.Timestamp(r["opened"])
        on_file = [(x.date.isoformat(), half, text) for x in D.REASONING.get(r["ticker"], [])
                   if pd.isna(opened) or pd.Timestamp(x.date) >= opened
                   for half, text in (("why_entered", x.why_entered), ("why_exited", x.why_exited))
                   if text and text.strip()]
        assert [(w["date"], w["half"], w["text"]) for w in r["whys"]] == on_file, r["ticker"]


@needs("buys", "current-prices")
def test_theses_owed_names_each_missing_half(book, monkeypatch):
    """Moving the cut-off back puts every position in scope, and every blank half then owes."""
    monkeypatch.setattr(book.D, "REVIEW_FROM", dt.date(2000, 1, 1))
    owed = book.theses_owed()
    assert owed and all(o["half"] in ("why we entered", "why we exited") for o in owed)
    blank_open = [t for t in book.holdings(by="ticker")["ticker"]
                  if not any(r.why_entered for r in D.REASONING.get(t, []))]
    assert {o["ticker"] for o in owed if o["account"] is None} == set(blank_open)


# ---- the findings ----------------------------------------------------------------------------

def test_findings_are_data_and_hardcode_no_figure(book):
    f = book.findings()
    assert set(f) == {"problems", "gaps", "notes", "prices"}
    assert any(n.endswith("account(s) reconcile to statement") for n in f["notes"])
    assert any(n.startswith("journal:") for n in f["notes"])
    assert any(n.startswith("evidence:") for n in f["notes"])


@needs("buys", "current-prices")
def test_prices_past_the_age_limit_are_a_problem(book):
    """Fired at a day far enough past the oldest mark that the book's own prices are too old."""
    oldest = pd.Timestamp(book.price_ageing()["oldest"])
    late = (oldest + pd.Timedelta(days=D.PRICE_AGE_LIMIT + 1)).date().isoformat()
    assert any("past the" in p and "-day limit" in p for p in book.findings(today=late)["problems"])
    fresh = oldest.date().isoformat()
    assert not any("days old" in p for p in book.findings(today=fresh)["problems"])


@needs("buys", "current-prices")
def test_the_dashboard_and_the_audit_read_one_price_age(book):
    """THE AGE IS WHAT TURNS INTO A PROBLEM, so the Dashboard's Prices line leads with it. It and
    `portfusion record` both read `price_ageing()`'s, the figure the age limit judges."""
    from portfusion.desk import panels
    age = book.price_ageing()["age_days"]
    assert panels.get("dashboard").data()["prices"]["age_days"] == age
    assert book.findings()["prices"][1].startswith(f"{age} days ")
    oldest = pd.Timestamp(book.price_ageing()["oldest"])
    later = (oldest + pd.Timedelta(days=5)).date().isoformat()
    assert book.price_ageing(later)["age_days"] == 5
    assert book.findings(today=later)["prices"][1].startswith("5 days ")


@needs("buys", "current-prices")
def test_a_reconciliation_past_its_band_is_a_problem(book, monkeypatch):
    rec = book.reconciliation()
    ig = rec[rec["comparable"] == True].index[0]                       # noqa: E712
    rec.loc[ig, "difference"] = rec.loc[ig, "statement"]                # 100% apart
    monkeypatch.setattr(book, "reconciliation", lambda: rec)
    assert any(p.startswith("reconciliation failed") for p in book.findings()["problems"])


@needs("buys", "current-prices")
def test_a_difference_that_rounds_to_nothing_carries_no_sign(book, monkeypatch):
    """Less than a penny reads "agree to £0.00": its sign does not outlive the rounding."""
    rec = book.reconciliation()
    ig = rec[rec["comparable"] == True].index[0]                       # noqa: E712
    agree = f"{rec.loc[ig, 'account']}: book and broker agree to "
    monkeypatch.setattr(book, "reconciliation", lambda: rec)
    for residue in (-1e-12, 0.0, 1e-12):
        rec.loc[ig, "difference"] = residue
        line = next(n for n in book.findings()["notes"] if n.startswith(agree))
        assert line.startswith(agree + "£0.00 ("), line


@needs("buys", "current-prices")
def test_an_account_with_no_statement_is_a_gap_not_a_problem(book, monkeypatch):
    rec = book.reconciliation()
    rec.loc[0, "statement"] = float("nan")
    monkeypatch.setattr(book, "reconciliation", lambda: rec)
    f = book.findings()
    assert any(g.startswith("NO STATEMENT") and rec.loc[0, "account"] in g for g in f["gaps"])
    assert not any(rec.loc[0, "account"] in p for p in f["problems"])


def test_the_evidence_line_survives_an_absent_archive(book, monkeypatch, tmp_path):
    """The findings promise never to fail over a provenance read; with no archive they say so.
    A check that cannot run is a problem, never good order: the audit's status counts them."""
    monkeypatch.setattr(D.schema, "BOOK", tmp_path)
    note, problem = book._evidence_chain()
    assert "unverifiable" in note and problem is None

    def broken():
        raise OSError("unreadable")
    for owner, name, check in ((D.schema, "filed_statements", "evidence chain"),
                               (book, "journal_unaccounted", "journal"),
                               (book, "conversions", "conversions")):
        with monkeypatch.context() as m:
            m.setattr(owner, name, broken)
            m.setattr(book, "journal_opened", lambda: "2026-01-01")
            assert any(f"{check} could not be checked" in p
                       for p in book.findings()["problems"]), check


@needs("buys", "current-prices")
def test_owed_reasoning_is_a_gap(book, monkeypatch):
    monkeypatch.setattr(book.D, "REVIEW_FROM", dt.date(2000, 1, 1))
    assert any(g.startswith("reasoning owed") for g in book.findings()["gaps"])


# ---- portfusion record -----------------------------------------------------------------------

def test_the_record_command_prints_every_finding(capsys):
    """The command computes nothing: each line it prints is the engine's or about.py's."""
    from portfusion.record.__main__ import findings
    problems = findings()
    out = capsys.readouterr().out
    f = Book().findings()
    assert problems == len(f["problems"])
    for line in f["notes"] + f["gaps"] + f["problems"] + f["prices"]:
        assert line in out, line
    assert "backup:" in out and "python:" in out


def test_the_close_procedure_names_the_freeze_and_its_window(monkeypatch):
    """Printed when a quarter has ended unfrozen, and every date in it is derived from that
    quarter end, never typed."""
    from portfusion.record.__main__ import close_reminder
    monkeypatch.setattr(Book, "quarter_to_close", staticmethod(lambda: pd.Timestamp("2026-09-24")))
    text = close_reminder(dt.date(2026, 9, 25))
    by = dt.date(2026, 9, 24) + dt.timedelta(days=D.CLOSE_CHECK_WINDOW_DAYS)
    assert "portfusion freeze 2026-09-24 --write" in text
    assert '"closes of"' in text and f"{by:%-d %b %Y}" in text
    assert "portfusion report --check 2026-09-24" in text
    assert close_reminder(dt.date(2026, 9, 23)) is None, "a quarter not yet ended is not owed"


# ---- the price limits ------------------------------------------------------------------------

def test_the_two_price_limits_are_the_agreed_values(repo_root):
    """Tuned to a weekly-or-wider refresh cadence. Changing either is a decision, not a tweak —
    this is the reminder."""
    from portfusion.record import rules as B
    assert B.PRICE_AGE_LIMIT == 21, "the absolute stale limit moved without a decision"
    assert B.PRICE_SPREAD_LIMIT == 4, "the spread limit moved without a decision"


def test_price_freshness_flags_a_stale_and_a_straggling_set(book, monkeypatch):
    """The bounds, fired at sets the record does not contain. A book refreshed inside the
    window passes; one left too long fails on AGE; one where a single ticker was missed
    fails on SPREAD even though its newest mark is fresh — which is the whole reason the
    second limit exists.

    JUDGED BY THE FINDINGS THEMSELVES. The test holds no copy of the rule."""
    import datetime as dt
    from portfusion.record import rules as B
    today = dt.date.today()
    fed = book.store["prices"][~book.store["prices"]["mark_key"].isin(set(B.STATEMENT_PRICED))]
    if len(fed) < 2:
        pytest.skip("the book holds fewer than two market-fed marks")
    real = book.store["prices"]

    def verdict(days_old):
        marks = fed.head(len(days_old)).copy()
        marks["as_of"] = [(today - dt.timedelta(days=d)).isoformat() for d in days_old]
        monkeypatch.setitem(book.store, "prices", marks)
        said = book.findings(today=today.isoformat())["problems"]
        monkeypatch.setitem(book.store, "prices", real)
        return (any("days old" in p for p in said), any("spread limit" in p for p in said))

    assert verdict([0, 3]) == (False, False), "a normal Friday/Monday sweep must pass"
    assert verdict([14, 14]) == (False, False), "a fortnight-old set must NOT nag"
    assert verdict([25, 25]) == (True, False), "a set left 25 days must fail on age"
    assert verdict([0, 30]) == (True, True), "a ticker missed 30 days ago fails both"
    assert verdict([0, 9]) == (False, True), (
        "THE SPREAD CASE: newest mark is today, one ticker is nine "
        "days behind. Age passes, spread must not")


# ---- the brokers' statements ----------------------------------------------------------------

def test_the_findings_judge_every_judgeable_account_and_name_the_rest(book):
    """The book against each broker's own statement, the one check against a source no code in
    this repo can influence. The findings and the engine agree about how many accounts are
    judged — whatever the record does next — and an account that cannot be judged is NAMED,
    never passed over."""
    import re
    f = book.findings()
    line = next(n for n in f["notes"] if n.endswith("account(s) reconcile to statement"))
    rec = book.reconciliation()
    judged = sum(1 for _, r in rec.iterrows()
                 if book.reconciliation_verdict(r["statement"], r["difference"], r["evidence"],
                                                r["comparable"], r["comparability"])["checkable"])
    assert int(re.match(r"(\d+)", line).group(1)) == judged
    if judged < len(rec):
        assert "GAPS, so not judged:" in f["notes"] or any(
            g.startswith("NO STATEMENT") for g in f["gaps"]), "fewer judged and none named"


def test_each_action_of_the_command_answers_help_and_runs_nothing():
    """`portfusion --help` and each action's `--help` answer and exit 0, and the audit's does not
    start the audit: a stranger's first question of a command must not run it. EVERY COMMAND IS
    IN `portfusion --help`: each action, and each module the package runs as `python3 -m`, but
    the hooks, which git runs."""
    import subprocess
    import sys
    from harness import SRC
    from portfusion import __main__ as cli
    said = {}
    for args in ([], ["desk"], ["record"], ["report"], ["freeze"]):
        r = subprocess.run([sys.executable, "-m", "portfusion", *args, "--help"],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (args, r.stderr)
        assert "portfusion" in r.stdout and "the record is in good order" not in r.stdout, args
        said[tuple(args)] = r.stdout
    assert all(f"portfusion {a} " in said[()] for a in cli.ACTIONS), said[()]
    runs = {f.relative_to(SRC).with_suffix("").as_posix() for f in SRC.rglob("*.py")
            if f.relative_to(SRC).parts[0] not in ("tests", "hooks") and f != SRC / "__main__.py"
            and '__name__ == "__main__"' in f.read_text(encoding="utf-8")}
    listed = said[()].replace(".", "/")
    missing = sorted(m for m in runs if m not in listed)
    assert not missing, f"not in portfusion --help: {missing}"


def test_book_names_the_folder_for_every_action(monkeypatch, repo_root):
    """`--book <folder>` sits anywhere on the line, in either form, and is taken out before the
    action sees its arguments. It sets PORTFUSION_BOOK from where the command was typed, and a folder
    holding no store/ is refused before anything runs."""
    import os
    import subprocess
    import sys
    import portfusion
    from portfusion import __main__ as cli
    assert portfusion.book(["desk", "--book", "demo", "--port", "8769"]) == (["desk", "--port", "8769"], "demo")
    assert portfusion.book(["--book=demo", "record"]) == (["record"], "demo")
    assert portfusion.book(["report"]) == (["report"], None)
    # AND EVERY `python3 -m` COMMAND, typed where no book is: the package takes it first.
    unset = {k: v for k, v in os.environ.items() if k != "PORTFUSION_BOOK"}
    for folder, code in (("demo", 0), ("nowhere", 2)):
        r = subprocess.run([sys.executable, "-m", "portfusion.history.accounts", "--book", folder,
                            "--check"], cwd=repo_root / "docs", env=unset, capture_output=True,
                           text=True, timeout=60)
        assert r.returncode == code, (folder, r.stderr)
    monkeypatch.setenv("PORTFUSION_BOOK", "unchanged")
    monkeypatch.chdir(repo_root)
    assert cli.main(["record", "--book", "nowhere"]) == 2
    assert os.environ["PORTFUSION_BOOK"] == "unchanged", "a refused book was set anyway"
    assert cli.main(["--help", "--book", "demo"]) == 0
    assert os.environ["PORTFUSION_BOOK"] == "demo", "the word names the demo the app ships"


def test_the_book_is_named_from_where_the_command_was_typed(repo_root):
    """A relative PORTFUSION_BOOK is a path from the folder the command runs in, and is written
    back absolute, so a process started elsewhere reads the same book. The word `demo`, from any
    folder, is the demo book the app ships. UNSET, it is the book in the folder the command runs
    in, and a folder holding no book is REFUSED rather than read as the demo, so a forgotten
    setting cannot show invented figures as a book's own."""
    import os
    import subprocess
    import sys
    show = "import os; from portfusion.record import schema; print(schema.BOOK); print(os.environ['PORTFUSION_BOOK'])"
    env = {k: v for k, v in os.environ.items() if k != "PORTFUSION_BOOK"}
    from portfusion.record import schema
    for named, cwd in (("../src/portfusion/demo", repo_root / "tools"), ("demo", repo_root / "tools")):
        r = subprocess.run([sys.executable, "-c", show], cwd=cwd,
                           env={**env, "PORTFUSION_BOOK": named}, capture_output=True, text=True, timeout=60)
        assert r.stdout.split() == [str(schema.DEMO)] * 2, (named, r.stderr)
    r = subprocess.run([sys.executable, "-c", show], cwd=schema.DEMO, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.stdout.split() == [str(schema.DEMO)] * 2, ("unset, in a book's folder", r.stderr)
    r = subprocess.run([sys.executable, "-c", show], cwd=repo_root / "tools", env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "no book here" in r.stderr, (r.stdout, r.stderr)
    # THE SUITE SAYS SO IN ONE LINE, and names the demo, rather than a page of INTERNALERROR.
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--co", "-p", "no:cacheprovider"],
                       cwd=repo_root, env=env, capture_output=True, text=True, timeout=60)
    said = r.stdout + r.stderr
    assert r.returncode != 0 and "no book here" in said and "PORTFUSION_BOOK=demo" in said \
        and "INTERNALERROR" not in said, said


def test_a_foreign_income_row_with_no_rate_on_file_is_a_problem(store_copy):
    """A ROW WITH NO RATE IS THE ONE THE CONVERSIONS CHECK EXISTS FOR, reported by name beside a
    row with a rate or with none."""
    from portfusion.history import fx as FX
    from portfusion.record import schema
    rates = FX.load()
    if not rates:
        pytest.skip("the book holds no rate history")
    cur, rated = rates[-1]["currency"], rates[-1]["date"]
    account = next(a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND.get(a) != "spread bet")
    path = schema.TABLES["income"].path
    head = path.read_text(encoding="utf-8")

    def with_rows(*days):
        path.write_text(head, encoding="utf-8")
        header = schema.TABLES["income"].header
        write_rows("income", *(dict(zip(header, f"{d},{account},Dividend,test dividend,7.50,test,,"
                                                 f"{cur},10.00,,".split(","))) for d in days))
        D.reload_store()
        return Book().findings()["problems"]

    for days in (("1999-01-04",), ("1999-01-04", rated)):
        said = [p for p in with_rows(*days) if "1999-01-04" in p and "no close on file" in p]
        assert said, f"{days}: the row with no rate was not reported"
