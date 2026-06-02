---
name: ask-a-friend
description: Ask another model (Google, 3P, or custom) for scoped help via Agent Platform. Triggers on /ask-friend, "ask a friend", "get second opinion", or auto after N retries.
alwaysApply: false
allowed-tools:
  - ask_a_friend
---

# Ask a Friend

Stuck? Ask smarter friend. One tool call. Friend answers terse.

## When to call

- Hard bug after 2 tries → ask_a_friend.
- Architecture/design decision → ask_a_friend with `task_type="spec_critique"`.
- Alternate solution drafting → ask_a_friend with `task_type="second_opinion"`.
- Code review → ask_a_friend with `task_type="code_review"`.
- Security audit → ask_a_friend with `task_type="security_audit"`.

## Tool Schema

The core tool `ask_a_friend` takes:
- `task_type`: Determines auto-routing and system instructions.
- `prompt`: Detailed query or question.
- `context`: Relevant code snippet or logs.
- `friend_model`: Specific model or alias. Default "auto" will resolve via routing table.
- `require_approval`: HIL gate (human-in-the-loop). Default is true.
- `use_cache`: Cache queries to prevent duplicate spend. Default is true.
- `max_tokens`: Token response limit. Default is 1024.

## Auto-Routing Table

When `friend_model='auto'`, routes by `task_type` to the strongest model:
- `code_review` → `claude-garden` (strong code reasoning)
- `build_tests` → `gemini-pro` (fast, cheap, structured)
- `second_opinion` → `gemini-pro` (default general)
- `security_audit` → `claude-garden` (careful, conservative)
- `spec_critique` → `gpt-garden` (broad critique)

## Friend Response Style

Friend answers terse: drop filler, code exact, [thing][action][reason].
See refs/brevity.md.

## Cost Guardrail

Each ask is logged to telemetry database. Rolling 5h cost cap prevents runaway loops.

## Load on demand

- Model catalog → read refs/models.md
- Setup/auth → read refs/setup.md
  Do NOT read refs until needed.
