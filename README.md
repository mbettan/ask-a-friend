<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/speech-balloon_1f4ac.png" width="120" />
</p>

<h1 align="center">Ask a Friend</h1>

<p align="center">
  <strong>why get stuck when specialized friend can help?</strong>
</p>

<p align="center">
  <a href="https://github.com/mbettan/ask-a-friend/stargazers"><img src="https://img.shields.io/github/stars/mbettan/ask-a-friend?style=flat&color=yellow" alt="Stars"></a>
  <a href="https://github.com/mbettan/ask-a-friend/commits/main"><img src="https://img.shields.io/github/last-commit/mbettan/ask-a-friend?style=flat" alt="Last Commit"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/mbettan/ask-a-friend?style=flat" alt="License"></a>
</p>

<p align="center">
  <a href="#before--after">before/after</a> •
  <a href="#install">install</a> •
  <a href="#setup">setup</a> •
  <a href="#what-you-get">what you get</a> •
  <a href="#telemetry-dashboard">telemetry dashboard</a> •
  <a href="#how-it-works">how it works</a>
</p>

---

An autonomous agent plugin and local CLI that lets your coding agent phone a specialized AI friend when stuck. Built with native client-side PII scrubbing, SHA-256 prompt caching, and rolling SQLite cost guardrails to keep agentic workflows secure, fast, and cheap.

> [!NOTE]
> This skill is built on a fork of the excellent [caveman](https://github.com/JuliusBrussee/caveman.git) project. We reuse its robust multi-agent installation hooks and statusline patterns to deliver broad IDE compatibility.

## Before / after

<table>
<tr>
<td width="50%">

### 🗣️ Raw agent call (vulnerable and expensive)

> Agent sends raw contexts, absolute paths, and sensitive credentials straight to external LLMs. Runaway recursive loops can generate massive, unexpected API bills:
> * 🔓 Raw credentials (`sk-...`, `Bearer ...`) sent in plain text
> * 💸 No spending controls; recursive loops run up bills unchecked
> * ⌛ Identical prompts re-sent over the wire during rapid iterations

</td>
<td width="50%">

### 🔒 Secure ask-a-friend call (sanitized and cached)

> A dedicated security proxy interceptor scrubs payload identifiers pre-transit, bypasses duplicate queries locally, and enforces strict spend bounds:
> * 🛡️ **PII scrubbing** out-of-band; secrets replaced with safe placeholders
> * 🛑 **cost breaker** automatically halts runaway recursive loops
> * ⚡ **SHA-256 cache** returns duplicate queries instantly (~1ms)

</td>
</tr>
</table>

**Specialized peer routing. Secure transit. Zero runaway spend.**

```
┌────────────────────────────────────────┐
│  out-of-band PII scrubbing  ██████ 100%│
│  duplicate cache latency   ██████ ~1ms│
│  rolling spend breakers    ██████ SQLite│
│  auto-routing engine       ██████ auto │
└────────────────────────────────────────┘
```

## Install

One command. Auto-detects and configures Claude Code, Cursor, Windsurf, Copilot, and OpenClaw workspaces.

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/mbettan/ask-a-friend/main/hooks/install.sh | bash

# Windows (PowerShell 5.1+)
irm https://raw.githubusercontent.com/mbettan/ask-a-friend/main/hooks/install.ps1 | iex
```

*Takes ~30 seconds. Requires Node ≥ 18 and Python 3. Safe to re-run.*

## Setup

### 1. Google Cloud authentication
Authenticate your local machine to Google Cloud to access your Agent Platform or Vertex AI backend:
```bash
gcloud auth application-default login
```

### 2. Configure your GCP project ID
You can configure your project ID using either environment variables or a persistent config file:

#### Option A: Environment variables (recommended for CLI / scripts)
Add this to your shell profile (e.g., `~/.zshrc` or `~/.bashrc`):
```bash
export AGENT_PLATFORM_PROJECT_ID="your-gcp-project-id"
# Optionally: export AGENT_PLATFORM_LOCATION="global"
```

#### Option B: Configuration file (recommended for persistent IDE plugins)
Modify your local configuration file at `~/.config/ask-a-friend/config.json` (created automatically during install):
```json
{
  "vertex_project": "your-gcp-project-id",
  "vertex_location": "global",
  "cost_cap_usd": 5.00,
  "require_approval": true
}
```

## Use

Once installed, your agent can call a friend through conversational triggers or explicit tool executions:

```text
/ask-friend review src/auth.ts
"ask a friend: why is this database query locking?"
ask_a_friend @friend:claude "perform a security audit on this endpoint"
```

## What you get

| Capability | CLI / script command | Description |
|---|---|---|
| **Specialized peer routing** | `ask_a_friend` tool | Automatically routes queries: `code_review` dispatches to `claude-garden`, while test structures run on fast, cost-efficient `gemini-pro`. |
| **PII interceptor** | `scripts/pii.py` | Pre-transit client-side regex scrubber that strips API keys, Bearer authorization tokens, email addresses, and absolute system usernames. |
| **Circuit breaker** | `scripts/cost.py` | SQLite-backed telemetry tracking rolling session expenses over a sliding 5h window to alert or hard-block recursive loops. |
| **Prompt caching** | `scripts/cache.py` | Prompts and contexts are hashed via SHA-256 to resolve repeated iterations locally under 1ms. |
| **CLI dashboard** | `python3 scripts/stats.py` | Command-center budget gauges showing exact rolling token spending, model breakdown metrics, and recent transaction history logs. |

## Telemetry dashboard

Every request (successes, warnings, and quota errors) is logged to `~/.ask-friend/telemetry.db`. You can launch a beautiful, live-updating glassmorphic telemetry dashboard server by running:

```bash
python3 scripts/dashboard.py
```

*Once launched, navigate to **http://localhost:8080** to inspect live spend metrics, cache hit rates, and transaction details.*

## How it works

```mermaid
sequenceDiagram
    autonumber
    participant Agent as coding agent
    participant Inbound as PII scrubber interceptor
    participant Cache as cache/cost guard
    participant Platform as Agent Platform / Vertex AI
    
    Agent->>Inbound: /ask-friend payload (sensitive strings included)
    Note over Inbound: client-side regex scrub.<br/>replaces keys/emails with placeholders.
    Inbound->>Cache: safe payload + out-of-band rehydrate maps
    Note over Cache: hashes query. checks SQLite 5h cap.<br/>bypasses network if cached.
    Cache->>Platform: dispatches sanitized query to Claude/Gemini
    Platform-->>Cache: returns terse answer
    Note over Cache: stores output in local cache & DB
    Cache-->>Inbound: terse answer payload
    Note over Inbound: injects real identifiers locally<br/>(rehydration)
    Inbound-->>Agent: clean, exact, safe response
```

1. **Trigger hook**: Fired dynamically when your agent encounters a bug after 2 retries, or when explicitly queried by the user.
2. **Pre-transit scrubber**: Interceptor identifies potential secrets, email addresses, and local directories, substituting them with mapping tokens (`[APIKEY_1]`).
3. **Cost and cache check**: Prompt SHA-256 signatures are evaluated. Rolling 5-hour budgets are queried in SQLite. If clean, it dispatches to the strongest model.
4. **Out-of-band rehydration**: The answer is returned to the client-side interceptor, which maps placeholders back to raw identifiers.
5. **Safe presentation**: The agent receives the technically exact, terse response securely.

## License

Apache License 2.0 — free and open-source.
