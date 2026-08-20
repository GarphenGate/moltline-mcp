"""Offline tests for the moltline-mcp stdio bridge.

No network, no dependencies - the bridge is exercised against fake HTTP
responses so the framing, session handling and error relay paths are all
covered. Run with: python -m unittest -v
"""
import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout

import moltline_mcp as m


class Headers(dict):
    """Case-insensitive header lookup, like http.client.HTTPMessage."""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class FakeResponse:
    """Minimal stand-in for the object urlopen returns."""

    def __init__(self, body=b"", headers=None, status=200,
                 content_type="application/json"):
        self._body = body
        hdrs = dict(headers or {})
        hdrs.setdefault("Content-Type", content_type)
        self.headers = Headers(hdrs)
        self.status = status

    def read(self):
        return self._body

    def __iter__(self):
        return iter(self._body.splitlines(keepends=True))


def relay(bridge, response, sent_message=None):
    """Run one response through the bridge and return the emitted lines."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        bridge._relay_response(response, sent_message or {})
    return [ln for ln in buf.getvalue().split("\n") if ln]


class ServerListTests(unittest.TestCase):

    def test_fourteen_servers_no_duplicates(self):
        self.assertEqual(len(m.SERVERS), 19)
        self.assertEqual(len(set(m.SERVERS)), 19)

    def test_default_server_is_in_the_whitelist(self):
        self.assertIn("catalog", m.SERVERS)

    def test_slugs_are_url_safe(self):
        for slug in m.SERVERS:
            self.assertRegex(slug, r"^[a-z][a-z0-9-]*$", slug)


class FramingTests(unittest.TestCase):

    def test_each_message_is_exactly_one_line(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            m._write_out('{"a":1}')
            m._write_out('{"b":2}\n')
        self.assertEqual(buf.getvalue(), '{"a":1}\n{"b":2}\n')

    def test_json_response_is_relayed_verbatim(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        out = relay(bridge, FakeResponse(json.dumps(payload).encode()))
        self.assertEqual(len(out), 1)
        self.assertEqual(json.loads(out[0]), payload)

    def test_202_and_204_relay_nothing(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        for status in (202, 204):
            out = relay(bridge, FakeResponse(b'{"ignored":true}', status=status))
            self.assertEqual(out, [], "status %d should emit nothing" % status)

    def test_non_json_payload_is_dropped(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        out = relay(bridge, FakeResponse(b"<html>gateway error</html>"))
        self.assertEqual(out, [])

    def test_non_json_input_line_is_dropped_without_output(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            bridge.forward("this is not json")
        self.assertEqual(buf.getvalue(), "")


class SseTests(unittest.TestCase):
    """SSE framing is where a bridge most often loses or merges messages."""

    def test_multiple_events_become_multiple_messages(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        body = (b'data: {"jsonrpc":"2.0","id":1,"result":1}\n'
                b'\n'
                b'data: {"jsonrpc":"2.0","id":2,"result":2}\n'
                b'\n')
        out = relay(bridge, FakeResponse(body, content_type="text/event-stream"))
        self.assertEqual(len(out), 2)
        self.assertEqual(json.loads(out[0])["id"], 1)
        self.assertEqual(json.loads(out[1])["id"], 2)

    def test_multi_line_data_is_joined_with_newlines(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        body = (b'data: {"jsonrpc":"2.0","id":9,\n'
                b'data: "result":{"v":1}}\n'
                b'\n')
        out = relay(bridge, FakeResponse(body, content_type="text/event-stream"))
        self.assertEqual(len(out), 1)
        self.assertEqual(json.loads(out[0])["id"], 9)

    def test_trailing_event_without_blank_line_is_flushed(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        body = b'data: {"jsonrpc":"2.0","id":3,"result":true}\n'
        out = relay(bridge, FakeResponse(body, content_type="text/event-stream"))
        self.assertEqual(len(out), 1)
        self.assertEqual(json.loads(out[0])["id"], 3)

    def test_sse_comments_and_event_names_are_ignored(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        body = (b': keep-alive\n'
                b'event: message\n'
                b'data: {"jsonrpc":"2.0","id":4,"result":"x"}\n'
                b'\n')
        out = relay(bridge, FakeResponse(body, content_type="text/event-stream"))
        self.assertEqual(len(out), 1)
        self.assertEqual(json.loads(out[0])["id"], 4)


class SessionTests(unittest.TestCase):

    def test_session_id_is_captured_case_insensitively(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        bridge._capture_session(Headers({"mcp-session-id": "abc123"}))
        self.assertEqual(bridge.session_id, "abc123")

    def test_first_session_id_wins(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        bridge._capture_session(Headers({"Mcp-Session-Id": "first"}))
        bridge._capture_session(Headers({"Mcp-Session-Id": "second"}))
        self.assertEqual(bridge.session_id, "first")

    def test_session_and_version_are_sent_once_known(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        self.assertNotIn("Mcp-Session-Id", bridge._headers())
        bridge.session_id = "sid"
        bridge.protocol_version = "2025-06-18"
        headers = bridge._headers()
        self.assertEqual(headers["Mcp-Session-Id"], "sid")
        self.assertEqual(headers["MCP-Protocol-Version"], "2025-06-18")
        self.assertIn("moltline-mcp/", headers["User-Agent"])


class ProtocolVersionTests(unittest.TestCase):

    def test_version_recorded_from_successful_initialize(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        sent = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "result": {"protocolVersion": "2025-06-18"}}).encode()
        relay(bridge, FakeResponse(body), sent)
        self.assertEqual(bridge.protocol_version, "2025-06-18")

    def test_version_not_recorded_from_other_methods(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        sent = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "result": {"protocolVersion": "2025-06-18"}}).encode()
        relay(bridge, FakeResponse(body), sent)
        self.assertIsNone(bridge.protocol_version)

    def test_version_not_recorded_from_initialize_error(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        sent = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "error": {"code": -32600, "message": "nope"}}).encode()
        relay(bridge, FakeResponse(body), sent)
        self.assertIsNone(bridge.protocol_version)


class HttpErrorTests(unittest.TestCase):

    def _error(self, code, body, headers=None):
        return urllib.error.HTTPError(
            "http://example.invalid/catalog", code, "err",
            Headers(headers or {}), io.BytesIO(body))

    def test_jsonrpc_error_document_is_relayed_verbatim(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        doc = {"jsonrpc": "2.0", "id": 7,
               "error": {"code": -32000, "message": "premium tool"}}
        buf = io.StringIO()
        with redirect_stdout(buf):
            bridge._relay_http_error(self._error(402, json.dumps(doc).encode()), 7)
        self.assertEqual(json.loads(buf.getvalue().strip()), doc)

    def test_opaque_error_body_becomes_internal_error(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            bridge._relay_http_error(self._error(502, b"<html>bad gateway</html>"), 7)
        emitted = json.loads(buf.getvalue().strip())
        self.assertEqual(emitted["id"], 7)
        self.assertEqual(emitted["error"]["code"], -32603)
        self.assertIn("502", emitted["error"]["message"])

    def test_error_without_request_id_emits_nothing(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            bridge._relay_http_error(self._error(500, b"boom"), None)
        self.assertEqual(buf.getvalue(), "")

    def test_session_is_captured_from_error_headers(self):
        bridge = m.Bridge("http://example.invalid/catalog", 5)
        err = self._error(400, b"nope", {"Mcp-Session-Id": "from-error"})
        with redirect_stdout(io.StringIO()):
            bridge._relay_http_error(err, 1)
        self.assertEqual(bridge.session_id, "from-error")


if __name__ == "__main__":
    unittest.main()
