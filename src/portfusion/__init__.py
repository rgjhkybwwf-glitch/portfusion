"""PortFusion — the app, and no book. What it holds is README.md's folder map; the
folder of facts it reads is whichever `PORTFUSION_BOOK` names (`record/schema.py:BOOK`).
"""

#: THE RELEASE, PEP 440, in its one home: `pyproject.toml` reads it, `portfusion --version` prints
#: it, and the desk's footer and the report's stamp carry it (`about.release()`). Raised by
#: decision, never by every merge. Between releases it is the next one's `.devN`, and the commit
#: says which code it is; a release is tagged `v<version>` when this says it.
__version__ = "0.2.0"
#: What a release in this series is called beside its number. A label, not part of the number.
LABEL = "beta"
