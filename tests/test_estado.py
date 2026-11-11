"""Tests for `secretary estado` using synthetic fixtures only."""
import json
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from typer.testing import CliRunner

from secretary import estado
from secretary.main import app

SECRET = "SENTINEL-SECRET-DO-NOT-LEAK"
PLAN = """---
id: demo-plan
goal: "Demo goal"
status: active
---

## Nodes

| id | mode | status | note | session | harness | branch | pr |
|----|------|--------|------|---------|---------|--------|----|
| n1 | autonomous | running | first node | local_abc123 | claude-code | | #7 |
| n2 | autonomous | pending | by branch | | | feat/second | |
"""
OLD_PLAN = """---
id: old-plan
status: active
---

## Nodes

| id | mode | status | note |
|----|------|--------|------|
| a1 | in_session | pending | legacy columns only |
"""


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "tester",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "tester"})


class EstadoFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name).resolve()
        self.t = t
        self.repo = t / "dev" / "demo-repo"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "docs" / "plans").mkdir(parents=True)
        (self.repo / "docs/plans/demo.md").write_text(PLAN)
        (self.repo / "docs/plans/old.md").write_text(OLD_PLAN)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        self.wt = self.repo / ".wt" / "feat-second"
        git(self.repo, "worktree", "add", "-q", "-b", "feat/second", str(self.wt))

        self.src = estado.Sources(
            claude_desktop=t / "desktop", claude_projects=t / "projects",
            codex_sessions=t / "codex", cursor_projects=t / "cursor", cache_dir=t / "cache",
        )
        # Claude desktop: one valid session, with secret keys that must never surface.
        d = self.src.claude_desktop / "acct" / "ws"
        d.mkdir(parents=True)
        (d / "local_abc123.json").write_text(json.dumps({
            "sessionId": "local_abc123", "cliSessionId": "cli-uuid-1", "title": "Desktop title",
            "cwd": str(self.repo), "originCwd": str(self.repo),
            "createdAt": 1_700_000_000_000, "lastActivityAt": int(time.time() * 1000),
            "isArchived": False, "model": "m", "scheduledTaskId": None,
            "permissionMode": SECRET, "spawnSeed": SECRET, "mcpServers": {"x": SECRET},
            "allowedTools": [SECRET],
        }))
        (d / "local_broken.json").write_text("{not json")
        # Claude CLI: transcript whose body is a secret; the cliSessionId one must be deduped.
        enc = re.sub(r"[^A-Za-z0-9]", "-", str(self.wt))
        p = self.src.claude_projects / enc
        p.mkdir(parents=True)
        (p / "cli-uuid-1.jsonl").write_text(SECRET)
        (p / "cli-uuid-2.jsonl").write_text(SECRET)
        # Codex rollout: first line is session_meta with base_instructions.
        c = self.src.codex_sessions / "2026" / "11" / "10"
        c.mkdir(parents=True)
        meta = {"type": "session_meta", "payload": {
            "id": "codex-1", "cwd": str(self.repo), "timestamp": "2026-11-10T10:00:00Z",
            "git": {"branch": "main", "commit_hash": SECRET, "repository_url": SECRET},
            "base_instructions": {"text": SECRET}, "cli_version": SECRET}}
        (c / "rollout-2026-11-10T10-00-00-codex-1.jsonl").write_text(
            json.dumps(meta) + "\n" + json.dumps({"type": "message", "text": SECRET}) + "\n")
        # Cursor
        cur = self.src.cursor_projects / re.sub(r"[^A-Za-z0-9]", "-", str(self.repo)).lstrip("-") \
            / "agent-transcripts" / "chat-1"
        cur.mkdir(parents=True)
        (cur / "chat-1.jsonl").write_text(SECRET)

    def tearDown(self):
        self.tmp.cleanup()

    def run_collect(self, **kw):
        return estado.collect(self.src, scan_roots=[], **kw)


class CollectTests(EstadoFixture):
    def test_whitelist_and_no_secret_leak(self):
        report = self.run_collect()
        estado.assert_whitelist(report)  # raises on any extra key
        self.assertNotIn(SECRET, json.dumps(report))

    def test_whitelist_check_catches_extra_key(self):
        report = self.run_collect()
        report["sessions"][0]["permissionMode"] = "x"
        with self.assertRaises(AssertionError):
            estado.assert_whitelist(report)
        report = self.run_collect()
        report["repos"][0]["plans"][0]["nodes"][0]["extra"] = 1
        with self.assertRaises(AssertionError):
            estado.assert_whitelist(report)

    def test_adapters_and_dedupe(self):
        by_id = {s["id"]: s for s in self.run_collect()["sessions"]}
        self.assertEqual(by_id["local_abc123"]["harness"], "claude-desktop")
        self.assertEqual(by_id["local_abc123"]["title"], "Desktop title")
        self.assertEqual(by_id["local_abc123"]["repo"], "demo-repo")
        self.assertNotIn("cli-uuid-1", by_id)  # linked to the desktop session
        self.assertEqual(by_id["cli-uuid-2"]["harness"], "claude-cli")
        self.assertEqual(by_id["cli-uuid-2"]["branch"], "feat/second")
        self.assertEqual(by_id["cli-uuid-2"]["worktree"], str(self.wt))
        self.assertEqual(by_id["codex-1"]["harness"], "codex")
        self.assertEqual(by_id["chat-1"]["harness"], "cursor")
        self.assertEqual(by_id["chat-1"]["repo"], "demo-repo")
        self.assertIn("local_broken", by_id)  # broken JSON degrades to a partial session
        self.assertIsNone(by_id["local_broken"]["repo"])

    def test_reconcile_by_session_then_branch(self):
        by_id = {s["id"]: s for s in self.run_collect()["sessions"]}
        s = by_id["local_abc123"]
        self.assertEqual((s["plan"], s["node"]), ("demo-plan", "n1"))
        self.assertEqual(s["pr"], {"state": "unknown", "number": 7, "url": None})
        s = by_id["cli-uuid-2"]  # no session id match; branch feat/second -> n2
        self.assertEqual((s["plan"], s["node"]), ("demo-plan", "n2"))
        self.assertIsNone(by_id["codex-1"]["node"])  # main branch never matches by branch

    def test_plans_with_and_without_optional_columns(self):
        repo = self.run_collect()["repos"][0]
        plans = {p["id"]: p for p in repo["plans"]}
        self.assertEqual(plans["demo-plan"]["goal"], "Demo goal")
        self.assertEqual(plans["old-plan"]["nodes"][0]["session"], None)
        self.assertEqual(plans["old-plan"]["nodes"][0]["note"], "legacy columns only")
        self.assertEqual(len(repo["worktrees"]), 2)

    def test_days_window_and_exclude(self):
        self.assertEqual(self.run_collect(days=0)["sessions"], [])
        report = self.run_collect(exclude=["demo-repo"])
        self.assertEqual(report["repos"], [])
        self.assertTrue(all(s["repo"] is None for s in report["sessions"]))

    def test_scan_roots_discovers_repos_with_plans(self):
        report = estado.collect(self.src, days=0, scan_roots=[str(self.repo.parent)])
        self.assertEqual([r["name"] for r in report["repos"]], ["demo-repo"])

    def test_status_values(self):
        s = {x["id"]: x for x in self.run_collect()["sessions"]}
        self.assertEqual(s["local_abc123"]["status"], "active")
        later = self.run_collect(now=time.time() + 3 * 86400)
        self.assertEqual({x["status"] for x in later["sessions"]}, {"stale"})

    def test_prs_unknown_without_flag_and_without_gh_data(self):
        report = self.run_collect(with_prs=True)  # no remote: gh fails -> stays unknown
        self.assertTrue(all(s["pr"]["state"] in {"unknown", "none"} for s in report["sessions"]))

    def test_fingerprint_changes_with_files(self):
        before = estado.fingerprint(self.src)
        time.sleep(0.01)
        (self.src.codex_sessions / "2026/11/10/rollout-x.jsonl").write_text("{}")
        self.assertNotEqual(before, estado.fingerprint(self.src))


class PrCacheTests(EstadoFixture):
    def test_cache_within_60_seconds(self):
        cache = self.src.cache_dir
        cache.mkdir(parents=True)
        now = time.time()
        prs = {"feat/second": {"state": "open", "number": 9, "url": "https://example.com/9"}}
        (cache / "estado-prs.json").write_text(json.dumps({str(self.repo): {"at": now - 10, "prs": prs}}))
        self.assertEqual(estado._pr_lookup(str(self.repo), cache, now), prs)
        report = self.run_collect(with_prs=True, now=now)
        s = {x["id"]: x for x in report["sessions"]}
        self.assertEqual(s["cli-uuid-2"]["pr"]["number"], 9)
        self.assertEqual(s["codex-1"]["pr"]["state"], "none")


class CliTests(EstadoFixture):
    def test_json_output(self):
        from unittest.mock import patch
        real = estado.collect
        with patch("secretary.estado.collect", lambda **kw: real(self.src, **{**kw, "scan_roots": []})):
            result = CliRunner().invoke(app, ["estado", "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(result.stdout)
        estado.assert_whitelist(report)
        self.assertEqual(report["schema"], 1)


class ParsePlanTests(unittest.TestCase):
    def test_no_nodes_no_id_returns_none(self):
        self.assertIsNone(estado.parse_plan("just text", "docs/plans/x.md"))

    def test_bad_frontmatter_is_tolerated(self):
        plan = estado.parse_plan("---\n: : bad\n---\n## Nodes\n\n| id | status |\n|--|--|\n| n1 | done |\n", "docs/plans/x.md")
        self.assertEqual(plan["nodes"][0]["id"], "n1")


if __name__ == "__main__":
    unittest.main()
