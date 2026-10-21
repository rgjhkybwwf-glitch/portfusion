"""THE APP'S ONE LOGGER. Every line a command says goes through `log`; no module of the app
prints (`tests/test_code.py` holds it at none).

A COMMAND'S OUTPUT IS ITS INTERFACE — the audit's findings, the sweep the Price Refresh takes its
lines from — so the handler writes the bare message and a command reads exactly as it did when it
printed: info and debug to stdout, warnings and errors to stderr, each line flushed as it is
written. The stream is looked up per line, so a redirected or captured stdout receives it.

    from portfusion.log import log         then log.info(...), log.error(...)
    portfusion -q <action>                 warnings and errors only;  -v  adds the debug lines

One logger rather than one per module: a module run as `python3 -m` is named `__main__`, and a
logger by that name would sit outside the app's and say nothing.
"""
import logging
import sys

log = logging.getLogger("portfusion")


class _Streams(logging.Handler):
    def emit(self, record):
        stream = sys.stderr if record.levelno >= logging.WARNING else sys.stdout
        try:
            stream.write(self.format(record) + "\n")
            stream.flush()
        except Exception:                                   # noqa: BLE001 — logging's own rule
            self.handleError(record)


def setup(level: int = logging.INFO) -> None:
    """Attach the handler once and set how much is said. Run at import, so every command speaks
    from its first line; `portfusion -q` and `-v` call it again with their level."""
    if not any(isinstance(h, _Streams) for h in log.handlers):
        handler = _Streams()
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False


setup()
