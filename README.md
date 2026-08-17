# moltline-mcp

A thin, dependency-free **stdio bridge** to [Moltline Studio](https://moltlinestudio.com)'s fleet of **14 hosted MCP servers**.

Most modern MCP clients can connect to the fleet **directly over Streamable HTTP** — no install needed (see [Direct connection](#direct-connection-preferred) below). This bridge exists for clients that only speak the stdio transport: it proxies newline-delimited JSON-RPC between your client and the hosted server, verbatim, with no telemetry and no dependencies beyond the Python 3.9+ standard library.

- Free tier: **no registration, no account, no credentials** — connect and call tools immediately.
- Premium tools are unlocked with a Moltline license, presented **only as a tool argument** (never in URLs or headers). See [auth.md](https://moltlinestudio.com/auth.md).
- Fleet is independently audited: **MCPize Verified A** on direct endpoints.

## The fleet

| Server | Tools | What it does |
|---|---|---|
| `catalog` | 10 | Search and browse the Moltline catalog: 138 skill bundles and all 14 servers. |
| `codereview` | 7 | Code review helpers: diff checklists, smell checks, review summaries. |
| `timeops` | 5 | Time operations: business days, meeting overlap, recurrence, deadlines, SLA due dates. |
| `data` | 7 | Data transforms: parsing, conversion, cleanup, and formatting utilities. |
| `business` | 8 | Small-business operations: invoices, follow-ups, everyday workflows. |
| `creator` | 8 | Content creation: hooks, outlines, captions, repurposing. |
| `educator` | 7 | Education: lesson planning, quizzes, and study aids. |
| `govern` | 7 | Governance checks: policy, compliance, and review gates. |
| `humanizer` | 5 | Text humanizing: tone, clarity, natural rewrites. |
| `merchant` | 6 | Commerce: product copy, listings, storefront helpers. |
| `outbound` | 8 | Outreach: sequences, personalization, reply drafting. |
| `personal` | 9 | Personal productivity: planning, routines, life admin. |
| `research` | 8 | Research: citations, summaries, source organization. |
| `skillmd-lint` | 6 | SKILL.md linting: validate and improve agent skill files. |

Machine-readable discovery: [api-catalog](https://moltlinestudio.com/.well-known/api-catalog) · per-server card at `https://mcp.moltlinestudio.com/<server>/.well-known/mcp/server-card.json` · [fleet health](https://mcp.moltlinestudio.com/health).

## Direct connection (preferred)

If your MCP client supports Streamable HTTP (Claude Desktop, Claude Code, Cursor, and most current clients do), point it straight at the hosted endpoint — nothing to install:

```json
{
  "mcpServers": {
    "moltline-timeops": {
      "type": "http",
      "url": "https://mcp.moltlinestudio.com/timeops"
    }
  }
}
```

Swap `timeops` for any slug in the table above.

## The stdio bridge (for stdio-only clients)

### Install

```bash
pip install moltline-mcp        # from PyPI, or:
pipx install moltline-mcp       # isolated install
```

Or run it straight from a checkout — it is a single stdlib-only file:

```bash
python3 moltline_mcp.py timeops
```

### Client configuration

```json
{
  "mcpServers": {
    "moltline-timeops": {
      "command": "moltline-mcp",
      "args": ["timeops"]
    }
  }
}
```

### CLI

```text
moltline-mcp [server] [--timeout SECONDS] [--list] [--version]
```

- `server` — one of the 14 slugs (default `catalog`); anything else fails fast with the valid list.
- `--timeout` — per-request timeout in seconds (default 300, or env `MOLTLINE_TIMEOUT`).
- `--list` — print the server slugs and exit.
- Env `MOLTLINE_BASE_URL` — override the fleet base URL (for testing).
- Env `MOLTLINE_DEBUG=1` — diagnostic logging on stderr (stdout stays protocol-clean).

## How it works

One process per server connection. Each JSON-RPC message read from stdin is POSTed to `https://mcp.moltlinestudio.com/<server>`; JSON and SSE-framed responses are relayed back to stdout as newline-delimited JSON. The bridge tracks the server-assigned `Mcp-Session-Id` and echoes the negotiated `MCP-Protocol-Version`, per the [Streamable HTTP transport spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports). It never inspects, stores, or reports your traffic.

## Access and licensing

- **Free tier** — anonymous. No registration or credentials; all free tools work immediately.
- **Premium** — unlocked with a Moltline license purchased (human-in-the-loop) at [moltlinestudio.com](https://moltlinestudio.com/). The license is passed as a tool argument where a premium tool asks for it — never as a bearer header, never in URLs. Details: [auth.md](https://moltlinestudio.com/auth.md).

## Links

- Website: https://moltlinestudio.com
- Agent access guide: https://moltlinestudio.com/auth.md
- API catalog: https://moltlinestudio.com/.well-known/api-catalog
- Community: https://community.moltlinestudio.com
- Issues and security reports: see [SECURITY.md](SECURITY.md)

## License

[MIT](LICENSE) © 2026 Moltline Studio
