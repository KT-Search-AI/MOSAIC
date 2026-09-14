"""Offline tests for mosaic_client against a local mock of the API contract.

Run:
    cd python && python -m unittest discover -s tests -v
"""

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mosaic_client import MosaicClient, MosaicError

SESSION = "mosaic_session=abc123"


class MockHandler(BaseHTTPRequestHandler):
    state = {"flaky": 0, "expire_next": False, "logins": 0}

    def log_message(self, *args):  # silence test output
        pass

    def _send(self, status, body, headers=None):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/version":
            return self._send(200, {"version": "0.1.0"})
        self._send(404, {"detail": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/mosaic/login":
            if body == {"username": "demo", "password": "pw"}:
                self.state["logins"] += 1
                return self._send(
                    200,
                    {"code": 0, "message": "ok", "payload": {"username": "demo"}},
                    {"Set-Cookie": SESSION + "; Path=/"},
                )
            return self._send(200, {"code": 40101, "message": "bad credentials"})
        if self.path == "/api/mosaic/answer":
            if self.state["flaky"] > 0:
                self.state["flaky"] -= 1
                return self._send(503, {"detail": "busy"})
            if self.state["expire_next"] or SESSION not in (self.headers.get("Cookie") or ""):
                self.state["expire_next"] = False
                return self._send(401, {"detail": "unauthorized"})
            if body["database"] not in ("medical", "novel"):
                return self._send(200, {"code": 40401, "message": "unknown database"})
            docs = [
                {"uid": f"doc-{i}", "rank": i, "score": 1.0 / i, "content": "..."}
                for i in range(1, 16)
            ]
            return self._send(200, {"code": 0, "message": "ok", "payload": {
                "answer": "Basal cell carcinoma.",
                "retrieval": {"backend": "mosaic", "documents": docs},
                "answering": {"domain": body["domain"],
                              "question_type": body["question_type"],
                              "query_id": body.get("query_id")},
            }})
        self._send(404, {"detail": "not found"})


class MosaicClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        MockHandler.state.update(flaky=0, expire_next=False, logins=0)
        self.client = MosaicClient(self.url, retry_backoff=0.01)

    def test_version(self):
        self.assertEqual(self.client.version()["version"], "0.1.0")

    def test_login_and_answer(self):
        self.assertEqual(self.client.login("demo", "pw")["username"], "demo")
        result = self.client.answer("medical", "q?", query_id="q-1")
        self.assertEqual(result["answer"], "Basal cell carcinoma.")
        self.assertEqual([d["rank"] for d in result["retrieval"]["documents"]],
                         list(range(1, 16)))
        self.assertEqual(result["answering"]["query_id"], "q-1")

    def test_bad_login(self):
        with self.assertRaises(MosaicError) as ctx:
            self.client.login("demo", "wrong")
        self.assertEqual(ctx.exception.code, 40101)

    def test_answer_without_login_is_401(self):
        with self.assertRaises(MosaicError) as ctx:
            self.client.answer("medical", "q?")
        self.assertEqual(ctx.exception.status, 401)

    def test_relogin_on_expired_session(self):
        self.client.login("demo", "pw")
        MockHandler.state["expire_next"] = True
        self.client.answer("medical", "q?")
        self.assertEqual(MockHandler.state["logins"], 2)

    def test_retries_transient_errors(self):
        self.client.login("demo", "pw")
        MockHandler.state["flaky"] = 2
        self.assertIn("answer", self.client.answer("novel", "q?", domain="novel"))

    def test_gives_up_after_max_retries(self):
        self.client.login("demo", "pw")
        MockHandler.state["flaky"] = 10
        with self.assertRaises(MosaicError) as ctx:
            self.client.answer("medical", "q?")
        self.assertEqual(ctx.exception.status, 503)

    def test_application_error(self):
        self.client.login("demo", "pw")
        with self.assertRaises(MosaicError) as ctx:
            self.client.answer("nope", "q?")
        self.assertEqual(ctx.exception.code, 40401)

    def test_validates_arguments(self):
        with self.assertRaises(ValueError):
            self.client.answer("medical", "q?", domain="legal")
        with self.assertRaises(ValueError):
            self.client.answer("medical", "q?", question_type="Trivia")


if __name__ == "__main__":
    unittest.main()
