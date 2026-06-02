import os
import json

def resolve_config():
    defaults = {
        "vertex_project": os.getenv("ASK_FRIEND_AGENT_PLATFORM_PROJECT") or os.getenv("ASK_FRIEND_VERTEX_PROJECT") or "your-gcp-project-id",
        "vertex_location": os.getenv("ASK_FRIEND_AGENT_PLATFORM_LOCATION") or os.getenv("ASK_FRIEND_VERTEX_LOCATION") or "us-central1",
        "friend_model": "auto",
        "require_approval": True,
        "use_cache": True,
        "max_tokens": 1024,
        "cost_cap_usd": 5.00,
        "cost_cap_mode": "warn",
        "max_calls_per_task": 3,
        "timeout_ms": 30000,
        "cache_ttl_sec": 3600,
        "custom_endpoint": "",
        "insecure_skip_verify": False
    }

    # Layer 2: config file in user config home (matching install.sh), falling back to legacy user home path
    cfg_path = os.path.expanduser("~/.config/ask-a-friend/config.json")
    if not os.path.isfile(cfg_path):
        cfg_path = os.path.expanduser("~/.ask-friend/config.json")
    file_cfg = {}
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path) as f:
                file_cfg = json.load(f)
        except Exception:
            file_cfg = {}

    # Layer 2.5: config file in project folder (fallback fallback)
    proj_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
    proj_cfg = {}
    if os.path.isfile(proj_cfg_path):
        try:
            with open(proj_cfg_path) as f:
                proj_cfg = json.load(f)
        except Exception:
            proj_cfg = {}

    # Layer 3: env vars (highest priority)
    env_cfg = {}
    if v := os.getenv("ASK_FRIEND_DEFAULT_MODEL"):
        env_cfg["friend_model"] = v
    if v := os.getenv("ASK_FRIEND_REQUIRE_APPROVAL"):
        env_cfg["require_approval"] = v.lower() == "true"
    if v := os.getenv("ASK_FRIEND_USE_CACHE"):
        env_cfg["use_cache"] = v.lower() == "true"
    if v := os.getenv("ASK_FRIEND_COST_CAP_USD"):
        env_cfg["cost_cap_usd"] = float(v)
    if v := os.getenv("ASK_FRIEND_COST_CAP_MODE"):
        env_cfg["cost_cap_mode"] = v
    if v := os.getenv("ASK_FRIEND_CUSTOM_ENDPOINT"):
        env_cfg["custom_endpoint"] = v
    if v := os.getenv("ASK_FRIEND_AGENT_PLATFORM_PROJECT") or os.getenv("ASK_FRIEND_VERTEX_PROJECT"):
        env_cfg["vertex_project"] = v
    if v := os.getenv("ASK_FRIEND_AGENT_PLATFORM_LOCATION") or os.getenv("ASK_FRIEND_VERTEX_LOCATION"):
        env_cfg["vertex_location"] = v
    if v := os.getenv("ASK_FRIEND_INSECURE_SKIP_VERIFY"):
        env_cfg["insecure_skip_verify"] = v.lower() == "true"

    # Merge: defaults < project_cfg < user_home_cfg < env
    merged = {**defaults, **proj_cfg, **file_cfg, **env_cfg}
    return merged
