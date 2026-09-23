from subprocess import CompletedProcess

from typer.testing import CliRunner

from secretary.main import app


runner = CliRunner()


def test_gwork_forwards_unknown_options(monkeypatch):
    calls = []
    monkeypatch.setattr("secretary.main.shutil.which", lambda name: "/tmp/gwork")

    def fake_run(command, check):
        calls.append((command, check))
        return CompletedProcess(command, 0)

    monkeypatch.setattr("secretary.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["gwork", "sync", "--root", "/tmp/project"])

    assert result.exit_code == 0
    assert calls == [(["/tmp/gwork", "sync", "--root", "/tmp/project"], False)]


def test_gwork_forwards_help(monkeypatch):
    monkeypatch.setattr("secretary.main.shutil.which", lambda name: "/tmp/gwork")
    monkeypatch.setattr(
        "secretary.main.subprocess.run",
        lambda command, check: CompletedProcess(command, 0),
    )

    result = runner.invoke(app, ["gwork", "--help"])

    assert result.exit_code == 0


def test_gwork_reports_missing_executable(monkeypatch):
    monkeypatch.setattr("secretary.main.shutil.which", lambda name: None)

    result = runner.invoke(app, ["gwork", "sync"])

    assert result.exit_code == 127
    assert "gwork is not installed" in result.output
