#!/usr/bin/env bash
set -euo pipefail
BEGIN="# DO NOT EDIT: BEGIN ASK-A-FRIEND SKILL"
END="# DO NOT EDIT: END ASK-A-FRIEND SKILL"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

strip() {
  local f="$1"
  [ -f "$f" ] || return 0
  grep -qF "$BEGIN" "$f" || return 0
  local tmp; tmp=$(mktemp)
  sed "/$BEGIN/,/$END/d" "$f" > "$tmp"
  if [ -s "$tmp" ]; then mv "$tmp" "$f"; else rm -f "$tmp" "$f"; fi
  echo "[ask-a-friend] cleaned $f"
}

strip "$CLAUDE_DIR/CLAUDE.md"
strip ".github/copilot-instructions.md"
strip "${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}/AGENTS.md"
rm -rf "$CLAUDE_DIR/skills/ask-a-friend"
rm -f  "$CLAUDE_DIR/hooks/session-start.js" "$CLAUDE_DIR/hooks/ask-friend-statusline.sh"
rm -f  ".cursor/rules/ask-a-friend.mdc" ".windsurf/rules/ask-a-friend.md"
echo "[ask-a-friend] uninstalled. Config at ~/.config/ask-a-friend preserved."
