"""tools/pictures.py: which retaken pictures `baselines.yml` may keep. A retake that kept every page
as drawn would accept a page the change moved by accident; this holds it to the pages the pull
request names, and refuses the rest by name."""
import importlib.util

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)


@pytest.fixture(scope="module")
def pictures():
    spec = importlib.util.spec_from_file_location("pictures", ROOT / "tools" / "pictures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png(*pages):
    return [f"tools/desk_walk/{p}-linux.png" for p in pages]


def test_the_line_is_read_however_it_is_written(pictures):
    assert pictures.named("What\n\nPictures: bench, what-changed\n") == {"bench", "what-changed"}
    assert pictures.named("**Pictures:** `Bench`, `Dashboard`.") == {"bench", "dashboard"}
    assert pictures.named("- Pictures: bench") == {"bench"}
    assert pictures.named("Pictures: none") == set()
    assert pictures.named("no line here") is None
    assert pictures.named("") is None


def test_only_the_named_pages_are_kept(pictures, monkeypatch):
    monkeypatch.setenv("PR_BODY", "Pictures: bench, dashboard")
    assert pictures.main(_png("bench")) == 0
    assert pictures.judge({"bench", "dashboard"}, _png("bench")) == (["bench"], [])


def test_a_page_not_named_fails_the_retake_by_name(pictures, monkeypatch, caplog):
    """THE CASE THAT MAKES IT FAIL: a picture that moved and is not named, which a retake of every
    page would have kept."""
    monkeypatch.setenv("PR_BODY", "Pictures: bench")
    assert pictures.judge({"bench"}, _png("bench", "trades", "reports")) == (["bench"], ["reports", "trades"])
    with caplog.at_level("INFO", logger="portfusion"):
        assert pictures.main(_png("bench", "trades")) == 1
    assert "for pages the pull request does not name: trades." in caplog.text
    monkeypatch.setenv("PR_BODY", "Pictures: none")
    assert pictures.main(_png("bench")) == 1


def test_no_line_and_a_name_that_is_no_page_are_refused(pictures, monkeypatch, caplog):
    """A typo would leave its page never retaken; a name not shaped as a page is not repeated
    into the comment the workflow posts."""
    monkeypatch.setenv("PR_BODY", "Closes the issue")
    assert pictures.main(_png("bench")) == 2
    monkeypatch.setenv("PR_BODY", "Pictures: benh")
    with caplog.at_level("INFO", logger="portfusion"):
        assert pictures.main(_png("bench")) == 2
    assert "benh" in caplog.text
    monkeypatch.setenv("PR_BODY", "Pictures: bench, @someone")
    caplog.clear()
    with caplog.at_level("INFO", logger="portfusion"):
        assert pictures.main(_png("bench")) == 2
    assert "@" not in caplog.text
    monkeypatch.setenv("PR_BODY", "Pictures: a-new-page")
    assert pictures.main(_png("a-new-page")) == 0


def _jobs(workflow: str) -> dict[str, str]:
    """Each job of a workflow, by name, as its text: the lines from `  name:` to the next job."""
    jobs, name = {}, None
    for line in workflow.split("\njobs:\n", 1)[1].splitlines():
        if line[:2] == "  " and line[2:3] not in (" ", "") and line.rstrip().endswith(":"):
            name = line.strip()[:-1]
            jobs[name] = ""
        elif name:
            jobs[name] += line + "\n"
    return jobs


def _holds_the_write_token(job: str) -> bool:
    return any(f"{grant}: write" in job for grant in ("contents", "pull-requests"))


def _runs_the_branch(job: str) -> list[str]:
    """What in a job runs code of the branch it checks out: an install, the walk, a tool of `tools/`."""
    return [w for w in ("npm ", "npx ", "node ", "pip ", "python3 ", "bash ", "make ", "./",
                        "tools/pictures.py", "walk --") if w in job]


def test_the_job_that_holds_the_write_token_runs_nothing_of_the_branch():
    """Code of the branch can plant a git hook or set `$GITHUB_ENV` for every later step of its
    job, so the job that can push runs none of it and its git runs with hooks off. THE CASE THAT MAKES
    IT FAIL: the retake as one job, the walk and the push side by side."""
    workflow = (ROOT / ".github" / "workflows" / "baselines.yml").read_text()
    assert "\npermissions: {}\n" in workflow, "a job's grant is its own, never the workflow's"
    jobs = _jobs(workflow)
    writers = {n: j for n, j in jobs.items() if _holds_the_write_token(j)}
    assert {"unlabel", "push", "tidy"} <= writers.keys()
    for name, job in writers.items():
        assert _runs_the_branch(job) == [], name
    assert not _holds_the_write_token(jobs["walk"]) and _runs_the_branch(jobs["walk"])
    assert "git() { command git -c core.hooksPath=/dev/null" in jobs["push"]
    planted = _jobs("\njobs:\n  retake:\n    permissions:\n      contents: write\n"
                    "    steps:\n      - run: npm ci --prefix tools\n")
    assert _runs_the_branch(planted["retake"]) and _holds_the_write_token(planted["retake"])
