# PRD: "Ask a Friend" Skill

**Status:** Draft v1.0
**Owner:** Product — LLM Skills
**Last Updated:** June 2026

---

## 1. Summary

"Ask a Friend" is a cross-agent LLM skill that lets a host model (Claude Code, Cursor, Gemini CLI, etc.) make an authenticated API call to **Google Agent Platform (Vertex AI)** to request a second opinion from another model — Google models (Gemini), third-party models (Anthropic, OpenAI via Model Garden), or custom-deployed endpoints.

Pattern: `[host stuck/wants verification] → [calls friend] → [gets focused answer] → [host integrates]`.

Use cases: code review, test generation, alternate solution drafting, security audit, "rubber duck" second opinion.

---

## 2. Problem

Single-model agents fail silently on blind spots: hard bugs, weak test coverage, model-specific reasoning gaps. No clean primitive exists to delegate a _scoped_ sub-question to a _different_ model without manual copy-paste between tools.

Existing multi-model routing (per Doc 2) sits in heavyweight orchestration engines. Developers want a lightweight, installable skill — not a framework migration.

---

## 3. Goals / Non-Goals

**Goals**

- One installable skill, works across all major agents (per Doc 1 injection matrix).
- Single declarative tool: `ask_a_friend`.
- Route to Vertex AI Agent Platform; support Google / 3P / custom models.
- Scoped, token-efficient calls (progressive disclosure, no context flooding).
- Secure credential handling — keys never enter model context.

**Non-Goals**

- Not a full agent orchestrator (no chains, no worktrees).
- No autonomous multi-turn debate loops (v1 = single round-trip).
- No model training / fine-tuning.

---

## 4. Users & Use Cases

| Use Case       | Trigger                            | Friend Task                |
| -------------- | ---------------------------------- | -------------------------- |
| Code review    | `/ask-friend review src/auth.ts`   | Find bugs, security issues |
| Test building  | `/ask-friend tests for payment.py` | Generate test cases        |
| Second opinion | Host stuck after N retries         | Alternate solution         |
| Security audit | Pre-merge gate                     | Vuln scan + remediation    |
| Spec critique  | Design phase                       | Poke holes in approach     |

---

## 5. Architecture

```
┌──────────────────┐   ask_a_friend()   ┌─────────────────────────┐
│  Host Agent      │ ─────────────────▶ │  Skill Proxy (local)     │
│ (Claude/Cursor)  │                    │  - resolve credentials   │
└──────────────────┘                    │  - build Vertex payload  │
         ▲                              │  - taint-redact PII      │
         │ scoped answer                └───────────┬─────────────┘
         │                                          │ JSON-RPC / REST
         │                              ┌───────────▼─────────────┐
         │                              │  Vertex AI Agent Platform│
         │                              │  ┌─────────┬───────────┐ │
         └──────────────────────────────│  │ Gemini  │ 3P / Garden│ │
                                        │  │         │ Custom EP │ │
                                        │  └─────────┴───────────┘ │
                                        └─────────────────────────┘
```

The skill ships a thin local proxy (per Doc 1 MCP middleware pattern) that handles auth, payload shaping, and PII redaction before the request leaves the host.

---

## 6. Tool Schema

Follows Doc 2 schema rules: `snake_case`, ≤7 params, enums, strict required/optional split.

```yaml
---
name: ask_a_friend
description: Request a scoped second opinion from another model via Vertex AI.
alwaysApply: false
allowed-tools:
  - ask_a_friend
---
```

```json
{
  "name": "ask_a_friend",
  "description": "Ask another model (Google, 3P, or custom) for help on a scoped task.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "task_type": {
        "type": "string",
        "enum": [
          "code_review",
          "build_tests",
          "second_opinion",
          "security_audit",
          "spec_critique"
        ]
      },
      "prompt": {
        "type": "string",
        "description": "Scoped question. No filler."
      },
      "context": {
        "type": "string",
        "description": "Relevant code/text. Pre-trimmed by host."
      },
      "friend_model": {
        "type": "string",
        "enum": ["gemini-pro", "claude-garden", "gpt-garden", "custom_endpoint"],
        "description": "Automatically translates. gemini-pro translates to gemini-3.5-flash, claude-garden to claude-sonnet-4-6."
      },
      "max_tokens": { "type": "integer" }
    },
    "required": ["task_type", "prompt"]
  }
}
```

---

## 7. Configuration

Resolution hierarchy (per Doc 1): CLI flags > env vars > local config > defaults.

```bash
# Env vars (keys never in model context)
export ASK_FRIEND_VERTEX_PROJECT="my-project"
export ASK_FRIEND_VERTEX_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="~/.ask-friend/sa.json"  # ADC
export ASK_FRIEND_DEFAULT_MODEL="gemini-pro"
```

```json
// ~/.ask-friend/config.json
{
  "default_model": "gemini-pro",
  "vertex_project": "your-gcp-project-id",
  "vertex_location": "global",
  "custom_endpoint": "projects/x/locations/us-central1/endpoints/123",
  "max_retries": 3,
  "timeout_ms": 30000
}
```

### 7.1 Model and Endpoint Resolution Rules

- **Model Version Constraints**: Version `2.5` and `1.5` Gemini models are forbidden and unavailable on the global endpoint. `gemini-pro` and `gemini-flash` map strictly to `gemini-3.5-flash`. `claude-garden` maps directly to Model Garden's `claude-sonnet-4-6`.
- **Global Endpoint Hostname routing**: If location is configured as `global`, the REST API endpoint domain resolves strictly to `aiplatform.googleapis.com` (omitting any prepended location prefixes). For standard regional locations (e.g. `us-central1`), the system routes to `{location}-aiplatform.googleapis.com`.

---

## 8. Installation

Cross-agent (per Doc 1 patterns):

```bash
# Auto-detect agent
npx skills add yourorg/ask-a-friend

# Specific agents
npx skills add yourorg/ask-a-friend -a cursor
npx skills add yourorg/ask-a-friend -a windsurf
npx skills add yourorg/ask-a-friend -a github-copilot

# Claude Code plugin
claude plugin marketplace add yourorg/ask-a-friend && claude plugin install ask-a-friend@ask-a-friend

# Gemini CLI
gemini extensions install https://github.com/yourorg/ask-a-friend
```

Idempotent install via marker fences (per Doc 1):

```bash
# DO NOT EDIT: BEGIN ASK-A-FRIEND SKILL
# ... rules ...
# DO NOT EDIT: END ASK-A-FRIEND SKILL
```

---

## 9. Security (per Doc 2)

- **Auth:** OAuth 2.0 / ADC service accounts. Credentials resolved out-of-band by local proxy. **Never** placed in model context.
- **PII redaction:** Client-side tokenization before sending to Vertex; rehydrate on return.
- **Taint tracking:** Redact secrets/keys detected in `context` before transmit.
- **Least privilege:** SA scoped to `aiplatform.endpoints.predict` only.
- **Token segregation:** Vertex tokens never shared with host agent or other tools.
- **Loop ceiling:** Max 3 friend calls per host task (prevents runaway cost).

---

## 10. Exception Handling (per Doc 2)

Mask raw errors. Return remediation-oriented plain text.

| Error             | Returned to Host                                                     |
| ----------------- | -------------------------------------------------------------------- |
| Auth fail         | "Vertex auth failed. Check GOOGLE_APPLICATION_CREDENTIALS."          |
| Model unavailable | "Friend model gemini-pro unavailable. Retry or switch friend_model." |
| Timeout           | "Friend timed out (30s). Reduce context size and retry."             |
| Quota             | "Vertex quota hit. Wait or reduce call rate."                        |
| Bad endpoint      | "custom_endpoint invalid. Verify config.json path."                  |

---

## 11. Token Efficiency (per Docs 1 & 2)

- Host **pre-trims** context — no raw file dumps.
- Friend instructed via brevity protocol: dense, code-exact, no filler.
- Structured return: `{verdict, findings[], suggested_diff}`.
- Lazy-load reference templates only when needed.
- Friend response format mirrors `caveman-review`:

```
L42: 🔴 bug: user null after .find(). Guard before .email.
L88: 🔵 nit: 50-line fn. Extract validate/normalize/persist.
```

---

## 12. Telemetry & Logging

Log each call (including successful requests and detailed error states) to the local SQLite telemetry database (`~/.ask-friend/telemetry.db`). The schema includes:

- `ts` (Timestamp)
- `model` (Model class used)
- `task` (Task type requested)
- `in_tok` (Input tokens, 0 on error)
- `out_tok` (Output tokens, 0 on error)
- `cost` (Computed rolling cost, 0.0 on error)
- `status` (`SUCCESS` or `ERROR` indicator)
- `error_reason` (Exact exception message or HTTP API error detail on failure)

### UI visualization and self-healing migrations:
- **Self-Healing Schema Migration**: The connection pool automatically inspects the DB and performs live in-place alterations to append `status` and `error_reason` columns seamlessly without destroying legacy telemetry.
- **Dashboard Integration**: Errors are cleanly visualised in a premium web dashboard (`dashboard.py`) using red status pills and containing native browser tooltip explanations of the error.
- **Cost Calculation exclusion**: Any call logged as `ERROR` is omitted from Rolling spend calculations to guarantee accuracy.

Cost formula for successful calls:

```
Cost = (in_tokens × in_rate + out_tokens × out_rate) / 1_000_000
```

---

## 13. Success Metrics

| Metric                                  | Target  |
| --------------------------------------- | ------- |
| Install → first call                    | < 5 min |
| Friend call success rate                | > 97%   |
| Median round-trip latency               | < 8s    |
| Context flooding incidents              | 0       |
| Credential leak incidents               | 0       |
| Avg tokens saved vs copy-paste workflow | > 40%   |

---

## 14. Phasing

- **v1:** Single round-trip, 5 task types, Gemini + custom endpoints, SQLite telemetry.
- **v1.1:** 3P Model Garden (Claude/GPT), tag-based model routing.
- **v2:** Multi-friend parallel polling, consensus verdict, async callbacks.

---

## 15. Architectural Decisions & Resolutions

1. **Default Model Resolution**: Auto-routes dynamically based on the `task_type` payload property using a local routing map (e.g., `code_review` dispatches to Claude-based model, `build_tests` maps to fast Gemini-based model).
2. **Human-In-The-Loop (HIL) Gate**: Integrated a native approval hook (`require_approval: true`) prompting standard input validation before executing GCP network calls. This parameter can be customized persistently inside the user configuration file.
3. **Cost Guardrails Mode**: Implemented granular budget breakers over a 5-hour sliding window. Hitting the spending limits warns or hard-blocks further executions depending on the configured `cost_cap_mode` ("warn" or "hard").
4. **Query Caching Engine**: Built a prompt and context caching mechanism. Payload signatures are hashed using SHA-256 to fetch duplicate inquiries locally under 1ms and completely eliminate repetitive external API expenses.

