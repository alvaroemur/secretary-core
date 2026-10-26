import json
from subprocess import CompletedProcess

from typer.testing import CliRunner

from secretary.gog_health import check_accounts, format_markdown, parse_doctor
from secretary.main import app


runner = CliRunner()


def _doctor(*refresh):
    checks = [{"name": "keyring.open", "status": "ok", "detail": "opened"}]
    for account, status, detail in refresh:
        checks.append({"name": f"refresh.default.{account}", "status": status, "detail": detail})
    return {"checks": checks, "status": "ok"}


def _patch_gog(monkeypatch, payload, returncode=0):
    monkeypatch.setattr("secretary.gog_health.shutil.which", lambda name: "/tmp/gog")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = payload if isinstance(payload, str) else json.dumps(payload)
        return CompletedProcess(cmd, returncode, stdout=out, stderr="")

    monkeypatch.setattr("secretary.gog_health.subprocess.run", fake_run)
    return calls


def test_parse_all_ok():
    report = parse_doctor(_doctor(("acct-a", "ok", "refresh token exchange succeeded")))
    assert report["ok"] is True
    assert report["accounts"][0]["account"] == "acct-a"
    assert report["failed"] == []


def test_parse_revoked_account_suggests_reauth():
    report = parse_doctor(
        _doctor(
            ("acct-a", "ok", "refresh token exchange succeeded"),
            ("acct-b", "error", "invalid_grant: Token has been expired or revoked."),
        )
    )
    assert report["ok"] is False
    assert report["failed"] == ["acct-b"]
    bad = report["accounts"][1]
    assert bad["fix"] == "gog auth add acct-b"
    assert "gog auth add acct-b" in format_markdown(report)


def test_parse_non_refresh_problem_fails():
    payload = _doctor(("acct-a", "ok", "ok"))
    payload["checks"].append({"name": "keyring.password", "status": "warn", "detail": "unset"})
    report = parse_doctor(payload)
    assert report["ok"] is False
    assert report["problems"][0]["check"] == "keyring.password"


def test_check_is_non_interactive(monkeypatch):
    calls = _patch_gog(monkeypatch, _doctor(("acct-a", "ok", "ok")))
    check_accounts()
    assert calls == [["/tmp/gog", "auth", "doctor", "--check", "--json", "--no-input"]]


def test_check_without_gog(monkeypatch):
    monkeypatch.setattr("secretary.gog_health.shutil.which", lambda name: None)
    report = check_accounts()
    assert report["ok"] is False
    assert report["gog_available"] is False


def test_check_unparseable_output(monkeypatch):
    _patch_gog(monkeypatch, "boom", returncode=1)
    report = check_accounts()
    assert report["ok"] is False
    assert "unparseable" in report["error"]


def test_cli_exit_codes(monkeypatch):
    _patch_gog(monkeypatch, _doctor(("acct-a", "ok", "ok")))
    assert runner.invoke(app, ["gog-health", "--format", "json"]).exit_code == 0

    _patch_gog(monkeypatch, _doctor(("acct-a", "error", "invalid_grant")))
    result = runner.invoke(app, ["gog-health", "--format", "markdown"])
    assert result.exit_code == 1
    assert "gog auth add acct-a" in result.output
