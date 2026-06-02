#!/usr/bin/env python3
import sqlite3
import time
import os
import sys

DB = os.path.expanduser("~/.ask-friend/telemetry.db")

def main():
    if not os.path.exists(DB):
        print("\n\033[1;31mError: Telemetry database does not exist yet.\033[0m")
        print("Submit at least one friend call to initialize telemetry logging.\n")
        return

    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    try:
        # 1. Cost Cap & Spend Check
        cap_usd = 5.00
        cfg_path = os.path.expanduser("~/.config/ask-a-friend/config.json")
        if os.path.exists(cfg_path):
            try:
                import json
                with open(cfg_path) as f:
                    cfg = json.load(f)
                    cap_usd = cfg.get("cost_cap_usd", 5.00)
            except Exception:
                pass

        # Rolling 5h spend
        cutoff_5h = time.time() - 18000
        c.execute("SELECT COALESCE(SUM(cost),0) FROM calls WHERE ts > ?", (cutoff_5h,))
        spend_5h = c.fetchone()[0]

        # Total stats
        c.execute("SELECT COUNT(*), COALESCE(SUM(cost),0), COALESCE(SUM(in_tok),0), COALESCE(SUM(out_tok),0) FROM calls")
        total_calls, total_cost, total_in, total_out = c.fetchone()

        if total_calls == 0:
            print("\n\033[1;33mNo logs in telemetry database yet.\033[0m\n")
            return

        print("\n\033[1;36m" + "="*76 + "\033[0m")
        print("\033[1;34m                ASK-A-FRIEND TELEMETRY COMMAND CENTER\033[0m")
        print("\033[1;36m" + "="*76 + "\033[0m\n")

        # Budget gauge
        percent = min(100.0, (spend_5h / cap_usd) * 100.0) if cap_usd > 0 else 0.0
        bar_width = 30
        filled = int(percent / 100.0 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        print(f"  \033[1m5-Hour Rolling Budget Usage:\033[0m")
        print(f"  \033[1;32m${spend_5h:.4f}\033[0m / \033[1;30m${cap_usd:.2f}\033[0m")
        color = "\033[1;32m" if percent < 80 else "\033[1;33m" if percent < 95 else "\033[1;31m"
        print(f"  [{color}{bar}\033[0m] {percent:.1f}%\n")

        print(f"  \033[1mOverall Telemetry Summary:\033[0m")
        print(f"  • Total Calls:     \033[1m{total_calls}\033[0m")
        print(f"  • Total Spend:     \033[1;32m${total_cost:.4f}\033[0m")
        print(f"  • Average Cost:    \033[1m${(total_cost/total_calls):.4f}\033[0m" if total_calls > 0 else "  • Average Cost:    $0.0000")
        print(f"  • Total Tokens:    \033[1m{total_in + total_out:,}\033[0m (In: {total_in:,} / Out: {total_out:,})\n")

        # Stats by Model family
        print(f"  \033[1mSpend by Model Class:\033[0m")
        c.execute("SELECT model, COUNT(*), SUM(cost) FROM calls GROUP BY model ORDER BY SUM(cost) DESC")
        for model, count, cost in c.fetchall():
            print(f"  • \033[1;35m{model:<18}\033[0m {count:>3} calls  →  \033[1;32m${cost:.4f}\033[0m")
        print()

        # Stats by Task type
        print(f"  \033[1mUsage by Task Type:\033[0m")
        c.execute("SELECT task, COUNT(*) FROM calls GROUP BY task ORDER BY COUNT(*) DESC")
        for task, count in c.fetchall():
            print(f"  • \033[1;33m{task:<18}\033[0m {count:>3} calls")
        print()

        # Recent Transactions table
        print(f"  \033[1mRecent Transactions Log (Last 5):\033[0m")
        print("  \033[1;30m" + "-"*76 + "\033[0m")
        print("  \033[1m%-8s  %-16s  %-16s  %-16s  %-8s\033[0m" % ("Time", "Model", "Task Type", "Tokens (In/Out)", "Cost"))
        print("  \033[1;30m" + "-"*76 + "\033[0m")
        
        c.execute("SELECT ts, model, task, in_tok, out_tok, cost FROM calls ORDER BY ts DESC LIMIT 5")
        for ts, model, task, in_t, out_t, cost in c.fetchall():
            t_str = time.strftime("%H:%M:%S", time.localtime(ts))
            print("  %-8s  %-16s  %-16s  %d/%-11d  \033[32m$%-8.4f\033[0m" % (t_str, model[:16], task[:16], in_t, out_t, cost))
        print("  \033[1;30m" + "-"*76 + "\033[0m")
        print()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
