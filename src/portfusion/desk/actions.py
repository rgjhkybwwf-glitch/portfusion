"""THE ACTION REGISTRY — the one place that says what this thing can do.

Every button on the desk is declared here. That is the point: "what can the desk write?" has
exactly one answer and it is readable in one file, rather than being the sum of whatever the
panels happen to call.

THE MARKS RULE IS ENCODED HERE AS STRUCTURE, NOT PROSE:

    a feed may write a MARK on the owner's tick.  A feed may NEVER write an EVENT.

`writes` is three-valued — None / "marks" / "events" — and deliberately NOT a boolean. A
boolean would make "does this write?" answerable and "what may it write?" unanswerable, and the
whole decision lives in the second question.

`tests/desk/test_boundaries.py` asserts no registered action declares `writes="events"`
(`test_no_registered_action_writes_an_event`) and pins the set of writing actions the way
`_EXPECTED_FLAGS` pins the flag count (`test_every_writing_action_is_pinned`). A new writing
button therefore FAILS THE SUITE until someone declares it on purpose.

`reaches` IS A SECOND AXIS: whether the action leaves this machine. Reading a document with the
model writes nothing to the store and does send it to a third party. The set of reaching actions
is pinned the same way (`test_every_reaching_action_is_pinned`).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Callable, Optional

# The only values `writes` may take. "marks" is a price, an FX rate, live account equity —
# things replaced by design at every refresh, whose outgoing value is archived BEFORE the new
# one lands, and which are therefore reversible in one command. "events" is a trade, an exit, a
# dividend, a capital movement: each happened once, on a date, and is history.
WRITE_KINDS = (None, "marks", "events")

# WHAT AN ACTION REACHES, and it is a SECOND AXIS rather than a fourth value on `writes`.
#
# Asking IG for an account's events sends a request to the broker. `writes` is None for it,
# which is TRUE and useless: it says the sweep changes nothing in the store, and says nothing
# about a request having left the building.
#
# Putting "network" into WRITE_KINDS is the obvious move and is wrong. `writes` answers "WHAT
# MAY IT WRITE" — three values, one question. A fourth value from a different question makes
# the first one unanswerable again, which is exactly the collapse the three-valued field was
# built to prevent (`test_reaches_is_not_a_fourth_value_on_writes`).
#
# So: two fields, two questions. An action may write nothing and still reach a third party;
# it may write marks and reach nothing.
REACH_KINDS = (None, "network")

# NO BLANKET DATE GATE, and the mechanism is kept.
#
# `None` means NO BLANKET GATE — not "no gate". A single action may still name its own
# `enabled_from`, and the real guard was never a date: it is
# `test_every_writing_action_is_pinned`, which fails the suite the moment a new writing button
# appears and keeps failing until someone declares it on purpose. That is a guard on WHAT
# WRITES rather than on WHEN — a rule naming a property survives, a rule naming a moment
# expires.
WRITES_ENABLED_FROM: Optional[_dt.date] = None


@dataclass(frozen=True)
class Action:
    name: str                                   # stable id, used by the API
    label: str                                  # what the button says
    panel: str                                  # the page it belongs to; "desk" for the shell's own
    run: Callable                               # what it does
    summary: str = ""                           # one line, shown as help
    writes: Optional[str] = None                # None | "marks" | "events"
    reaches: Optional[str] = None               # None | "network" — leaves this machine
    gate: str = ""                              # what the human must do first
    enabled_from: Optional[_dt.date] = None     # None = available now
    # INVOKED FROM A ROW, NOT FROM THE PANEL'S LIST. An action that only means anything against
    # ONE row — an event from a sweep — must not stand as a panel button with nothing to work.
    # The panel filters on this rather than on the action's name, so the next row-scoped action
    # does not have to be special-cased in the UI.
    inline: bool = False

    def __post_init__(self):
        if self.writes not in WRITE_KINDS:
            raise ValueError(
                f"action {self.name!r}: writes={self.writes!r} is not one of {WRITE_KINDS}. "
                f"It is three-valued on purpose.")
        if self.writes == "events":
            raise ValueError(
                f"action {self.name!r} declares writes='events'. A feed may never write an "
                f"event: a trade, exit, dividend or capital movement happened once and is "
                f"history. Events go to the bench for evidence, reasoning and approval.")
        if self.reaches not in REACH_KINDS:
            raise ValueError(
                f"action {self.name!r}: reaches={self.reaches!r} is not one of {REACH_KINDS}.")
        if self.reaches and not self.gate:
            raise ValueError(
                f"action {self.name!r} reaches {self.reaches!r} with no gate. Something leaving "
                f"this machine needs a stated human step for the same reason a write does — "
                f"more so, because it cannot be undone by restoring a file.")
        if self.writes and not self.gate:
            raise ValueError(
                f"action {self.name!r} writes {self.writes!r} with no gate. A write with no "
                f"stated human step is exactly what the marks rule did not settle.")

    @property
    def available(self) -> bool:
        """False while a writing action is still behind a date it names.

        With the blanket gate lifted this answers for per-action `enabled_from` only. Kept
        because the mechanism costs nothing and a future action may want to defer itself.
        """
        due = self.enabled_from or (WRITES_ENABLED_FROM if self.writes else None)
        return True if due is None else _dt.date.today() >= due

    def as_json(self) -> dict:
        due = self.enabled_from or (WRITES_ENABLED_FROM if self.writes else None)
        return {"name": self.name, "label": self.label, "panel": self.panel,
                "summary": self.summary, "writes": self.writes,
                "reaches": self.reaches, "gate": self.gate,
                "available": self.available, "inline": self.inline,
                "enabled_from": due.isoformat() if due else None}


_REGISTRY: dict[str, Action] = {}


def register(action: Action) -> Action:
    existing = _REGISTRY.get(action.name)
    if existing is not None and existing.panel != action.panel:
        raise ValueError(f"two actions named {action.name!r}, in panels {existing.panel!r} and "
                         f"{action.panel!r} — names are the API's handle on a button and must "
                         f"be unique")
    _REGISTRY[action.name] = action
    return action


def _load_panels():
    """Import every panel, so their actions are registered before the registry is read.

    An action registers when the panel declaring it is imported, which means asking "what can
    the desk do?" before any panel has loaded gave the honest-but-useless answer "nothing" —
    and the whole claim about this file is that it is the ONE place with the answer. A registry
    that has to be primed by the caller is not that.

    Imported inside the function because panels import THIS module; at module level it would be
    a cycle.
    """
    from portfusion.desk import panels, restart   # noqa: F401 — the shell's own action registers on import
    panels.all_panels()


def all_actions() -> list[Action]:
    _load_panels()
    return sorted(_REGISTRY.values(), key=lambda a: (a.panel, a.name))


def get(name: str) -> Action:
    _load_panels()
    if name not in _REGISTRY:
        raise KeyError(name)
    return _REGISTRY[name]


def reaching_actions() -> list[Action]:
    """Every action that leaves this machine. The mirror of writing_actions(), and pinned by
    its own test so a second one cannot appear without somebody deciding it should."""
    return [a for a in all_actions() if a.reaches]


def writing_actions() -> list[Action]:
    """Every action that can change the record. The list a test pins."""
    return [a for a in all_actions() if a.writes]
