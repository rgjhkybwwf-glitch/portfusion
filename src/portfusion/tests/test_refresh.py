"""
THE PRICE SWEEP — `feeds/refresh.py`.

Two properties matter. The IG levels and the IG equity are read back to back, because the book
reconciles one against the other. And each vendor's failure stays its own. Nothing here reaches a
network: the feeds are replaced by functions that log what was asked of them.
"""
import subprocess
import sys

import pytest

from portfusion.feeds import refresh as R


def _run(args, repo_root):
    return subprocess.run([sys.executable, "-m", "portfusion.feeds.refresh", *args],
                          cwd=repo_root, capture_output=True, text=True)


def test_help_does_not_start_a_refresh(repo_root):
    """--help prints the usage and fetches nothing."""
    r = _run(["--help"], repo_root)
    assert r.returncode == 0
    assert "THE PRICE SWEEP" in r.stdout
    assert "STEP 1 of" not in r.stdout, "--help started the sweep"


@pytest.mark.parametrize("args", [["--achive"], ["--on", "30-09-2026"], ["--on"]])
def test_an_unknown_flag_or_a_bad_date_stops_rather_than_sweeping(repo_root, args):
    r = _run(args, repo_root)
    assert r.returncode == 2
    assert "unrecognised" in r.stdout
    assert "STEP 1 of" not in r.stdout


def test_check_changes_nothing(repo_root):
    """--check reports and returns; it must not archive as a side effect."""
    from portfusion.history import prices as PH
    before = len(PH.load())
    r = _run(["--check"], repo_root)
    assert r.returncode == 0
    assert len(PH.load()) == before


def _logged(monkeypatch, fail_archive=False):
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    log = []

    def archive(what):
        def run(*a, **k):
            if fail_archive:
                raise OSError("disk full")
            log.append(what)
            return []
        return run
    monkeypatch.setattr(PH, "archive", archive("prices banked"))
    monkeypatch.setattr(FX, "archive", archive("rates banked"))
    monkeypatch.setattr(R, "sweep", lambda on=None, filed=None: log.append("swept") or {})
    monkeypatch.setattr(R, "_print", lambda r: None)
    return log


def test_the_marks_are_banked_before_the_sweep(monkeypatch):
    log = _logged(monkeypatch)
    assert R.main([]) == 0
    assert log == ["prices banked", "rates banked", "swept"]


def test_no_sweep_starts_if_the_bank_fails(monkeypatch, capsys):
    log = _logged(monkeypatch, fail_archive=True)
    assert R.main([]) == 2
    assert log == [] and "ARCHIVE FAILED" in capsys.readouterr().out


# =================================================================================================
# THE SWEEP, with each vendor replaced
# =================================================================================================
_ACCOUNT = {"kind": "row", "account": "Rowe IG Spread bet", "account_id": "QZ7XD", "env": "live",
            "funds": 20000.0, "running_pl": -237.6, "equity": 19762.4, "deposit": 3000.0,
            "available": 16805.9, "source": "IG REST live /accounts"}


class _Conn:
    """A TradingView connection that answers every call the sweep makes."""


def _vendors(monkeypatch, log, tv_signed_in=True, levels_fail=False):
    from portfusion.feeds import ig, tv

    def levels():
        log.append("levels")
        if levels_fail:
            raise ig.IGError(503, "error.service.unavailable", "IG is down")
        return {"rows": [{"contract": "ZEPH-DEC26", "priced": True, "level": 75.5}]}

    def equity():
        log.append("equity")
        return {"rows": [_ACCOUNT], "refusals": []}

    def connect():
        log.append("tv")
        if not tv_signed_in:
            raise tv.TVError("not signed in to TradingView")
        return _Conn()

    monkeypatch.setattr(ig, "contract_levels", levels)
    monkeypatch.setattr(ig, "account_state", equity)
    monkeypatch.setattr(ig, "contract_closes", lambda on: log.append(f"ig closes {on}") or {
        "rows": [{"contract": "ZEPH-MAR27", "priced": False, "status": "not quoted"}]})
    monkeypatch.setattr(tv, "connect", connect)
    monkeypatch.setattr(tv, "sweep", lambda conn: log.append("quotes") or {
        "prices": [], "rates": [], "failed": []})
    monkeypatch.setattr(tv, "closes", lambda on, conn: log.append(f"tv closes {on}") or {
        "prices": [], "rates": [], "failed": []})


def test_the_equity_is_read_straight_after_the_levels(monkeypatch):
    """ONE OBSERVATION: nothing is fetched between the levels and the equity, and each account
    comes back as a reading the observations door can take."""
    log = []
    _vendors(monkeypatch, log)
    r = R.sweep()
    assert log == ["levels", "equity", "tv", "quotes"]
    assert r["ig_equity"]["gap_seconds"] is not None
    reading = r["ig_equity"]["readings"][0]
    assert (reading["account"], reading["equity"], reading["funds"], reading["evidence"]) == (
        "Rowe IG Spread bet", 19762.4, 20000.0, "ig-accounts")
    assert reading["reference"].startswith("QZ7XD, read ")


def test_one_vendors_failure_is_not_the_others(monkeypatch):
    """IG down still reads the equity and all of TradingView; TradingView signed out costs IG
    nothing. Each failure is named where it happened."""
    log = []
    _vendors(monkeypatch, log, levels_fail=True)
    r = R.sweep()
    assert not r["ig_levels"]["ok"] and "IG is down" in r["ig_levels"]["error"]
    assert r["ig_equity"]["ok"] and r["tv"]["ok"]

    log = []
    _vendors(monkeypatch, log, tv_signed_in=False)
    r = R.sweep()
    assert r["ig_levels"]["ok"] and r["ig_equity"]["ok"]
    assert "not signed in" in r["tv"]["error"]


def test_a_sweep_with_no_sign_in_anywhere_names_each_vendor_and_raises_nothing(
        tmp_path, monkeypatch):
    """THE REAL FEEDS, NOT STUBS, with no IG credentials and no TradingView session: each
    fails before a request is built, and the sweep must hand that back part by part. Any request
    that did get built fails this test rather than leaving the machine."""
    import urllib.request
    from portfusion.feeds import ig, tv
    def no_network(*a, **k):
        raise AssertionError("a request was built — the feed reached for the network")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(ig._schema, "BOOK", tmp_path)
    monkeypatch.setattr(tv, "SESSION_FILE", str(tmp_path / "none.tv.json"))
    r = R.sweep()
    for part in ("ig_levels", "ig_equity", "tv"):
        assert r[part]["ok"] is False, part
    assert "CredentialsError" in r["ig_levels"]["error"]
    assert "not signed in to TradingView" in r["tv"]["error"]


def test_a_past_day_is_closes_only(monkeypatch):
    """No equity and no list for a past day — a reading is an instant — and without a statement
    reader the far contract stays unpriced, saying why."""
    log = []
    _vendors(monkeypatch, log)
    r = R.sweep("2026-09-30")
    assert log == ["ig closes 2026-09-30", "tv", "tv closes 2026-09-30"]
    assert set(r) == {"on", "ig_levels", "tv"}
    assert r["ig_levels"]["rows"][0]["status"] == "not quoted"


def test_the_sweep_prints_its_rates(capsys):
    """A RATE ROW HAS NO `key`, only its currency (both producers drop it): `_print` prints it by
    the currency, and raises no KeyError."""
    R._print({"on": None, "ig_levels": {"ok": True, "rows": []},
              "tv": {"ok": True, "prices": [], "failed": [], "rates": [
                  {"currency": "USD", "rate": 1.3611, "struck": "close", "source": "test"}]}})
    assert "USD" in capsys.readouterr().out
