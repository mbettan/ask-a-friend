#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="$REPO_DIR/skills/ask-a-friend"
RULE_SRC="$REPO_DIR/rules/ask-a-friend-activate.md"
FORCE="${1:-}"

BEGIN="# DO NOT EDIT: BEGIN ASK-A-FRIEND SKILL"
END="# DO NOT EDIT: END ASK-A-FRIEND SKILL"

log() { echo "[ask-a-friend] $*"; }

# --- idempotent injection (marker-fenced, surgical replace) ---
inject() {
  local f="$1" src="$2"
  mkdir -p "$(dirname "$f")"; [ -f "$f" ] || touch "$f"
  if grep -qF "$BEGIN" "$f"; then
    local tmp; tmp=$(mktemp)
    sed "/$BEGIN/,/$END/d" "$f" > "$tmp" && mv "$tmp" "$f"
  fi
  { echo "$BEGIN"; cat "$src"; echo "$END"; } >> "$f"
  log "injected → $f"
}

# --- env path resolution (CLI > env > default) ---
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CFG_DIR="$HOME/.config/ask-a-friend"
mkdir -p "$CFG_DIR"

# --- graceful, per-host degradation ---
log "Detecting hosts..."

# Claude Code
if command -v claude &>/dev/null || [ -d "$CLAUDE_DIR" ]; then
  log "Claude Code detected."
  mkdir -p "$CLAUDE_DIR/skills/ask-a-friend"
  cp -r "$SKILL_SRC/." "$CLAUDE_DIR/skills/ask-a-friend/"
  inject "$CLAUDE_DIR/CLAUDE.md" "$RULE_SRC"

  # hooks
  mkdir -p "$CLAUDE_DIR/hooks"
  cp "$REPO_DIR/hooks/session-start.js" "$CLAUDE_DIR/hooks/"
  cp "$REPO_DIR/hooks/ask-friend-statusline.sh" "$CLAUDE_DIR/hooks/"
  cp "$REPO_DIR/hooks/package.json" "$CLAUDE_DIR/hooks/"   # pins type:commonjs
  node "$REPO_DIR/hooks/session-start.js" --patch-settings "$CLAUDE_DIR/settings.json" || \
    log "WARN: settings patch skipped (node missing?)"
else
  log "Claude Code not found. Skipping."
fi

# Cursor
if [ -d "$HOME/.cursor" ] || [ -d ".cursor" ]; then
  log "Cursor detected."
  mkdir -p ".cursor/rules"
  { echo "---"; echo "alwaysApply: true"; echo "---"; cat "$RULE_SRC"; } > ".cursor/rules/ask-a-friend.mdc"
fi

# Windsurf
if [ -d "$HOME/.windsurf" ] || [ -d ".windsurf" ]; then
  log "Windsurf detected."
  mkdir -p ".windsurf/rules"
  { echo "---"; echo "trigger: always_on"; echo "---"; cat "$RULE_SRC"; } > ".windsurf/rules/ask-a-friend.md"
fi

# Copilot
if [ -d ".github" ]; then
  log "Copilot (.github) detected."
  inject ".github/copilot-instructions.md" "$RULE_SRC"
fi

# OpenClaw gateway
if command -v openclaw &>/dev/null || [ -d "$HOME/.openclaw" ]; then
  log "OpenClaw detected."
  WS="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
  mkdir -p "$WS"
  inject "$WS/AGENTS.md" "$RULE_SRC"
  echo "- ask_a_friend: consult Agent Platform model. See skills/ask-a-friend." >> "$WS/TOOLS.md"
fi

# --- write default config if absent ---
if [ ! -f "$CFG_DIR/config.json" ]; then
  cat > "$CFG_DIR/config.json" <<'JSON'
{
  "vertex_project": "your-gcp-project-id",
  "vertex_location": "global",
  "default_model": "claude-sonnet-4-6",
  "require_approval": true,
  "cost_cap_usd": 5.0,
  "cost_cap_mode": "warn",
  "use_cache": true,
  "custom_endpoint": "",
  "max_retries": 3,
  "timeout_ms": 30000
}
JSON
  log "wrote default config → $CFG_DIR/config.json"
fi

# --- graceful dependency check ---
log "Validating ask-a-friend dependencies..."
if ! command -v python3 &> /dev/null; then
  log "WARN: Python 3 not detected. Python scripts fallback might be required."
else
  if ! python3 -c "import google.auth" &> /dev/null; then
    log "WARN: python module 'google-auth' is missing. Run: pip install google-auth"
  fi
fi

log "Done. Friend ready. Try: /ask why is this leaking?"
[ "$FORCE" = "--force" ] && log "(forced reinstall)"
exit 0
