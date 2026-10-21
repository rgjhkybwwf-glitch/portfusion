"""THE RECORD'S ONE LOCK — `schema.LOCK`, shared by every door, the record's reload and the desk's
engine.

The desk serves its routes on a pool of threads, and until 21 Oct 2026 nothing in `desk/` held a
lock: a door's check and its write were two steps another request could fall between, a refusal's
restore put back bytes another write had since moved on from, and the engine could be rebuilt over
a record another request was half-way through re-reading (the review of 21 Oct 2026).
"""
from __future__ import annotations

import threading

import pytest

#: Long enough for an unblocked call to have finished; a blocked one is still waiting after it.
_WAIT = 0.5


def _doors():
    """Every way into the store a request can take, each called so that it is refused (or, for
    the engine, merely built): what is tested is that it WAITS, not what it then does."""
    from portfusion.desk import engine
    from portfusion.desk.doors import commit, freeze, marks, observations, research_notes
    from portfusion.record import rules
    return {
        "commit": lambda: commit.commit("no-such-item"),
        "marks.write": lambda: marks.write(),
        "marks.bank_closes": lambda: marks.bank_closes("2026-01-02", prices=[], rates=[]),
        "observations.write": lambda: observations.write(),
        "freeze.write": lambda: freeze.write("1999-12-31"),
        "freeze.restate": lambda: freeze.restate({}, "nothing"),
        "research_notes.write": lambda: research_notes.write("no-such-note"),
        "atomic": lambda: commit.atomic().__enter__(),
        "reload_store": rules.reload_store,
        "engine.book": lambda: (engine._cache.update(key=None), engine.book()),
    }


@pytest.mark.parametrize("door", sorted(_doors()))
def test_every_door_waits_for_the_lock(door, store_copy):
    """WHILE ANOTHER REQUEST HOLDS THE RECORD, A DOOR WAITS. Each is started on its own thread
    while this one holds `schema.LOCK`; it must still be running when the wait is up, and finish
    once the lock is let go."""
    from portfusion.record import schema
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
    from portfusion.desk.doors import commit
    from portfusion.record import schema
    path = schema.TABLES["journal"].path
    line = "2026-10-21T12:00:00,test,append,journal,0,,the second request's write"

    def second():
        with commit.atomic(path):
            path.write_bytes(path.read_bytes() + line.encode() + b"\n")

    t = threading.Thread(target=second, daemon=True)
    with pytest.raises(RuntimeError):
        with commit.atomic(path):
            t.start()
            t.join(_WAIT)
            raise RuntimeError("the first request is refused")
    t.join(30)
    assert line in path.read_text(encoding="utf-8"), \
        "the first request's refusal erased the second request's write"
