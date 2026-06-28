"""Tests for the browser interface server (routing + JSON contract)."""

from __future__ import annotations

import json
import unittest
import urllib.request
import urllib.error

from src.web.server import WebInterface


class FakeApp:
    """Stand-in for FullscreenApp's web bridge (no Tk required)."""

    def __init__(self) -> None:
        self.cast_calls: list[str] = []
        self.refresh_calls = 0
        self.known_uuids = {"abc"}

    def get_web_snapshot(self) -> dict:
        return {
            "status": {"text": "Playing on Kitchen", "kind": "success"},
            "active_uuid": "abc",
            "busy": False,
            "scanning": False,
            "targets": [
                {"uuid": "abc", "name": "Kitchen", "is_group": False, "active": True},
            ],
            "level": 0.5,
            "rms": 0.16,
            "peak": 0.2,
        }

    def web_request_cast(self, uuid: str) -> bool:
        self.cast_calls.append(uuid)
        return uuid in self.known_uuids

    def web_request_refresh(self) -> None:
        self.refresh_calls += 1


class TestWebServer(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FakeApp()
        # Port 0 lets the OS pick a free port.
        self.web = WebInterface(self.app, host="127.0.0.1", port=0)
        self.web.start()
        self.port = self.web._server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.web.stop()

    def _get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return resp.status, resp.read()

    def _post(self, path: str, payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read())
            exc.close()
            return exc.code, body

    def test_index_serves_html(self) -> None:
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Pi Audio Cast", body)
        self.assertIn(b"manifest.webmanifest", body)

    def test_manifest_is_valid_json(self) -> None:
        status, body = self._get("/manifest.webmanifest")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["display"], "standalone")
        self.assertTrue(data["icons"])

    def test_service_worker_served(self) -> None:
        status, body = self._get("/sw.js")
        self.assertEqual(status, 200)
        self.assertIn(b"addEventListener", body)

    def test_icon_served(self) -> None:
        status, body = self._get("/icon.svg")
        self.assertEqual(status, 200)
        self.assertIn(b"<svg", body)

    def test_state_returns_snapshot(self) -> None:
        status, body = self._get("/api/state")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["status"]["text"], "Playing on Kitchen")
        self.assertEqual(data["targets"][0]["name"], "Kitchen")
        self.assertTrue(data["targets"][0]["active"])

    def test_cast_known_uuid(self) -> None:
        status, data = self._post("/api/cast", {"uuid": "abc"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(self.app.cast_calls, ["abc"])

    def test_cast_unknown_uuid_returns_404(self) -> None:
        status, data = self._post("/api/cast", {"uuid": "nope"})
        self.assertEqual(status, 404)
        self.assertFalse(data["ok"])

    def test_cast_missing_uuid_returns_400(self) -> None:
        status, data = self._post("/api/cast", {})
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_refresh(self) -> None:
        status, data = self._post("/api/refresh")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(self.app.refresh_calls, 1)

    def test_unknown_path_returns_404(self) -> None:
        status, data = self._post("/api/bogus")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
