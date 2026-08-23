# moltline-mcp

A thin, dependency-free **stdio bridge** to [Moltline Studio](https://moltlinestudio.com)'s fleet of **19 hosted MCP servers**.

Most modern MCP clients can connect to the fleet **directly over Streamable HTTP** — no install needed (see [Direct connection](#direct-connection-preferred) below). This bridge exists for clients that only speak the stdio transport: it proxies newline-delimited JSON-RPC between your client and the hosted server, verbatim, with no telemetry and no dependencies beyond the Python 3.9+ standard library.

- **132 tools across 19 servers; 92 are free.**
- Free tier: **no registration, no account, no credentials** — connect and call tools immediately.
- Premium tools are unlocked with a Moltline license. Set `MOLTLINE_LICENSE` in your MCP client's environment; the bridge sends it as the `X-Moltline-License` header and never writes it to argv, URLs or logs. See [auth.md](https://moltlinestudio.com/auth.md).
- Fleet is independently audited: **MCPize Verified A** on direct endpoints.

**Find it on:** [Smithery](https://smithery.ai/servers/techdpr/moltline-catalog) · [MCPize](https://mcpize.com/mcp/moltline-catalog) · [Glama](https://glama.ai/mcp/servers/GarphenGate/moltline-mcp) · [Clawmart](https://clawmart.sh/l/3ShWAZ) · [MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=moltlinestudio)

## The fleet

| Server | Tools | What it does |
|---|---|---|
| `catalog` | 10 | Search 138 agent skills and personas by plain-language job; preview any product. |
| `codereview` | 7 | Risk-scan a diff, flag AI-generated-code tells, find secrets, report complexity. |
| `govern` | 8 | Audit an MCP config or SKILL.md for over-broad scope and prompt-injection risk. |
| `timeops` | 5 | Business days, meeting overlap, recurrence expansion, deadline and SLA math. |
| `data` | 7 | Paste-your-data analytics: CSV profiling, A/B tests, correlation, growth, cohorts. |
| `humanizer` | 5 | Find AI-isms with evidence, fingerprint a writing voice, measure burstiness. |
| `business` | 8 | 30 finance, bookkeeping, legal-ops and SMB operations persona-skill products. |
| `creator` | 8 | 20 blogging, brand-voice, copywriting, video and social persona-skill products. |
| `educator` | 7 | 8 curriculum, classroom, accommodations and exam-prep persona-skill products. |
| `outbound` | 8 | 7 outreach, sequencing, deliverability, call-coaching and CRM-hygiene products. |
| `personal` | 9 | 20 inbox, calendar, travel, meals and family-logistics persona-skill products. |
| `research` | 8 | 7 research navigation, thesis, note-taking and citation persona-skill products. |
| `skillmd-lint` | 6 | Lint a SKILL.md for frontmatter, structure, secrets and size. All tools free. |
| `merchant` | 6 | Commerce arithmetic: processor fees, charge-to-net, invoice totals, proration. |
| `shipping` | 6 | Dimensional weight, parcel fit, landed cost, freight class, rate cards. |
| `shopify` | 6 | Check a product CSV, URL handles, variant matrices and metafield keys. |
| `dropship` | 6 | Dropshipping unit economics: margin, lead time, SKU mapping, price ladders. |
| `recall` | 6 | A portable knowledge-graph memory you pass in and get back. No database. |
| `vision` | 6 | Image header probing, bbox conversion, resize plans, color and detection math. |

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

**Run directly (recommended)** — the bridge is a single stdlib-only file, so a
clone is all you need:

```bash
git clone https://github.com/GarphenGate/moltline-mcp.git
python3 moltline-mcp/moltline_mcp.py timeops   # any of the 19 slugs; default: catalog
```

**Docker** — see [Docker](#docker) below if you prefer a container.

A PyPI package is planned; until then, use the methods above.

### Client configuration

Point your MCP client at the script with an absolute path:

```json
{
  "mcpServers": {
    "moltline-timeops": {
      "command": "python3",
      "args": ["/absolute/path/to/moltline-mcp/moltline_mcp.py", "timeops"]
    }
  }
}
```

Or run it through Docker (after `docker build -t moltline-mcp .`):

```json
{
  "mcpServers": {
    "moltline-timeops": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "moltline-mcp", "timeops"]
    }
  }
}
```

### CLI

```text
python3 moltline_mcp.py [server] [--timeout SECONDS] [--list] [--version]
```

- `server` — one of the 19 slugs (default `catalog`); anything else fails fast with the valid list.
- `--timeout` — per-request timeout in seconds (default 300, or env `MOLTLINE_TIMEOUT`).
- `--list` — print the server slugs and exit.
- Env `MOLTLINE_BASE_URL` — override the fleet base URL (for testing).
- Env `MOLTLINE_LICENSE` — your Moltline license, sent as the `X-Moltline-License`
  header to unlock premium tools. Omit it and the bridge runs free-tier only.
- Env `MOLTLINE_DEBUG=1` — diagnostic logging on stderr (stdout stays protocol-clean).
  The license is never logged; debug output reports only whether one is configured.

## Docker

The bridge also runs containerized (stdio in, network egress to the fleet required):

```bash
docker build -t moltline-mcp .
docker run -i --rm moltline-mcp timeops   # any of the 19 slugs; default: catalog
```

See [Client configuration](#client-configuration) for the matching `mcpServers` entry.

## How it works

One process per server connection. Each JSON-RPC message read from stdin is POSTed to `https://mcp.moltlinestudio.com/<server>`; JSON and SSE-framed responses are relayed back to stdout as newline-delimited JSON. The bridge tracks the server-assigned `Mcp-Session-Id` and echoes the negotiated `MCP-Protocol-Version`, per the [Streamable HTTP transport spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports). It never inspects, stores, or reports your traffic.

## Tests

The bridge ships with an offline test suite - no network, no dependencies:

```bash
python -m unittest -v
```

Twenty-two tests cover the parts that actually break in a transport bridge:
newline-delimited framing, SSE event splitting (multiple events, multi-line
`data:` payloads, a trailing event with no blank line, comments and named
events), session-id capture and reuse, protocol-version negotiation on
`initialize` only, and error relay - a JSON-RPC error document is passed
through verbatim, anything else becomes a well-formed `-32603`. CI runs them
on Python 3.9, 3.12 and 3.13, plus a Docker build and container smoke test.

## Access and licensing

- **Free tier** — anonymous. No registration or credentials; all free tools work immediately.
- **Premium** — unlocked with a Moltline license purchased (human-in-the-loop) at [moltlinestudio.com](https://moltlinestudio.com/). Set `MOLTLINE_LICENSE` in the environment and the bridge forwards it as the `X-Moltline-License` request header. It is deliberately not a command-line flag: argv is world-readable through `ps`. It is never placed in a URL and never logged. Details: [auth.md](https://moltlinestudio.com/auth.md).

## Links

- Website: https://moltlinestudio.com
- Agent access guide: https://moltlinestudio.com/auth.md
- API catalog: https://moltlinestudio.com/.well-known/api-catalog
- Agent protocol reference (x402, AP2, ACP, UCP, MPP, A2A): https://moltlinestudio.com/protocols.html
- Community: https://community.moltlinestudio.com
- Issues and security reports: see [SECURITY.md](SECURITY.md)

## License

[MIT](LICENSE) © 2026 Moltline Studio
