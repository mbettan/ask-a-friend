import os
import sqlite3
import time

DB = os.path.expanduser("~/.ask-friend/telemetry.db")
RATES = {  # USD per 1M tokens (in, out)
    "gemini-pro": (1.25, 5.00),
    "claude-garden": (3.00, 15.00),
    "gpt-garden": (2.50, 10.00),
    "custom_endpoint": (1.00, 1.00),
}

def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    try:
        with c:
            c.execute("""CREATE TABLE IF NOT EXISTS calls(
                ts REAL, model TEXT, task TEXT, in_tok INT, out_tok INT, cost REAL,
                status TEXT DEFAULT 'SUCCESS', error_reason TEXT)""")
            
            # Handle migration if table existed without the new columns
            cursor = c.cursor()
            cursor.execute("PRAGMA table_info(calls)")
            columns = [col[1] for col in cursor.fetchall()]
            if "status" not in columns:
                c.execute("ALTER TABLE calls ADD COLUMN status TEXT DEFAULT 'SUCCESS'")
            if "error_reason" not in columns:
                c.execute("ALTER TABLE calls ADD COLUMN error_reason TEXT")
    except Exception:
        c.close()
        raise
    return c

def session_spend(window_sec=18000):  # 5h rolling
    c = None
    try:
        c = _conn()
        cutoff = time.time() - window_sec
        row = c.execute(
            "SELECT COALESCE(SUM(cost),0) FROM calls WHERE ts > ? AND status != 'ERROR'", (cutoff,)
        ).fetchone()
        return row[0]
    except Exception:
        return 0.0
    finally:
        if c:
            c.close()

def check_cost_cap(cap_usd, mode):
    spend = session_spend()
    if spend >= cap_usd:
        return "blocked" if mode == "hard" else "warn"
    if spend >= cap_usd * 0.8:
        return "warn"
    return "ok"

def log_call(model, task, usage, status="SUCCESS", error_reason=None):
    c = None
    try:
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)
        ri, ro = RATES.get(model, (1.0, 1.0))
        cost = (in_t * ri + out_t * ro) / 1_000_000 if status == "SUCCESS" else 0.0
        c = _conn()
        with c:
            c.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)",
                      (time.time(), model, task, in_t, out_t, cost, status, error_reason))
    except Exception:
        pass  # silent-fail
    finally:
        if c:
            c.close()

