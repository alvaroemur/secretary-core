"""Read-only local HTTP view for :mod:`secretary.estado`."""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from secretary import estado

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_POLL_SECONDS = 1.0
_HOST_RE = re.compile(r"(?:127\.0\.0\.1|localhost)(?::([0-9]{1,5}))?\Z", re.IGNORECASE)

HTML = b"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>secretary estado</title>
<style>
:root{color-scheme:light dark;font:14px system-ui,sans-serif}body{margin:2rem;max-width:1200px}h1{margin-bottom:.25rem}#connection{color:#777}table{border-collapse:collapse;width:100%;margin:1rem 0 2rem}th,td{border-bottom:1px solid #8885;padding:.45rem;text-align:left;vertical-align:top}th{position:sticky;top:0;background:Canvas}code{font-size:.9em}.empty{color:#777}
</style>
</head>
<body>
<h1>secretary estado</h1>
<div id="connection">Connecting...</div>
<h2>Sessions</h2><div id="sessions"></div>
<h2>Plans</h2><div id="plans"></div>
<script>
const el=id=>document.getElementById(id);
const table=(headers,rows)=>{if(!rows.length){const p=document.createElement('p');p.className='empty';p.textContent='No data';return p}const t=document.createElement('table'),head=t.createTHead().insertRow();headers.forEach(h=>{const c=document.createElement('th');c.textContent=h;head.appendChild(c)});const b=t.createTBody();rows.forEach(row=>{const tr=b.insertRow();row.forEach(value=>{const c=tr.insertCell();c.textContent=value??''})});return t};
const replace=(id,node)=>{const root=el(id);root.replaceChildren(node)};
const render=data=>{replace('sessions',table(['time','harness','repo','branch','status','plan / node','title'],data.sessions.map(s=>[s.time,s.harness,s.repo,s.branch,s.status,[s.plan,s.node].filter(Boolean).join(' / '),s.title])));const rows=[];data.repos.forEach(r=>r.plans.forEach(p=>p.nodes.forEach(n=>rows.push([r.name,p.id,n.id,n.status,n.session,n.harness,n.branch,n.pr,n.note]))));replace('plans',table(['repo','plan','node','status','session','harness','branch','PR','note'],rows));el('connection').textContent=`Live - updated ${data.generated_at}`};
const stream=new EventSource('/events');stream.addEventListener('status',e=>render(JSON.parse(e.data)));stream.onerror=()=>{el('connection').textContent='Reconnecting...'};
</script>
</body>
</html>
"""


def valid_host(value: str | None) -> bool:
    """Accept only loopback Host values, with an optional valid port."""
    if not value:
        return False
    match = _HOST_RE.fullmatch(value.strip())
    if not match:
        return False
    port = match.group(1)
    return port is None or 0 < int(port) <= 65535


class StatusStore:
    """Cache a whitelisted report and refresh it when watched mtimes change."""

    def __init__(
        self,
        collect: Callable[[], dict[str, Any]],
        fingerprint: Callable[[list[str]], str],
    ) -> None:
        self._collect = collect
        self._fingerprint = fingerprint
        self._lock = threading.Lock()
        self._report: dict[str, Any] | None = None
        self._payload = ""
        self._signal = ""
        self._version = 0

    @staticmethod
    def _repo_paths(report: dict[str, Any] | None) -> list[str]:
        paths: list[str] = []
        for repo in (report or {}).get("repos", []):
            paths.append(repo["path"])
            paths.extend(w["path"] for w in repo["worktrees"] if w["path"])
        return paths

    def snapshot(self, *, force: bool = False) -> tuple[int, str]:
        with self._lock:
            signal = self._fingerprint(self._repo_paths(self._report))
            if force or self._report is None or signal != self._signal:
                report = self._collect()
                estado.assert_whitelist(report)
                self._report = report
                self._payload = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
                self._signal = self._fingerprint(self._repo_paths(report))
                self._version += 1
            return self._version, self._payload


class EstadoHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], store: StatusStore, poll_seconds: float) -> None:
        self.store = store
        self.poll_seconds = poll_seconds
        super().__init__(address, EstadoHandler)


class EstadoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: EstadoHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _reject_host(self) -> bool:
        if valid_host(self.headers.get("Host")):
            return False
        self.send_error(HTTPStatus.FORBIDDEN, "Host must be localhost or 127.0.0.1")
        return True

    def _send(self, status: HTTPStatus, content_type: str, body: bytes, *, head: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _read(self, *, head: bool = False) -> None:
        if self._reject_host():
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", HTML, head=head)
        elif path == "/api/status":
            _, payload = self.server.store.snapshot()
            self._send(HTTPStatus.OK, "application/json; charset=utf-8", payload.encode(), head=head)
        elif path == "/events" and not head:
            self._events()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_version = -1
        try:
            while True:
                version, payload = self.server.store.snapshot()
                if version != last_version:
                    self.wfile.write(f"event: status\ndata: {payload}\n\n".encode())
                    self.wfile.flush()
                    last_version = version
                time.sleep(self.server.poll_seconds)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:  # noqa: N802
        self._read()

    def do_HEAD(self) -> None:  # noqa: N802
        self._read(head=True)

    def _method_not_allowed(self) -> None:
        if self._reject_host():
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


def make_server(
    *,
    port: int,
    collect: Callable[[], dict[str, Any]],
    fingerprint: Callable[[list[str]], str],
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> EstadoHTTPServer:
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    if poll_seconds <= 0:
        raise ValueError("poll interval must be greater than zero")
    store = StatusStore(collect, fingerprint)
    store.snapshot(force=True)
    return EstadoHTTPServer((LOOPBACK, port), store, poll_seconds)
