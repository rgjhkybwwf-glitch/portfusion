"""THE DESK'S LAUNCHAGENT — `portfusion desk --install-agent`, written into a folder of the test's
own, with launchctl stood in for: no test loads, stops or reads this Mac's agents."""
import plistlib
import sys

import pytest

from portfusion.desk import agent


@pytest.fixture
def agents(tmp_path, monkeypatch):
    """A LaunchAgents folder and a log of the test's own, and a launchctl that only records."""
    monkeypatch.setattr(agent, "AGENTS", tmp_path / "LaunchAgents")
    monkeypatch.setattr(agent, "LOG", tmp_path / "Logs" / "portfusion-desk.log")
    monkeypatch.setattr(sys, "platform", "darwin")
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    def launchctl(*args):
        calls.append(args)
        done = Done()
        done.returncode = 1 if args[0] == "print" else 0     # nothing is loaded
        return done
    monkeypatch.setattr(agent, "_launchctl", launchctl)
    return calls


def _written():
    return plistlib.loads(agent.plist_path().read_bytes())


def test_the_agent_runs_the_book_it_was_installed_for_on_the_python_that_installed_it(agents, tmp_path):
    """Everything the agent needs is in its plist, so no shell profile is read at login: the
    book's venv, the book absolute and its folder to run in, and the log."""
    book = tmp_path / "book"
    agent.install(book, None, python="/a/book/.venv/bin/python3")
    p = _written()
    assert p["Label"] == agent.LABEL and agent.plist_path().name == f"{agent.LABEL}.plist"
    assert p["ProgramArguments"] == ["/a/book/.venv/bin/python3", "-m", "portfusion.desk", "--no-open"]
    assert p["EnvironmentVariables"] == {"PORTFUSION_BOOK": str(book)}
    assert p["WorkingDirectory"] == str(book) and p["RunAtLoad"] is True
    assert p["StandardOutPath"] == p["StandardErrorPath"] == str(agent.LOG)
    assert ("bootstrap", agents[-1][1], str(agent.plist_path())) == agents[-1]


def test_a_book_with_a_hosted_desk_gets_its_remote_door(agents, tmp_path):
    agent.install(tmp_path / "book", agent.REMOTE_PORT)
    assert _written()["ProgramArguments"][-2:] == ["--remote-port", str(agent.REMOTE_PORT)]


def test_installing_again_for_the_same_book_restarts_it(agents, tmp_path):
    """The way to bring the agent onto newly installed code: it is booted out before it is
    loaded again, never bootstrapped over itself."""
    agent.install(tmp_path / "book", None)
    agents.clear()
    agent.install(tmp_path / "book", None)
    verbs = [c[0] for c in agents]
    assert verbs.index("bootout") < verbs.index("bootstrap")


def test_an_agent_for_another_book_is_refused_and_left_as_it_was(agents, tmp_path):
    agent.install(tmp_path / "one", None)
    was = agent.plist_path().read_bytes()
    with pytest.raises(agent.Refused, match="another book"):
        agent.install(tmp_path / "two", None)
    assert agent.plist_path().read_bytes() == was


def test_another_agent_that_runs_the_desk_is_named_and_never_removed(agents, tmp_path):
    """One desk per Mac user: an agent of another label would hold the port. It is not this
    module's to delete, so the refusal names it and the command that would."""
    agent.AGENTS.mkdir(parents=True)
    old = agent.AGENTS / "an.older.desk.plist"
    old.write_bytes(plistlib.dumps({"Label": "an.older.desk",
                                    "ProgramArguments": ["python3", "-m", "portfusion.desk"]}))
    (agent.AGENTS / "unrelated.plist").write_bytes(plistlib.dumps({"Label": "x",
                                                                   "ProgramArguments": ["x"]}))
    with pytest.raises(agent.Refused, match="an.older.desk") as e:
        agent.install(tmp_path / "book", None)
    assert "unrelated" not in str(e.value) and old.exists()
    assert not agent.plist_path().exists()


def test_uninstalling_removes_the_plist_it_wrote_and_nothing_else(agents, tmp_path):
    agent.install(tmp_path / "book", None)
    (agent.AGENTS / "unrelated.plist").write_bytes(b"")
    agent.uninstall()
    assert not agent.plist_path().exists() and (agent.AGENTS / "unrelated.plist").exists()
    assert "no desk agent" in agent.uninstall()


def test_off_macos_nothing_is_written(agents, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(agent.Refused, match="macOS"):
        agent.install(tmp_path / "book", None)
    assert not agent.AGENTS.exists() and agents == []
