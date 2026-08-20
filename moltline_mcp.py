#!/usr/bin/env python3
"""moltline-mcp: a thin stdio bridge to the Moltline Studio hosted MCP fleet.

Bridges MCP clients that only speak stdio JSON-RPC (newline-delimited) to
Moltline Studio's hosted MCP servers, which speak MCP Streamable HTTP at
https://mcp.moltlinestudio.com/<server>.

The bridge is intentionally minimal and dependency-free:

  stdin  --> JSON-RPC message --> HTTP POST --> hosted server
  stdout <-- JSON-RPC message <-- JSON or SSE response

It forwards messages verbatim (no inspection, mutation, or telemetry),
tracks the Mcp-Session-Id header the server assigns, and echoes the
negotiated MCP protocol version on subsequent requests as required by the
Streamable HTTP transport spec.

Usage:
    moltline-mcp [server]

where [server] is one of the 19 Moltline server slugs (default: catalog).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import urllib.error
import urllib.request

__version__ = "1.1.0"

DEFAULT_BASE_URL = "https://mcp.moltlinestudio.com"

# The 19 hosted servers. Kept as an explicit whitelist so a typo fails fast
# with a helpful message instead of a confusing HTTP 404 mid-session.
SERVERS = (
    "catalog",
    "codereview",
    "timeops",
    "data",
    "business",
    "creator",
    "educator",
    "govern",
    "humanizer",
    "merchant",
    "outbound",
    "personal",
    "research",
    "skillmd-lint",
    "shipping",
    "shopify",
    "dropship",
    "recall",
    "vision",
)

_stdout_lock = threading.Lock()


def _debug(msg: str) -> None:
    if os.environ.get("MOLTLINE_DEBUG"):
        print("[moltline-mcp] " + msg, file=sys.stderr, flush=True)


def _write_out(obj_text: str) -> None:
    """Write one JSON-RPC message to stdout (newline-delimited framing)."""
    with _stdout_lock:
        sys.stdout.write(obj_text.rstrip("\n") + "\n")
        sys.stdout.flush()


class Bridge:
    """Forwards JSON-RPC messages between stdio and one hosted MCP server."""

    def __init__(self, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.session_id: str | None = None
        self.protocol_version: str | None = None

    # -- outbound ---------------------------------------------------------

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "moltline-mcp/" + __version__,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    def forward(self, raw: str) -> None:
        """POST one client message to the server and relay the response."""
        try:
            message = json.loads(raw)
        except ValueError:
            _debug("dropping non-JSON input line")
            return

        request_id = message.get("id") if isinstance(message, dict) else None

        req = urllib.request.Request(
            self.endpoint,
            data=raw.encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self._capture_session(resp.headers)
                self._relay_response(resp, message)
        except urllib.error.HTTPError as err:
            self._relay_http_error(err, request_id)
        except Exception as err:  # network failure, timeout, ...
            if request_id is not None:
                self._emit_error(request_id, -32603,
                                 "moltline-mcp transport error: %s" % err)
            _debug("transport error: %r" % err)

    # -- inbound ----------------------------------------------------------

    def _capture_session(self, headers) -> None:
        sid = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
        if sid and not self.session_id:
            self.session_id = sid
            _debug("session established: " + sid)

    def _relay_response(self, resp, sent_message) -> None:
        status = resp.status
        ctype = (resp.headers.get("Content-Type") or "").lower()

        if status == 202 or status == 204:
            return  # accepted notification/response: nothing to relay

        if "text/event-stream" in ctype:
            # SSE: each event's data payload is one JSON-RPC message.
            data_lines: list[str] = []
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line == "" and data_lines:
                    self._emit_event("\n".join(data_lines), sent_message)
                    data_lines = []
            if data_lines:
                self._emit_event("\n".join(data_lines), sent_message)
        else:
            body = resp.read().decode("utf-8", "replace").strip()
            if body:
                self._emit_event(body, sent_message)

    def _emit_event(self, payload: str, sent_message) -> None:
        try:
            parsed = json.loads(payload)
        except ValueError:
            _debug("dropping non-JSON event payload")
            return
        self._remember_protocol_version(parsed, sent_message)
        _write_out(json.dumps(parsed, separators=(",", ":")))

    def _remember_protocol_version(self, parsed, sent_message) -> None:
        """After a successful initialize, echo the negotiated version."""
        if (
            isinstance(sent_message, dict)
            and sent_message.get("method") == "initialize"
            and isinstance(parsed, dict)
            and isinstance(parsed.get("result"), dict)
        ):
            version = parsed["result"].get("protocolVersion")
            if isinstance(version, str):
                self.protocol_version = version
                _debug("negotiated protocol version: " + version)

    def _relay_http_error(self, err: urllib.error.HTTPError, request_id) -> None:
        self._capture_session(err.headers)
        body = ""
        try:
            body = err.read().decode("utf-8", "replace").strip()
        except Exception:
            pass
        # If the server answered with a JSON-RPC error document, relay it.
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("jsonrpc") == "2.0":
                _write_out(json.dumps(parsed, separators=(",", ":")))
                return
        except ValueError:
            pass
        if request_id is not None:
            self._emit_error(request_id, -32603,
                             "HTTP %d from %s" % (err.code, self.endpoint))
        _debug("HTTP %d: %s" % (err.code, body[:200]))

    def _emit_error(self, request_id, code: int, message: str) -> None:
        _write_out(json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }, separators=(",", ":")))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="moltline-mcp",
        description="stdio bridge to the Moltline Studio hosted MCP fleet",
        epilog="Servers: " + ", ".join(SERVERS),
    )
    parser.add_argument("server", nargs="?", default="catalog",
                        help="Moltline server slug (default: catalog)")
    parser.add_argument("--list", action="store_true",
                        help="list the available server slugs and exit")
    parser.add_argument("--timeout", type=float,
                        default=float(os.environ.get("MOLTLINE_TIMEOUT", "300")),
                        help="per-request timeout in seconds (default: 300)")
    parser.add_argument("--version", action="version",
                        version="moltline-mcp " + __version__)
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(SERVERS))
        return 0

    if args.server not in SERVERS:
        parser.error(
            "unknown server %r - expected one of: %s"
            % (args.server, ", ".join(SERVERS))
        )

    base_url = os.environ.get("MOLTLINE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    bridge = Bridge(endpoint="%s/%s" % (base_url, args.server),
                    timeout=args.timeout)
    _debug("bridging stdio <-> " + bridge.endpoint)

    # Exit promptly and quietly on Ctrl-C / SIGTERM.
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    except (OSError, ValueError):
        pass  # not available on some platforms / non-main threads

    threads: list[threading.Thread] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        worker = threading.Thread(target=bridge.forward, args=(line,), daemon=True)
        worker.start()
        threads.append(worker)
        threads = [t for t in threads if t.is_alive()]

    for t in threads:  # let in-flight requests finish before exiting
        t.join(timeout=args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
