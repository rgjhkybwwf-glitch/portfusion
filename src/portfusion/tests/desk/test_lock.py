"""THE RECORD'S ONE LOCK — `schema.LOCK`, shared by every door, the record's reload, the desk's
engine and the restart's exit.

The desk serves its routes on a pool of threads: without the lock a door's check and its write are
two steps another request can fall between, a refusal's restore puts back bytes another write has
moved on from, and the engine can be rebuilt over a record half-way through re-reading.
"""
from __future__ import annotations

import threading

import pytest

#: Long enough for an unblocked call to have finished; a blocked one is still waiting after it.
_WAIT = 0.1


def _doors():
    """Every way into the store a request can take, each called so that it is refused (or, for
    the engine, merely built): what is tested is that it WAITS, not what it then does."""
    from portfusion.desk import engine, restart
    from portfusion.desk.doors import commit, envelope, freeze, marks, observations, research_notes
    from portfusion.record import rules
    return {
        "commit": lambda: commit.commit("no-such-item"),
        "marks.write": lambda: marks.write(),
        "marks.bank_closes": lambda: marks.bank_closes("2026-01-02", prices=[], rates=[]),
        "marks.refresh": lambda: marks.refresh(),
        "observations.write": lambda: observations.write(),
        "freeze.write": lambda: freeze.write("1999-12-31"),
        "freeze.restate": lambda: freeze.restate({}, "nothing"),
        "research_notes.write": lambda: research_notes.write("no-such-note"),
        "atomic": lambda: envelope.atomic().__enter__(),
        "reload_store": rules.reload_store,
        # THE KEY IS THE STORE'S, so `book()` has nothing to rebuild: what it waits for is its own
        # lock, not the lock of the reload a rebuild would make.
        "engine.book": lambda: (engine._cache.update(key=engine.store_mtime()), engine.book()),
        "engine.report_page": lambda: engine.report_page("1999-12-31"),
        # NOT A DOOR, but the restart's exit must wait as one does, or it ends a write half-done.
        "restart._exit": restart._exit,
    }


@pytest.mark.parametrize("door", sorted(_doors()))
def test_every_door_waits_for_the_lock(door, store_copy, monkeypatch):
    """WHILE ANOTHER REQUEST HOLDS THE RECORD, A DOOR WAITS. Each is started on its own thread
    while this one holds `schema.LOCK`; it must still be running when the wait is up, and finish
    once the lock is let go."""
    import os
    from portfusion.desk import engine
    from portfusion.record import schema
    for key in ("key", "book"):                     # put back after: a case re-keys the cache
        monkeypatch.setitem(engine._cache, key, engine._cache[key])
    monkeypatch.setattr(os, "_exit", lambda code: None)     # the restart's exit ends no suite
    call = _doors()[door]
    done = threading.Event()

    def run():
        try:
            call()
        except BaseException:                       # noqa: BLE001 — refused is the expected end
            pass
        finally:
            done.set()

    with schema.LOCK:
        t = threading.Thread(target=run, daemon=True)
        t.start()
        assert not done.wait(_WAIT), f"{door} ran while another request held the record"
    assert done.wait(30), f"{door} never finished once the lock was let go"
    t.join(5)


def test_a_refusal_does_not_erase_a_write_that_landed_during_it(store_copy):
    """A RESTORE PUTS BACK WHAT WAS READ ON ENTRY. Two envelopes over one file, the second
    written while the first is still open: when the first is refused, its restore must not take
    the second's line with it. With the lock, the second waits for the first and lands after."""
    from portfusion.desk.doors import envelope
    from portfusion.record import schema
    path = schema.TABLES["journal"].path
    line = "2026-10-21T12:00:00,test,append,journal,0,,the second request's write"

    def second():
        with envelope.atomic(path):
            path.write_bytes(path.read_bytes() + line.encode() + b"\n")

    t = threading.Thread(target=second, daemon=True)
    with pytest.raises(RuntimeError):
        with envelope.atomic(path):
            t.start()
            t.join(_WAIT)
            raise RuntimeError("the first request is refused")
    t.join(30)
    assert line in path.read_text(encoding="utf-8"), \
        "the first request's refusal erased the second request's write"


def test_a_panel_reads_the_record_through_the_desks_one_book():
    """A PANEL READS THE RECORD THROUGH `engine.book()`, the Book built under the lock, never
    `record.rules` itself: a read beside it can serve rows the Book was not built from, or the
    tables a reload refused. A reload after a refused write is the door's, not the panel's."""
    import ast
    from harness import SRC
    reads = []
    for f in sorted((SRC / "desk" / "panels").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        alias = {a.asname or a.name for n in imports if n.module == "portfusion.record"
                 for a in n.names if a.name == "rules"}
        alias |= {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                  for a in n.names if a.name == "portfusion.record.rules"}
        reads += [f"{f.name}:{n.lineno} {a.name}" for n in imports
                  if n.module == "portfusion.record.rules" for a in n.names]
        reads += [f"{f.name}:{n.lineno} {n.value.id}.{n.attr}" for n in ast.walk(tree)
                  if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                  and n.value.id in alias]
    assert not reads, f"a panel reads the record beside the desk's Book: {reads}"
