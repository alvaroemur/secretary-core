#!/usr/bin/env python3
"""Servidor local para la wiki con API de comentarios.

Sirve archivos estáticos desde output/ y expone endpoints REST:
  GET  /api/comments/<slug>       → lista de comentarios (JSON)
  POST /api/comments/<slug>       → agregar comentario
  PUT  /api/comments/<slug>/<id>  → actualizar comentario
"""
from __future__ import annotations

import json
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
COMENTARIOS = ROOT / "comentarios"

COMENTARIOS.mkdir(exist_ok=True)


def _comment_path(slug: str) -> Path:
    safe = re.sub(r"[^a-z0-9_/-]", "", slug.lower().replace("\\", "/"))
    return COMENTARIOS / f"{safe.replace('/', '_')}.json"


def _read_comments(slug: str) -> list[dict]:
    p = _comment_path(slug)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _write_comments(slug: str, data: list[dict]) -> None:
    p = _comment_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class WikiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUTPUT), **kwargs)

    def do_GET(self):
        m = re.match(r"^/api/comments/(.+?)/?$", self.path)
        if m:
            slug = m.group(1).rstrip("/")
            data = _read_comments(slug)
            self._json_response(200, data)
            return
        super().do_GET()

    def do_POST(self):
        m = re.match(r"^/api/comments/(.+?)/?$", self.path)
        if not m:
            self._json_response(404, {"error": "not found"})
            return
        slug = m.group(1).rstrip("/")
        body = self._read_body()
        if body is None:
            return
        comments = _read_comments(slug)
        comments.append(body)
        _write_comments(slug, comments)
        self._json_response(201, body)

    def do_PUT(self):
        m_sync = re.match(r"^/api/sync-page/(.+?)/?$", self.path)
        if m_sync:
            slug = m_sync.group(1).rstrip("/")
            body = self._read_body()
            if body is None:
                return
            if isinstance(body, list):
                _write_comments(slug, body)
                self._json_response(200, {"synced": slug})
            else:
                self._json_response(400, {"error": "expected array"})
            return
        m = re.match(r"^/api/comments/(.+?)/@(.+)$", self.path)
        if not m:
            self._json_response(404, {"error": "not found"})
            return
        slug, cid = m.group(1), m.group(2)
        body = self._read_body()
        if body is None:
            return
        comments = _read_comments(slug)
        found = False
        for i, c in enumerate(comments):
            if c.get("id") == cid:
                comments[i] = body
                found = True
                break
        if not found:
            self._json_response(404, {"error": "comment not found"})
            return
        _write_comments(slug, comments)
        self._json_response(200, body)

    def do_DELETE(self):
        m = re.match(r"^/api/comments/(.+?)/@(.+)$", self.path)
        if not m:
            self._json_response(404, {"error": "not found"})
            return
        slug, cid = m.group(1), m.group(2)
        comments = _read_comments(slug)
        filtered = [c for c in comments if c.get("id") != cid]
        _write_comments(slug, filtered)
        self._json_response(200, {"deleted": cid})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._json_response(400, {"error": "empty body"})
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._json_response(400, {"error": "invalid JSON"})
            return None

    def _json_response(self, code: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    server = HTTPServer(("", port), WikiHandler)
    print(f"Wiki server en http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
