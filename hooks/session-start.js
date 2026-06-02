#!/usr/bin/env node
// Runs once per session start. Silent-fails on all errors. Never blocks.
const fs = require("fs");
const path = require("path");

const CFG_DIR = path.join(
  process.env.HOME || process.env.USERPROFILE,
  ".config",
  "ask-a-friend",
);
const FLAG = path.join(CFG_DIR, ".active");

function safeWrite(p, content) {
  try {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    const fd = fs.openSync(p, "w", 0o600);
    fs.writeSync(fd, content);
    fs.closeSync(fd);
  } catch (_) {}
}

function resolveDefault() {
  if (process.env.ASK_FRIEND_DEFAULT) return process.env.ASK_FRIEND_DEFAULT;
  try {
    const c = JSON.parse(
      fs.readFileSync(path.join(CFG_DIR, "config.json"), "utf8"),
    );
    return c.default || "gemini-2.5-pro";
  } catch (_) {
    return "gemini-2.5-pro";
  }
}

// --- patch settings.json mode (installer) ---
if (process.argv[2] === "--patch-settings") {
  const sp = process.argv[3];
  let s = {};
  try {
    s = JSON.parse(fs.readFileSync(sp, "utf8"));
  } catch (_) {}
  s.hooks = s.hooks || {};
  const h = (e) => `node ~/.claude/hooks/session-start.js --event ${e}`;
  s.hooks.onSessionStart = h("SessionStart");
  s.hooks.onSessionExit = h("SessionExit");
  s.statusLine = s.statusLine || {
    type: "command",
    command: "bash ~/.claude/hooks/ask-friend-statusline.sh",
  };
  safeWrite(sp, JSON.stringify(s, null, 2));
  process.exit(0);
}

// --- session start: write flag + emit ruleset as hidden system context ---
const def = resolveDefault();
if (def !== "off") {
  safeWrite(FLAG, def);
  // Claude Code injects SessionStart stdout as hidden system context
  process.stdout.write(
    `ask_a_friend tool available. Default friend: ${def}. ` +
      `Stuck >2 tries → call ask_a_friend. Friend answers terse. Off: "solo mode".\n`,
  );
}
