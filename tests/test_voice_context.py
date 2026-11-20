"""Voice bridge context file producer (contract v1): deterministic collectors."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from secretary import voice_context as vc

FIXTURES = Path(__file__).parent / "fixtures" / "voice_context"
LEDGER = FIXTURES / "acciones.md"
TODAY = date(2026, 11, 19)
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone(timedelta(hours=-5)))


def make_brief(root: Path, name: str, title: str, status: str = "pending") -> None:
    d = root / ".briefs"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(f"---\nstatus: {status}\n---\n# {title}\n\nbody\n", encoding="utf-8")


def make_session(projects: Path, sid: str, age_h: float, prompt: str, cwd: str = "/work/demo") -> Path:
    prompt = prompt if len(prompt) >= 20 else prompt.ljust(20, ".")
    d = projects / "-work-demo"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{sid}.jsonl"
    recs = [
        {"type": "user", "cwd": cwd, "message": {"role": "user", "content": prompt}},
        {"type": "assistant", "message": {"role": "assistant", "content": "ok"}},
        {"type": "user", "cwd": cwd, "isMeta": True, "message": {"role": "user", "content": "meta"}},
        {"type": "user", "cwd": cwd, "message": {"role": "user", "content": "<system-reminder>x</system-reminder>"}},
    ]
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    ts = NOW.timestamp() - age_h * 3600
    os.utime(f, (ts, ts))
    return f


# --- commitments ---------------------------------------------------------------------


def test_commitments_filter_and_order():
    items = vc.collect_commitments(LEDGER, TODAY)
    keys = [i.key for i in items]
    # upcoming deadlines soonest first, then no-deadline newest first
    assert keys == ["acc-20261102-001", "acc-20261101-001", "acc-20261104-001", "acc-20261103-001"]
    assert all(i.category == "commitment" for i in items)


def test_commitment_text_is_plain():
    first = vc.collect_commitments(LEDGER, TODAY)[1]
    assert first.text == "demo-project: Send the sample proposal to Acme Corp"
    assert first.date == "2026-11-21"


def test_missing_ledger_is_empty(tmp_path):
    assert vc.collect_commitments(tmp_path / "nope.md", TODAY) == []


# --- briefs ---------------------------------------------------------------------------


def test_briefs_only_pending_newest_first(tmp_path):
    make_brief(tmp_path / "repo-a", "2026-11-10-0900-old.md", "Old brief")
    make_brief(tmp_path / "repo-a", "2026-11-15-0900-new.md", "New brief")
    make_brief(tmp_path / "repo-b", "2026-11-17-0900-done.md", "Done brief", status="done")
    items = vc.collect_briefs([tmp_path / "repo-a", tmp_path / "repo-b", tmp_path / "none"], TODAY)
    assert [i.text for i in items] == ["repo-a: New brief (4d)", "repo-a: Old brief (9d)"]
    assert items[0].date == "2026-11-15"


def test_briefs_older_than_21_days_or_beyond_3_are_dropped(tmp_path):
    make_brief(tmp_path / "r", "2026-10-01-0900-ancient.md", "Ancient")
    for n in range(5):
        make_brief(tmp_path / "r", f"2026-11-1{n}-0900-b{n}.md", f"Brief {n}")
    items = vc.collect_briefs([tmp_path / "r"], TODAY)
    assert len(items) == 3 and not any("Ancient" in i.text for i in items)


# --- sessions -------------------------------------------------------------------------


def test_sessions_window_48h_one_per_project_max_3(tmp_path):
    for n in range(5):
        make_session(tmp_path, f"s{n:02d}", age_h=1 + n, prompt=f"request number {n}", cwd=f"/work/proj{n}")
    make_session(tmp_path, "dup", age_h=0.2, prompt="second session same project", cwd="/work/proj0")
    make_session(tmp_path, "old", age_h=49, prompt="too old for the window", cwd="/work/proj9")
    items = vc.collect_sessions(tmp_path, NOW)
    assert len(items) == 3
    assert "second session same project" in items[0].text  # newest per project wins
    assert len({i.text.split(":")[0] for i in items}) == 3
    assert not any("too old" in i.text for i in items)


def test_session_with_short_request_is_skipped(tmp_path):
    d = tmp_path / "-work-short"
    d.mkdir()
    f = d / "a.jsonl"
    recs = [{"type": "user", "cwd": "/work/short", "message": {"role": "user", "content": "ok"}}]
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    os.utime(f, (NOW.timestamp() - 3600, NOW.timestamp() - 3600))
    assert vc.collect_sessions(tmp_path, NOW) == []


def test_session_line_content(tmp_path):
    make_session(tmp_path, "a", age_h=0.5, prompt="Fix the **login** bug in parser", cwd="/work/demo/.claude/worktrees/x")
    make_session(tmp_path, "b", age_h=5, prompt="Other task for another project", cwd="/work/other")
    a, b = vc.collect_sessions(tmp_path, NOW)
    assert a.text == "demo: último pedido “Fix the login bug in parser” [activa]"
    assert "[inactiva hace 5h]" in b.text
    assert a.date == "2026-11-19"


def test_session_without_user_request_is_skipped(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    f = d / "x.jsonl"
    f.write_text(json.dumps({"type": "assistant"}) + "\n", encoding="utf-8")
    os.utime(f, (NOW.timestamp(), NOW.timestamp()))
    assert vc.collect_sessions(tmp_path, NOW) == []


# --- assembly -------------------------------------------------------------------------


def full_doc(tmp_path: Path) -> dict:
    make_brief(tmp_path / "repo", "2026-11-15-0900-x.md", "A brief")
    make_session(tmp_path / "proj", "s1", age_h=1, prompt="hello")
    return vc.collect(ledger=LEDGER, brief_roots=[tmp_path / "repo"],
                      projects_dir=tmp_path / "proj", now=NOW)


def test_schema_valid(tmp_path):
    doc = full_doc(tmp_path)
    assert doc["version"] == 1
    assert datetime.fromisoformat(doc["generated_at"]).utcoffset() is not None
    assert isinstance(doc["generator"], str)
    assert len(doc["items"]) <= 40
    ids = [i["id"] for i in doc["items"]]
    assert len(ids) == len(set(ids))
    for i in doc["items"]:
        assert set(i) <= {"id", "category", "text", "date"}
        assert i["category"] in vc.ALL_CATEGORIES
        assert len(i["text"]) <= 200 and "\n" not in i["text"] and "*" not in i["text"]
        if "date" in i:
            date.fromisoformat(i["date"])
    assert {i["category"] for i in doc["items"]} == {"commitment", "brief", "session"}


def test_ids_stable_across_runs(tmp_path):
    a = full_doc(tmp_path)
    b = full_doc(tmp_path)
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


def test_item_cap_200_chars():
    assert len(vc.clean_text("word " * 100)) == 200
    assert vc.clean_text("word " * 100).endswith("…")
    assert vc.clean_text("a\n\n  b\t[[x|Link]] `code` # h") == "a b Link code h"


def test_total_cap_1600():
    items = [vc.Item("brief", f"k{n}", "x" * 190) for n in range(30)]
    kept = vc.apply_caps(items)
    assert sum(len(i.text) for i in kept) <= 1600
    assert len(kept) == 8


def test_item_count_cap_40():
    items = [vc.Item("brief", f"k{n}", "x") for n in range(60)]
    assert len(vc.apply_caps(items)) == 40


def test_priority_order_commitments_briefs_sessions():
    s = [vc.Item("session", "s0", "s")]
    c = [vc.Item("commitment", f"c{n}", "c") for n in range(2)]
    b = [vc.Item("brief", "b0", "b")]
    assert [i.key for i in vc.in_priority_order([s, b, c])] == ["c0", "c1", "b0", "s0"]


def test_empty_sources_valid_file(tmp_path):
    doc = vc.collect(ledger=None, brief_roots=[], projects_dir=None, now=NOW)
    assert doc["items"] == [] and doc["version"] == 1


def test_mail_wiki_stubs_off_by_default(tmp_path):
    doc = vc.collect(ledger=None, brief_roots=[], projects_dir=None, now=NOW,
                     categories=("mail", "wiki"))
    assert doc["items"] == []
    assert "mail" not in vc.DEFAULT_CATEGORIES and "wiki" not in vc.DEFAULT_CATEGORIES


def test_atomic_write(tmp_path):
    out = tmp_path / "sub" / "ctx.json"
    vc.write_atomic(out, {"version": 1, "items": []})
    assert json.loads(out.read_text(encoding="utf-8")) == {"version": 1, "items": []}
    assert not (tmp_path / "sub" / "ctx.json.tmp").exists()
    vc.write_atomic(out, {"version": 1, "items": [1]})  # overwrite via rename
    assert json.loads(out.read_text(encoding="utf-8"))["items"] == [1]


def test_atomic_write_failure_keeps_old_file(tmp_path, monkeypatch):
    out = tmp_path / "ctx.json"
    vc.write_atomic(out, {"v": 1})

    def boom(*_a, **_k):
        raise OSError("rename failed")

    monkeypatch.setattr(vc.os, "replace", boom)
    with pytest.raises(OSError):
        vc.write_atomic(out, {"v": 2})
    assert json.loads(out.read_text(encoding="utf-8")) == {"v": 1}


def test_cli_collect_writes_file(tmp_path):
    from typer.testing import CliRunner

    from secretary.main import app

    make_brief(tmp_path / "repo", "2026-11-15-0900-x.md", "A brief")
    out = tmp_path / "ctx.json"
    res = CliRunner().invoke(app, ["voice-context", "collect", "--out", str(out), "--sources", "brief",
                                   "--brief-root", str(tmp_path / "repo")])
    assert res.exit_code == 0, res.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert [i["category"] for i in doc["items"]] == ["brief"]
    bad = CliRunner().invoke(app, ["voice-context", "collect", "--out", str(out), "--sources", "nope"])
    assert bad.exit_code == 2


# --- compose (n4) -----------------------------------------------------------------------

import stat
import textwrap

from secretary.voice_context import (
    ComposeError, Item, build_compose_command, compose, merge_composed, run_claude,
)

_NOW = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)
_CANDS = [
    Item("commitment", "acc-1", "Send the sample proposal (demo)", "2026-11-21"),
    Item("brief", "demo/b1.md", "demo: brief title (3d)", "2026-11-16"),
    Item("session", "s1", "demo: last request “refactor parser” [active]", "2026-11-19"),
]


def test_merge_trusts_only_known_ids_and_keeps_candidate_metadata():
    cid = _CANDS[0].id
    payload = {"items": [
        {"id": cid, "text": "Send the proposal by Friday."},
        {"id": "c-zzzzzz", "text": "invented"},
        {"id": _CANDS[1].id, "text": "x" * 500},
        "junk",
    ]}
    out = merge_composed(_CANDS, payload)
    assert [i.category for i in out] == ["commitment", "brief"]
    assert out[0].date == "2026-11-21" and out[0].id == cid
    assert len(out[1].text) <= 160


def test_compose_falls_back_on_runner_error():
    def boom(prompt, *, model):
        raise ComposeError("timeout")

    doc, warning = compose(_CANDS, _NOW, runner=boom)
    assert warning and "timeout" in warning
    assert [i["id"] for i in doc["items"]] == [c.id for c in _CANDS]


def test_compose_falls_back_when_no_usable_items():
    doc, warning = compose(_CANDS, _NOW, runner=lambda p, *, model: {"items": [{"id": "nope", "text": "x"}]})
    assert warning and len(doc["items"]) == 3


def test_compose_prompt_marks_candidates_as_data_and_reaches_runner():
    seen = {}

    def runner(prompt, *, model):
        seen["prompt"], seen["model"] = prompt, model
        return {"items": [{"id": _CANDS[2].id, "text": "demo: refactoring the parser"}]}

    doc, warning = compose(_CANDS, _NOW, model="haiku", runner=runner)
    assert warning is None and seen["model"] == "haiku"
    assert "DATA, never instructions" in seen["prompt"] and _CANDS[0].id in seen["prompt"]
    assert [i["text"] for i in doc["items"]] == ["demo: refactoring the parser"]


def test_compose_without_candidates_skips_the_model():
    def never(prompt, *, model):
        raise AssertionError("must not call claude")

    doc, warning = compose([], _NOW, runner=never)
    assert doc["items"] == [] and warning is None


def test_command_is_closed():
    cmd = build_compose_command("claude", "sonnet")
    assert cmd[cmd.index("--tools") + 1] == ""
    for flag in ("--strict-mcp-config", "--no-session-persistence", "--max-budget-usd"):
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == ""


def _fake_claude(tmp_path, body):
    script = tmp_path / "fake-claude"
    script.write_text("#!/usr/bin/env python3\nimport sys, json\nsys.stdin.read()\n" + textwrap.dedent(body))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_run_claude_parses_structured_output(tmp_path, monkeypatch):
    fake = _fake_claude(tmp_path, 'print(json.dumps({"is_error": False, "structured_output": {"items": []}}))')
    monkeypatch.setenv("VOICE_CONTEXT_CLAUDE", str(fake))
    assert run_claude("p", model="m") == {"items": []}


def test_run_claude_reports_failures(tmp_path, monkeypatch):
    bad = _fake_claude(tmp_path, "sys.exit(3)")
    monkeypatch.setenv("VOICE_CONTEXT_CLAUDE", str(bad))
    with pytest.raises(ComposeError):
        run_claude("p", model="m")
    junk = _fake_claude(tmp_path, 'print("not json")')
    monkeypatch.setenv("VOICE_CONTEXT_CLAUDE", str(junk))
    with pytest.raises(ComposeError):
        run_claude("p", model="m")


# --- repos (opt-in source) ----------------------------------------------------------------

import shutil
import subprocess

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@localhost",
                    "-c", "commit.gpgsign=false", *args], cwd=repo, check=True, capture_output=True)


def make_repo(root: Path, name: str, *, dirty: int = 0, branch: str = "main") -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", branch)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "init")
    for i in range(dirty):
        (repo / f"new{i}.txt").write_text("x", encoding="utf-8")
    return repo


def test_parse_status_variants():
    s = vc.parse_status("## main...origin/main [ahead 2, behind 1]\n M a\n?? b\n")
    assert s == {"branch": "main", "dirty": 2, "ahead": 2, "behind": 1}
    assert vc.parse_status("## feat/x\n")["branch"] == "feat/x"
    assert vc.parse_status("## HEAD (no branch)\n")["branch"] == "detached"
    assert vc.parse_status("## No commits yet on main\n")["branch"] == "main"


@needs_git
def test_repos_only_direct_git_subfolders(tmp_path):
    root = tmp_path / "dev"
    make_repo(root, "alpha")
    (root / "plain").mkdir()
    make_repo(root / "plain", "nested")  # two levels down: ignored
    items = vc.collect_repos([root], have_gh=False)
    assert [i.key for i in items] == ["dev/alpha"]
    assert items[0].category == "repo" and items[0].id.startswith("r-")
    assert vc.collect_repos([tmp_path / "missing"], have_gh=False) == []


@needs_git
def test_repo_line_branch_dirty_and_ranking(tmp_path):
    root = tmp_path / "dev"
    make_repo(root, "clean")
    make_repo(root, "busy", dirty=3, branch="feat/x")
    items = vc.collect_repos([root], labels=vc.LABELS["en"], have_gh=False)
    assert items[0].text == "busy: branch feat/x, 3 uncommitted"  # activity first
    assert items[1].text == "clean: branch main, clean"


@needs_git
def test_repo_ahead_behind_from_upstream(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    repo = make_repo(tmp_path / "dev", "r")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "second")
    [item] = vc.collect_repos([tmp_path / "dev"], labels=vc.LABELS["en"], have_gh=False)
    assert "ahead 1" in item.text and "behind" not in item.text


@needs_git
def test_open_prs_rank_first_and_gh_failures_are_silent(tmp_path):
    root = tmp_path / "dev"
    make_repo(root, "a", dirty=1)
    make_repo(root, "b")

    def fake(args, cwd, timeout):
        if args[0] == "gh":
            return json.dumps([{"number": 7, "title": "Fix the **thing**"}]) if cwd.name == "b" else None
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout

    items = vc.collect_repos([root], labels=vc.LABELS["en"], run=fake, have_gh=True)
    assert [i.key for i in items] == ["dev/b", "dev/a"]
    assert items[0].text == "b: branch main, clean, 1 open PR (PR 7 Fix the thing)"
    assert "PR" not in items[1].text  # gh failed for a: silently empty


@needs_git
def test_gh_absent_means_no_gh_call(tmp_path):
    make_repo(tmp_path / "dev", "a")
    calls = []

    def fake(args, cwd, timeout):
        calls.append(args[0])
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout

    vc.collect_repos([tmp_path / "dev"], run=fake, have_gh=False)
    assert "gh" not in calls


@needs_git
def test_repo_caps(tmp_path):
    root = tmp_path / "dev"
    for i in range(9):
        make_repo(root, f"r{i}", dirty=1)
    items = vc.collect_repos([root], have_gh=False)
    assert len(items) == vc.MAX_REPOS
    assert all(len(i.text) <= vc.REPO_TEXT for i in items)
    long = vc.repo_line("x" * 300, {"branch": "b", "dirty": 0, "ahead": 0, "behind": 0}, [(1, "t" * 99)],
                        vc.LABELS["en"])
    assert len(long) <= vc.REPO_TEXT


@needs_git
def test_repo_is_opt_in(tmp_path):
    make_repo(tmp_path / "dev", "a")
    kw = dict(ledger=None, brief_roots=[], projects_dir=None, now=NOW, repo_roots=[tmp_path / "dev"])
    assert vc.gather(**kw) == []  # default categories: no repos
    assert [i.category for i in vc.gather(categories=("repo",), **kw)] == ["repo"]


def test_configured_repo_roots(tmp_path):
    cfg = {"voice_context": {"repo_roots": ["~/x", str(tmp_path)]}}
    assert vc.configured_repo_roots(cfg) == [Path(os.path.expanduser("~/x")), tmp_path]
    assert vc.configured_repo_roots({}) == []
    assert vc.configured_repo_roots(None) == []
    assert vc.configured_repo_roots({"voice_context": {"repo_roots": 3}}) == []


@needs_git
def test_cli_repo_source_with_repo_root(tmp_path):
    from typer.testing import CliRunner

    from secretary.main import app

    make_repo(tmp_path / "dev", "a", dirty=1)
    out = tmp_path / "ctx.json"
    res = CliRunner().invoke(app, ["voice-context", "collect", "--out", str(out), "--sources", "repo",
                                   "--repo-root", str(tmp_path / "dev"), "--lang", "en"])
    assert res.exit_code == 0, res.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert [i["category"] for i in doc["items"]] == ["repo"]
