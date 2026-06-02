import os
import json
import time
import re

CACHE_DIR = os.path.expanduser("~/.ask-friend/cache")

def _validate_key(key):
    return isinstance(key, str) and re.match(r"^[a-f0-9]{64}$", key) is not None

def cache_get(key, ttl_sec):
    if not _validate_key(key):
        return None
    try:
        path = os.path.join(CACHE_DIR, key + ".json")
        if not os.path.isfile(path):
            return None
        with open(path) as f:
            entry = json.load(f)
        if time.time() - entry["ts"] > ttl_sec:
            os.remove(path)
            return None
        return entry["answer"]
    except Exception:
        return None

def cache_set(key, answer):
    if not _validate_key(key):
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, key + ".json")
        with open(path, "w") as f:
            json.dump({"ts": time.time(), "answer": answer}, f)
    except Exception:
        pass
