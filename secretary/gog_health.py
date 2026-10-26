"""Read-only health probe for gog OAuth accounts.

`gog auth list` shows every stored account as valid even when Google has
revoked its refresh token. `gog auth doctor --check` exchanges each refresh
token for an access token, which is the only reliable signal. This module
wraps that call so skills (sec-refresh, sec-heartbeat) can warn before a task
fails with `invalid_grant`.

Never triggers an interactive OAuth flow: `--no-input` makes gog fail instead
of prompting.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

REFRESH_PREFIX = "refresh."
DEFAULT_TIMEOUT_S = 90


def _parse_refresh_check(name: str) -> tuple[str, str]:
    """`refresh.<client>.<account>` → (client, account). Account may contain dots."""
    rest = name[len(REFRESH_PREFIX):]
    client, _, account = rest.partition(".")
    return client, account


def parse_doctor(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn `gog auth doctor --check --json` output into a per-account report."""
    accounts: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for check in payload.get("checks") or []:
        name = str(check.get("name", ""))
        status = str(check.get("status", "unknown"))
        if name.startswith(REFRESH_PREFIX):
            client, account = _parse_refresh_check(name)
            ok = status == "ok"
            row = {
                "account": account,
                "client": client,
                "ok": ok,
                "status": status,
                "detail": check.get("detail", ""),
            }
            if not ok:
                row["fix"] = f"gog auth add {account}"
            accounts.append(row)
        elif status != "ok":
            problems.append(
                {
                    "check": name,
                    "status": status,
                    "detail": check.get("detail", ""),
                    "hint": check.get("hint", ""),
                }
            )
    failed = [a for a in accounts if not a["ok"]]
    return {
        "ok": not failed and not problems and bool(accounts),
        "accounts": accounts,
        "failed": [a["account"] for a in failed],
        "problems": problems,
    }


def check_accounts(*, timeout: int = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
    """Probe every stored gog account. Never raises; errors land in the report."""
    gog = shutil.which("gog")
    if gog is None:
        return {"ok": False, "gog_available": False, "accounts": [], "failed": [],
                "problems": [], "error": "gog not installed"}
    cmd = [gog, "auth", "doctor", "--check", "--json", "--no-input"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "gog_available": True, "accounts": [], "failed": [],
                "problems": [], "error": f"gog auth doctor timed out after {timeout}s"}
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        err = (r.stderr or r.stdout or "no output").strip()[:300]
        return {"ok": False, "gog_available": True, "accounts": [], "failed": [],
                "problems": [], "error": f"unparseable gog output (exit {r.returncode}): {err}"}
    report = parse_doctor(payload)
    report["gog_available"] = True
    if not report["accounts"]:
        report["error"] = "no stored accounts"
    return report


def format_markdown(report: dict[str, Any]) -> str:
    """Section for heartbeat `latest.md` / sec-refresh Phase 1 report."""
    lines = ["## gog accounts", ""]
    if report.get("error"):
        lines.append(f"- 🚨 {report['error']}")
    if report.get("accounts"):
        lines += ["| Account | State | Detail / action |", "|---|---|---|"]
        for a in report["accounts"]:
            state = "✅" if a["ok"] else "🚧"
            action = a["detail"] if a["ok"] else f"{a['detail']} → run `{a['fix']}`"
            lines.append(f"| {a['account']} | {state} | {action} |")
    for p in report.get("problems") or []:
        hint = f" ({p['hint']})" if p.get("hint") else ""
        lines.append(f"- ⚠️ `{p['check']}`: {p['detail']}{hint}")
    return "\n".join(lines) + "\n"
