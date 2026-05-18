#!/usr/bin/env python3
"""Bidirectional sync between local comment JSON files and Cloudflare KV.

Usage: python3 sync-comments.py [--once]

Without --once, runs every 30 seconds.
Requires WIKI_COMMENTS_API and WIKI_COMMENTS_SECRET env vars.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "comentarios"
LOCAL_DIR.mkdir(exist_ok=True)

API_URL = os.environ.get("WIKI_COMMENTS_API", "").rstrip("/")
API_SECRET = os.environ.get("WIKI_COMMENTS_SECRET", "")

if not API_URL or not API_SECRET:
    print("Set WIKI_COMMENTS_API and WIKI_COMMENTS_SECRET env vars")
    sys.exit(1)


def api(method: str, path: str, data: object = None) -> object:
    body = json.dumps(data).encode() if data else None
    req = Request(
        f"{API_URL}{path}",
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_SECRET}",
            "User-Agent": "wiki-sync/1.0",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def read_local() -> dict[str, list[dict]]:
    result = {}
    for f in LOCAL_DIR.glob("*.json"):
        slug = f.stem.replace("_", "/")
        try:
            result[slug] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return result


def write_local(slug: str, comments: list[dict]) -> None:
    safe = slug.replace("/", "_")
    path = LOCAL_DIR / f"{safe}.json"
    path.write_text(json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_comments(local: list[dict], remote: list[dict]) -> tuple[list[dict], bool]:
    by_id: dict[str, dict] = {}
    for c in local:
        by_id[c["id"]] = c
    changed = False
    for c in remote:
        cid = c["id"]
        if cid not in by_id:
            by_id[cid] = c
            changed = True
        else:
            existing = by_id[cid]
            local_replies = len(existing.get("replies") or [])
            remote_replies = len(c.get("replies") or [])
            local_resolved = existing.get("status") == "resolved"
            remote_resolved = c.get("status") == "resolved"
            if remote_replies > local_replies or (remote_resolved and not local_resolved):
                by_id[cid] = c
                changed = True
    for c in local:
        cid = c["id"]
        if cid in by_id and by_id[cid] is not c:
            continue
        by_id[cid] = c
    return sorted(by_id.values(), key=lambda x: x.get("created", "")), changed


def sync_once() -> None:
    try:
        remote_all = api("GET", "/api/sync")
    except (URLError, OSError) as e:
        print(f"  fetch failed: {e}")
        return

    local_all = read_local()
    all_slugs = set(list(remote_all.keys()) + list(local_all.keys()))
    upload = {}
    local_changed = 0

    for slug in all_slugs:
        local_comments = local_all.get(slug, [])
        remote_comments = remote_all.get(slug, [])
        merged, changed = merge_comments(local_comments, remote_comments)

        if merged != local_comments:
            write_local(slug, merged)
            local_changed += 1

        if merged != remote_comments:
            upload[slug] = merged

    if upload:
        try:
            api("PUT", "/api/sync", upload)
            print(f"  → pushed {len(upload)} slug(s) to remote")
        except (URLError, OSError) as e:
            print(f"  push failed: {e}")

    if local_changed:
        print(f"  → updated {local_changed} local file(s)")

    if not upload and not local_changed:
        print("  in sync")


def main() -> None:
    once = "--once" in sys.argv
    print(f"Wiki comment sync — {API_URL}")
    if once:
        sync_once()
    else:
        while True:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] syncing...")
            sync_once()
            time.sleep(30)


if __name__ == "__main__":
    main()
