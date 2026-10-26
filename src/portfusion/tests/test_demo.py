"""THE DEMO BOOK NAMES NOBODY HERE, AND ITS GENERATOR WRITES ALL OF IT.

`demo/` is a small invented book, written whole by `tools/make_demo.py`; every name and figure in
it is made up and every source says so. It ships with the code, so nothing of a real book may
appear in its files: `test_what_leaves.py` holds them, with the code, to the book loaded.

THE TESTS HERE RUN ON ANY BOOK, since they read `demo/` whichever is loaded: a fresh run of
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


def test_the_demos_bench_record_is_what_the_bench_gives_its_note_today(inbox):
    """THE BENCH RECORD IN THE CURRENT SHAPE, held rather than asserted. Its filed note is opened
    on a bench under the name it arrived as; what the bench recognises, the class and the three
    limbs must be the record's own, and every key the bench gives an item must be on it. A bench
    that starts writing another shape fails here, and the generator follows."""
    from portfusion.desk.intake import bench, filing
    archived = [json.loads(p.read_text()) for p in sorted((ROOT / DEMO / "_archive" / "bench").glob("*.json"))]
    assert len(archived) == 1, "the demo keeps one bench record"
    item = archived[0]
    shutil.copy(ROOT / DEMO / item["document_archived_to"], inbox / item["document"]["name"])

    fresh = bench.for_document(item["document"]["name"])
    for key in ("evidence_class", "evidence", "recognised", "origin", "title", "document"):
        assert item[key] == fresh[key], f"{key}: the record has {item[key]}, the bench {fresh[key]}"
    assert not set(fresh) - set(item), f"the record lacks {sorted(set(fresh) - set(item))}"
    assert item["document_archived_to"].endswith(filing.archive_name(item, item["document"]["name"]))


def test_the_generator_loads_no_book(tmp_path, repo_root):
    """IT RUNS TO WRITE A BOOK, so it must not need one. The histories import the record, which
    loads a store on import, so a generator importing them could not rebuild the demo after a
    schema change. Loaded here with the book pointed at an empty folder: it imports, and the
    record is never loaded."""
    import subprocess
    import sys
    probe = (f"import importlib.util, sys\n"
             f"spec = importlib.util.spec_from_file_location('make_demo', {str(repo_root / 'tools' / 'make_demo.py')!r})\n"
             f"spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
             f"assert 'portfusion.record.rules' not in sys.modules, 'the record was loaded'\n")
    env = {**__import__("os").environ, "PORTFUSION_BOOK": str(tmp_path)}
    run = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
