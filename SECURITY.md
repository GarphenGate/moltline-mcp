# Security Policy

## Supported versions

The latest release of `moltline-mcp` is supported.

## Reporting a vulnerability

Please email **support@moltlinestudio.com** with a description of the issue,
reproduction steps, and impact. We aim to acknowledge reports within 72 hours.
Please do not open public issues for security-sensitive reports.

## Scope notes

- This bridge is a thin transport proxy: it forwards JSON-RPC between your
  MCP client and `https://mcp.moltlinestudio.com/<server>` verbatim, over TLS,
  and stores nothing.
- It sends no telemetry and requires no credentials. Moltline licenses are
  passed as tool arguments by your client, never by this bridge itself, and
  never appear in URLs or headers.
- Reports about the hosted fleet (mcp.moltlinestudio.com) are also welcome at
  the same address.
