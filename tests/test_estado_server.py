"""Tests for the read-only local `secretary estado serve` view."""

import http.client
import json
import threading
import unittest

from secretary.estado_server import StatusStore, make_server, valid_host


def report() -> dict:
    return {
        "schema": 1,
        "generated_at": "2026-11-11T12:00:00Z",
        "repos": [],
        "sessions": [],
        "warnings": [],
    }


class HostTests(unittest.TestCase):
    def test_only_loopback_host_values_are_allowed(self):
        for value in ("127.0.0.1", "127.0.0.1:8765", "localhost", "LOCALHOST:1"):
            self.assertTrue(valid_host(value), value)
        for value in (None, "", "example.com", "127.0.0.2", "localhost.example.com", "localhost:0", "localhost:65536"):
            self.assertFalse(valid_host(value), value)


class StoreTests(unittest.TestCase):
    def test_mtime_signal_controls_collection(self):
        signal = ["a"]
        calls = []
        store = StatusStore(lambda: calls.append(1) or report(), lambda _repos: signal[0])

        first = store.snapshot()
        second = store.snapshot()
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

        signal[0] = "b"
        version, payload = store.snapshot()
        self.assertEqual(version, 2)
        self.assertEqual(json.loads(payload), report())
        self.assertEqual(len(calls), 2)

    def test_non_whitelisted_report_is_rejected(self):
        bad = report()
        bad["content"] = "not metadata"
        store = StatusStore(lambda: bad, lambda _repos: "a")
        with self.assertRaises(AssertionError):
            store.snapshot()


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server(
            port=0,
            collect=report,
            fingerprint=lambda _repos: "a",
            poll_seconds=0.01,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, method: str, path: str, host: str = "127.0.0.1"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host)
        conn.endheaders()
        response = conn.getresponse()
        body = response.read()
        conn.close()
        return response, body

    def test_html_and_json_are_read_only(self):
        response, body = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn(b"EventSource('/events')", body)

        response, body = self.request("GET", "/api/status")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body), report())

        response, _ = self.request("POST", "/api/status")
        self.assertEqual(response.status, 405)
        self.assertEqual(response.getheader("Allow"), "GET, HEAD")

    def test_event_stream_starts_with_whitelisted_report(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        conn.request("GET", "/events")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.readline(), b"event: status\n")
        payload = json.loads(response.readline().removeprefix(b"data: "))
        self.assertEqual(payload, report())
        conn.close()

    def test_host_header_is_checked_before_routing(self):
        response, _ = self.request("GET", "/api/status", host="example.com")
        self.assertEqual(response.status, 403)


if __name__ == "__main__":
    unittest.main()
