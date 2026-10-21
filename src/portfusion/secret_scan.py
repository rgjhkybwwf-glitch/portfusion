"""secret_scan.py — WHAT A CREDENTIAL LOOKS LIKE, so nothing secret leaves a book's folder.

A book's folder holds the files that reach its brokers and readers (`credentials.json`, the feeds'
sessions, the hosted desk's proxy secret). Two places must never carry what is in them: a commit,
and the hosted desk's published shell. Both ask here, so there is one statement of what counts:
`.githooks/pre-commit` refuses a commit by it, and `desk/publish.py` refuses a publish.

It names WHICH credential matched, never the value, because a refusal that quoted the key would
leave it in the terminal's scrollback.

Imports nothing beyond the standard library, so a git hook can load it without the venv.
"""
from __future__ import annotations

import json
import pathlib
import re

CREDENTIAL_FILES = ("credentials.json", ".ig_session.json", ".tv_session.json",
                    ".desk_proxy_secret.json")

# The fields in those files that are NOT secret, and why each one is safe in git.
EXEMPT_KEYS = {
    "account_id": "the broker's account number, which store/accounts.csv already carries",
    "identifier": "the broker login name, which a /Users/ path may also contain",
    "env": "LIVE or DEMO",
    "saved": "when the session was cached",
    "scope": "the name of an OAuth scope",
    "token_type": "the word Bearer",
    "expires_in": "a lifetime in seconds",
}

# Shorter than this and a value is too likely to occur by chance to be worth refusing on.
MIN_LENGTH = 8

KEY_SHAPES = {
    "an Anthropic API key": rb"sk-ant-[\w-]{20,}",
    "a GitHub token": rb"\bgh[pousr]_\w{30,}",
    "a GitHub fine-grained token": rb"github_pat_\w{20,}",
    "a private key": rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}


def _leaves(node, keys=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, keys + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, keys + (str(i),))
    elif isinstance(node, str):
        yield keys, node


def credential_values(folders) -> tuple[dict[bytes, str], bool, list[str]]:
    """({value: 'file key/path'}, whether any credential file was found, the names of any that
    are not valid JSON) over the credential files in `folders`. The values stay in this mapping;
    only the labels are ever printed."""
    values, found, unreadable = {}, False, []
    for root in folders:
        for name in CREDENTIAL_FILES:
            path = pathlib.Path(root) / name
            if not path.is_file():
                continue
            found = True
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                unreadable.append(name)
                continue
            for keys, value in _leaves(data):
                if keys and keys[-1] in EXEMPT_KEYS or len(value) < MIN_LENGTH:
                    continue
                values.setdefault(value.encode(), f"{name} {'/'.join(keys)}")
    return values, found, unreadable


def matches(where: str, data: bytes, values: dict[bytes, str]):
    """(where, why) for each credential value and each key shape `data` holds."""
    for value, label in values.items():
        if value in data:
            yield where, f"holds {label}"
    for name, shape in KEY_SHAPES.items():
        if re.search(shape, data):
            yield where, f"holds {name}"
