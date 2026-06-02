#!/usr/bin/env python3
import os
import sys

# Auto-bootstrap: Re-execute using the virtualenv python if it exists and we're not in it
venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python3")
if os.path.exists(venv_python) and sys.executable != venv_python and not os.getenv("ASK_FRIEND_IN_VENV"):
    os.environ["ASK_FRIEND_IN_VENV"] = "1"
    os.execv(venv_python, [venv_python] + sys.argv)

import json
import hashlib
from resolve_config import resolve_config
from pii import redact, rehydrate
from cost import check_cost_cap, log_call
from cache import cache_get, cache_set
from agent_platform import call_agent_platform

ROUTING = {
    "code_review": "claude-garden",
    "build_tests": "gemini-pro",
    "second_opinion": "gemini-pro",
    "security_audit": "claude-garden",
    "spec_critique": "gpt-garden",
}

def ask_a_friend(args):
    try:
        cfg = resolve_config()
    except Exception as e:
        return {"status": "error", "reason": f"Failed to resolve configuration: {e}"}

    task_type = args.get("task_type", "second_opinion")
    prompt = args.get("prompt", "")
    context = args.get("context", "")
    friend = args.get("friend_model")
    if not friend:
        friend = cfg.get("friend_model")
        if not friend or friend == "auto":
            friend = cfg.get("default_model", "auto")
    require_approval = args.get("require_approval", cfg.get("require_approval", True))
    use_cache = args.get("use_cache", cfg.get("use_cache", True))
    max_tokens = args.get("max_tokens", cfg.get("max_tokens", 1024))

    # Resolve auto-routing
    if friend == "auto":
        friend = ROUTING.get(task_type, "gemini-pro")

    # Generate Cache Key
    cache_key = hashlib.sha256(
        f"{friend}:{task_type}:{prompt}:{context}".encode("utf-8")
    ).hexdigest()

    # Cache check
    if use_cache:
        try:
            cached = cache_get(cache_key, cfg.get("cache_ttl_sec", 3600))
            if cached:
                return {"status": "ok", "cached": True, "friend": friend, "answer": cached}
        except Exception:
            pass

    # Cost cap pre-check
    try:
        cap_status = check_cost_cap(cfg.get("cost_cap_usd", 5.0), cfg.get("cost_cap_mode", "warn"))
        if cap_status == "blocked":
            return {
                "status": "error",
                "reason": f"Session cost cap ${cfg.get('cost_cap_usd', 5.0)} hit (hard mode). Reset or raise cap."
            }
    except Exception:
        cap_status = "ok"

    # HIL gate
    if require_approval:
        if not prompt_user_approval(friend, task_type, prompt):
            return {"status": "cancelled", "reason": "User declined friend call."}

    # PII redact before transmit
    try:
        safe_prompt, prompt_lookup = redact(prompt)
        safe_context, context_lookup = redact(context)
        lookup = {**prompt_lookup, **context_lookup}
    except Exception as e:
        safe_prompt, safe_context, lookup = prompt, context, {}

    # Call Agent Platform
    result = call_agent_platform(
        friend_model=friend,
        task_type=task_type,
        prompt=safe_prompt,
        context=safe_context,
        project_id=cfg.get("vertex_project"),
        location=cfg.get("vertex_location"),
        max_tokens=max_tokens,
        timeout_ms=cfg.get("timeout_ms", 30000),
        insecure_skip_verify=cfg.get("insecure_skip_verify", False),
    )

    if result.get("status") != "ok":
        try:
            log_call(friend, task_type, {}, status="ERROR", error_reason=result.get("reason"))
        except Exception:
            pass
        return result  # already masked plain-text

    # Rehydrate PII out-of-band
    try:
        answer = rehydrate(result["answer"], lookup)
    except Exception:
        answer = result["answer"]

    # Telemetry + cache (silent-fail)
    try:
        log_call(friend, task_type, result.get("usage", {}), status="SUCCESS")
    except Exception:
        pass

    if use_cache:
        try:
            cache_set(cache_key, answer)
        except Exception:
            pass

    if cap_status == "warn":
        answer += "\n\n⚠ Approaching session cost cap."

    return {"status": "ok", "cached": False, "friend": friend, "answer": answer}

def prompt_user_approval(friend, task_type, prompt):
    preview = prompt[:80].replace("\n", " ")
    sys.stderr.write(
        f"\n[ask-a-friend] Call {friend} for {task_type}? \"{preview}...\" [y/N]: "
    )
    sys.stderr.flush()
    try:
        # Read one line from stderr/stdin connection
        # We use sys.stdin because input() in python reads from stdin
        val = sys.stdin.readline().strip().lower()
        return val == "y"
    except Exception:
        return False

if __name__ == "__main__":
    # Read inputs from environment variable if set, otherwise fall back to stdin JSON payload
    payload_env = os.getenv("ASK_FRIEND_INPUT_PAYLOAD")
    if payload_env:
        try:
            args = json.loads(payload_env)
        except Exception as e:
            args = {}
            sys.stderr.write(f"Error parsing environment variable payload: {e}\n")
    else:
        try:
            raw = sys.stdin.read()
            args = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            args = {}
            sys.stderr.write(f"Error reading input from stdin: {e}\n")
    
    res = ask_a_friend(args)
    print(json.dumps(res))
