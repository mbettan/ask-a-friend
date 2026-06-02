#!/usr/bin/env python3
import http.server
import socketserver
import sqlite3
import time
import os
import json
import webbrowser

PORT = 8080
DB = os.path.expanduser("~/.ask-friend/telemetry.db")

class TelemetryHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.generate_html().encode("utf-8"))
        elif self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.get_stats_json()).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def get_stats_json(self):
        if not os.path.exists(DB):
            return {"calls": []}
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute("PRAGMA table_info(calls)")
            cols = [col[1] for col in c.fetchall()]
            has_extra = "status" in cols
            
            if has_extra:
                c.execute("SELECT ts, model, task, in_tok, out_tok, cost, status, error_reason FROM calls ORDER BY ts DESC")
                rows = c.fetchall()
                keys = ["ts", "model", "task", "in_tok", "out_tok", "cost", "status", "error_reason"]
            else:
                c.execute("SELECT ts, model, task, in_tok, out_tok, cost FROM calls ORDER BY ts DESC")
                rows = c.fetchall()
                keys = ["ts", "model", "task", "in_tok", "out_tok", "cost"]
                
            return {"calls": [dict(zip(keys, r)) for r in rows]}
        finally:
            conn.close()

    def generate_html(self):
        if not os.path.exists(DB):
            return """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Ask a Friend — Live Telemetry Dashboard</title>
  <meta http-equiv="refresh" content="5">
  <style>
    body { background: #030508; color: #fff; font-family: -apple-system, BlinkMacSystemFont, sans-serif; text-align: center; padding-top: 100px; }
    code { background: rgba(255,255,255,0.08); padding: 0.3rem 0.6rem; border-radius: 4px; font-family: monospace; }
  </style>
</head>
<body>
  <h2>No Telemetry Logged Yet</h2>
  <p>Submit at least one friend call using <code>/ask-friend</code> to initialize the telemetry log.</p>
  <p style="color:#555;font-size:0.8rem;">SQLite Path: ~/.ask-friend/telemetry.db</p>
</body>
</html>"""

        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()

            # Read cap from config
            cap_usd = 5.00
            cfg_path = os.path.expanduser("~/.config/ask-a-friend/config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path) as f:
                        cfg = json.load(f)
                        cap_usd = cfg.get("cost_cap_usd", 5.00)
                except Exception:
                    pass

            # 5h spend
            cutoff_5h = time.time() - 18000
            c.execute("SELECT COALESCE(SUM(cost),0) FROM calls WHERE ts > ?", (cutoff_5h,))
            spend_5h = c.fetchone()[0]

            # Total stats
            c.execute("SELECT COUNT(*), COALESCE(SUM(cost),0), COALESCE(SUM(in_tok),0), COALESCE(SUM(out_tok),0) FROM calls")
            total_calls, total_cost, total_in, total_out = c.fetchone()

            # Budget percent
            percent = min(100.0, (spend_5h / cap_usd) * 100.0) if cap_usd > 0 else 0.0

            # Model table rows
            c.execute("SELECT model, COUNT(*), SUM(cost) FROM calls GROUP BY model ORDER BY SUM(cost) DESC")
            model_rows = ""
            for m, cnt, cst in c.fetchall():
                model_rows += f"""
                <div class="log-row">
                  <span class="log-dot ok"></span>
                  <span style="font-weight:bold; color:#e5e7eb;">{m}</span>
                  <span style="color:rgba(255,255,255,0.3); margin-left:10px;">{cnt} calls</span>
                  <span class="log-cost">${cst:.4f}</span>
                </div>
                """

            # Task list rows
            c.execute("SELECT task, COUNT(*) FROM calls GROUP BY task ORDER BY COUNT(*) DESC")
            task_rows = ""
            for t, cnt in c.fetchall():
                task_rows += f"""
                <div class="log-row">
                  <span class="log-dot cache"></span>
                  <span style="color:#e5e7eb;">{t}</span>
                  <span class="log-cost" style="color:#60a5fa;">{cnt} calls</span>
                </div>
                """

            # Log table rows
            c.execute("PRAGMA table_info(calls)")
            cols = [col[1] for col in c.fetchall()]
            has_extra = "status" in cols

            if has_extra:
                c.execute("SELECT ts, model, task, in_tok, out_tok, cost, status, error_reason FROM calls ORDER BY ts DESC LIMIT 10")
                rows = c.fetchall()
            else:
                c.execute("SELECT ts, model, task, in_tok, out_tok, cost FROM calls ORDER BY ts DESC LIMIT 10")
                rows = [(r[0], r[1], r[2], r[3], r[4], r[5], "SUCCESS", None) for r in c.fetchall()]

            log_rows = ""
            for ts, m, t, it, ot, cst, status, err_reason in rows:
                t_str = time.strftime("%H:%M:%S", time.localtime(ts))
                if status == "ERROR":
                    pill_color = "background: rgba(239, 68, 68, 0.12); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2);"
                    reason_html = f' title="{err_reason}" style="cursor:help;"' if err_reason else ''
                    status_html = f'<span class="status-pill" style="{pill_color}"{reason_html}>ERROR</span>'
                    cost_style = "color: rgba(255,255,255,0.3);"
                else:
                    status_html = '<span class="status-pill">SUCCESS</span>'
                    cost_style = "font-weight:bold; color:#34d399;"

                log_rows += f"""
                <tr>
                  <td style="color:rgba(255,255,255,0.4);">{t_str}</td>
                  <td><span style="color:#60a5fa; font-weight:bold;">{m}</span></td>
                  <td><code>{t}</code></td>
                  <td>{it}/{ot}</td>
                  <td style="{cost_style}">${cst:.5f}</td>
                  <td>{status_html}</td>
                </tr>
                """
        finally:
            conn.close()

        # Full glowing HTML template matching premium docs styles
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ask a Friend — Live Telemetry Dashboard</title>
  <meta http-equiv="refresh" content="5">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {{
      --bg-base: #030508; --bg-surface: #0a0d14;
      --primary: #3b82f6; --blue-400: #60a5fa;
      --emerald-400: #34d399; --amber-400: #fbbf24;
      --text-100: #f9fafb; --text-200: #e5e7eb; --text-400: #9ca3af;
      --border-subtle: rgba(255,255,255,0.06);
    }}
    body {{
      background: var(--bg-base); color: var(--text-100);
      font-family: 'Inter', sans-serif; margin: 0; padding: 2rem 1rem;
      overflow-x: hidden; text-align: center;
    }}
    .bg-canvas {{ position: fixed; inset: 0; z-index: -1; overflow: hidden; }}
    .orb {{ position: absolute; border-radius: 50%; filter: blur(120px); opacity: 0.15; }}
    .orb-1 {{ width: 500px; height: 500px; background: #3b82f6; top: -10%; left: -10%; }}
    .orb-2 {{ width: 500px; height: 500px; background: #8b5cf6; bottom: -10%; right: -10%; }}
    .grid-overlay {{
      position: absolute; inset: 0;
      background-image: linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 40px 40px;
    }}
    .container {{ max-width: 1000px; margin: 0 auto; }}
    .logo {{ display: inline-flex; align-items: center; gap: 10px; text-decoration: none; font-weight: 800; font-size: 1.5rem; color: #fff; margin-bottom: 2rem; }}
    .logo-mark {{ width: 36px; height: 36px; background: linear-gradient(135deg, #3b82f6, #6366f1); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1rem; }}
    .agent-window {{ background: var(--bg-surface); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; overflow: hidden; box-shadow: 0 24px 64px rgba(0,0,0,0.6); text-align: left; }}
    .win-bar {{ background: rgba(255,255,255,0.03); border-bottom: 1px solid var(--border-subtle); padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; }}
    .win-dots {{ display: flex; gap: 6px; }}
    .win-dot {{ width: 11px; height: 11px; border-radius: 50%; }}
    .win-dot.r {{ background: #ff5f57; }}.win-dot.y {{ background: #ffbd2e; }}.win-dot.g {{ background: #28c840; }}
    .win-title {{ flex: 1; text-align: center; font-size: 0.75rem; font-weight: 600; color: var(--text-400); font-family: 'JetBrains Mono', monospace; }}
    .win-badge {{ background: rgba(16,185,129,0.12); color: var(--emerald-400); font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 9999px; border: 1px solid rgba(16,185,129,0.2); }}
    .dash-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.25rem; padding: 1.5rem; }}
    .dash-kpi {{ background: rgba(255,255,255,0.02); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 1.25rem; }}
    .dash-kpi .k-label {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-400); display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }}
    .dash-kpi .k-value {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -0.03em; }}
    .dash-kpi .k-trend {{ font-size: 0.7rem; color: var(--text-400); margin-top: 0.25rem; }}
    .dash-progress-bar {{ width: 100%; height: 6px; background: rgba(255,255,255,0.08); border-radius: 99px; overflow: hidden; margin-top: 0.5rem; }}
    .dash-progress-fill {{ height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 99px; }}
    .dash-main {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 1.5rem; padding: 0 1.5rem 1.5rem; }}
    .dash-panel {{ background: rgba(255,255,255,0.02); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 1.25rem; }}
    .dash-panel h4 {{ font-size: 0.75rem; font-weight: 700; margin-top: 0; margin-bottom: 1.25rem; display: flex; align-items: center; justify-content: space-between; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-400); }}
    .log-row {{ display: flex; align-items: center; gap: 0.625rem; padding: 0.6rem 0; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; }}
    .log-row:last-child {{ border-bottom: none; }}
    .log-dot {{ width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }}
    .log-dot.ok {{ background: var(--emerald-400); }}
    .log-dot.cache {{ background: var(--blue-400); }}
    .log-cost {{ margin-left: auto; font-weight: bold; color: var(--emerald-400); }}
    .dash-table-section {{ padding: 0 1.5rem 1.5rem; }}
    .dash-table {{ width: 100%; border-collapse: collapse; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; }}
    .dash-table th {{ color: var(--text-400); border-bottom: 1px solid rgba(255,255,255,0.08); padding: 0.75rem 0.5rem; text-align: left; }}
    .dash-table td {{ border-bottom: 1px solid rgba(255,255,255,0.03); padding: 0.75rem 0.5rem; color: var(--text-200); }}
    .status-pill {{ display: inline-flex; align-items: center; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-weight: bold; background: rgba(16, 185, 129, 0.12); color: var(--emerald-400); border: 1px solid rgba(16, 185, 129, 0.2); }}
    
    @media (max-width: 768px) {{
      .dash-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .dash-main {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 480px) {{
      .dash-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="bg-canvas" aria-hidden="true">
    <div class="orb orb-1"></div><div class="orb orb-2"></div>
    <div class="grid-overlay"></div>
  </div>
  <div class="container">
    <a href="#" class="logo">
      <div class="logo-mark"><i class="fas fa-comments"></i></div>
      <span>Ask<span style="color:#3b82f6;">Friend</span></span>
    </a>
    <div class="agent-window">
      <div class="win-bar">
        <div class="win-dots"><div class="win-dot r"></div><div class="win-dot y"></div><div class="win-dot g"></div></div>
        <div class="win-title">Ask a Friend · Live Telemetry Dashboard</div>
        <div class="win-badge">● LIVE UPDATING</div>
      </div>
      <div class="win-body">
        <div class="dash-grid">
          <div class="dash-kpi">
            <div class="k-label"><i class="fas fa-dollar-sign" style="color:var(--amber-400);"></i> 5h Rolling Spend</div>
            <div class="k-value">${spend_5h:.4f} <span style="font-size:0.75rem; color:var(--text-400); font-weight:normal;">/ ${cap_usd:.2f}</span></div>
            <div class="dash-progress-bar"><div class="dash-progress-fill" style="width: {percent:.1f}%;"></div></div>
          </div>
          <div class="dash-kpi">
            <div class="k-label"><i class="fas fa-phone" style="color:var(--blue-400);"></i> Total Calls</div>
            <div class="k-value">{total_calls}</div>
            <div class="k-trend">queries logged to DB</div>
          </div>
          <div class="dash-kpi">
            <div class="k-label"><i class="fas fa-wallet" style="color:var(--emerald-400);"></i> Total Cost</div>
            <div class="k-value">${total_cost:.4f}</div>
            <div class="k-trend">cumulative spend</div>
          </div>
          <div class="dash-kpi">
            <div class="k-label"><i class="fas fa-database" style="color:#c792ea;"></i> Total Tokens</div>
            <div class="k-value">{total_in + total_out:,}</div>
            <div class="k-trend">In: {total_in:,} / Out: {total_out:,}</div>
          </div>
        </div>
        <div class="dash-main">
          <div class="dash-panel">
            <h4>Model Class Breakdown</h4>
            {model_rows}
          </div>
          <div class="dash-panel">
            <h4>Task Type Usage</h4>
            {task_rows}
          </div>
        </div>
        <div class="dash-table-section">
          <h4 style="font-size:0.75rem; font-weight:700; margin-top:0; margin-bottom:1rem; text-transform:uppercase; color:var(--text-400); letter-spacing:0.05em;">Transaction History Log</h4>
          <table class="dash-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Model Class</th>
                <th>Task Type</th>
                <th>Tokens (In/Out)</th>
                <th>Cost</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {log_rows}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div style="margin-top:2rem; font-size:0.75rem; color:var(--text-400); font-family:'JetBrains Mono',monospace;">
      SQLite path: <code>~/.ask-friend/telemetry.db</code> · Auto-refreshes every 5 seconds
    </div>
  </div>
</body>
</html>"""

def start_server():
    handler = TelemetryHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n\033[1;36m[ask-a-friend] Live Telemetry Dashboard Server started on port {PORT}...\033[0m")
        print(f"\033[1;32m[ask-a-friend] Access the live dashboard at: http://localhost:{PORT}\033[0m")
        print("[ask-a-friend] Press Ctrl+C to stop the server.")
        webbrowser.open(f"http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[ask-a-friend] Server stopped.")

if __name__ == "__main__":
    start_server()
