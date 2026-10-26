"""secret_scan.py — WHAT A CREDENTIAL LOOKS LIKE, so nothing secret leaves a book's folder.

A book's folder holds the files that reach its brokers and readers (`credentials.json`, the feeds'
sessions, the hosted desk's proxy secret). Two places must never carry what is in them: a commit,
and the hosted desk's published shell. Both ask here, so there is one statement of what counts:
`.githooks/pre-commit` and `commit-msg` refuse a commit by it, and `desk/publish.py` a publish.

It names WHICH credential matched, never the value, because a refusal that quoted the key would
leave it in the terminal's scrollback.

A BYTE SEARCH FINDS a value as it is, in either case, URL-encoded, or in base64 that starts where
the value starts. It cannot find one split across lines or files, in UTF-16, inside anything
compressed (a zip, a PDF's packed streams), in base64 that starts elsewhere, or shorter than
`MIN_LENGTH`; the key shapes are the guard for the formats a value is not read from.

Imports nothing beyond the standard library, so a git hook can load it without the venv.
"""
from __future__ import annotations

import base64
import json
import pathlib
import re
import urllib.parse

#: EVERY FILE A BOOK KEEPS A SECRET IN, by the pattern that keeps it out of git, and the file whose
#: values are scanned, or None where the file is ignored only. A new book's `.gitignore`
#: (`init.GITIGNORE`) is written from it.
SECRET_FILES = {
    "credentials.*": "credentials.json",
    "secrets.*": None,
    "*.key": None,
    ".env": ".env",
    ".ig_session.json": ".ig_session.json",
    ".tv_session.json": ".tv_session.json",
    ".desk_passkeys.json": None,
    ".desk_readers.json": None,
    ".desk_signins.jsonl": None,
    ".desk_proxy_secret.json": ".desk_proxy_secret.json",
    ".desk_*.tmp": None,                    # desk/auth.py's, part-way through being replaced
}
CREDENTIAL_FILES = tuple(f for f in SECRET_FILES.values() if f)

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


def _env(text: str):
    """(key,), value for each `KEY=value` line of a `.env` file, a trailing ` # note` aside."""
    for line in text.splitlines():
        key, eq, value = line.strip().removeprefix("export ").partition("=")
        if eq and not key.startswith("#"):
            yield (key.strip(),), value.split(" #")[0].strip().strip("'\"")


def _forms(value: str):
    """The value, and each form it arrives in changed, by the name a refusal gives it."""
    raw = value.encode()
    yield "", raw
    yield " (upper case)", value.upper().encode()
    yield " (lower case)", value.lower().encode()
    yield " (URL-encoded)", urllib.parse.quote(value, safe="").encode()
    yield " (base64)", base64.b64encode(raw[:len(raw) // 3 * 3])
    yield " (base64)", base64.urlsafe_b64encode(raw[:len(raw) // 3 * 3])


def credential_values(folders) -> tuple[dict[bytes, str], bool, list[str]]:
    """({value: 'file key/path'}, whether any credential file was found, the names of any that
    do not parse) over the credential files in `folders`. The values stay in this mapping;
    only the labels are ever printed."""
    values, found, unreadable = {}, False, []
    for root in folders:
        for name in CREDENTIAL_FILES:
            path = pathlib.Path(root) / name
            if not path.is_file():
                continue
            found = True
            try:
                text = path.read_text(encoding="utf-8")
                leaves = list(_env(text) if name == ".env" else _leaves(json.loads(text)))
            except ValueError:
                unreadable.append(name)
                continue
            for keys, value in leaves:
                if keys and keys[-1] in EXEMPT_KEYS or len(value) < MIN_LENGTH:
                    continue
                for form, encoded in _forms(value):
                    values.setdefault(encoded, f"{name} {'/'.join(keys)}{form}")
    return values, found, unreadable


def matches(where: str, data: bytes, values: dict[bytes, str]):
    """(where, why) for each credential value and each key shape `data` holds."""
    for value, label in values.items():
        if value in data:
            yield where, f"holds {label}"
    for name, shape in KEY_SHAPES.items():
        if re.search(shape, data):
            yield where, f"holds {name}"
