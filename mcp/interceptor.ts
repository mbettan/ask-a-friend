// Bidirectional MCP middleware: validators (parallel) → mutators (ordered) → observability (async).
import * as http from "http";

type Req = { friend_model?: string; task_type?: string; prompt: string; context?: string };
type Res = { answer: string; usage?: any };

export class Interceptor {
  private tainted = new Set<string>();
  private SECRET =
    /(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)/g;

  async inbound(req: Req): Promise<Req> {
    // --- validators (parallel, fail-closed on injection in both prompt and context) ---
    const promptCheck = this.detectInjection(req.prompt);
    const contextCheck = req.context ? this.detectInjection(req.context) : "ok";

    if (promptCheck === "error" || contextCheck === "error") {
      throw new Error("ask_a_friend: request rejected (injection check failed in prompt or context)");
    }

    // --- mutators (ordered): taint secrets found in context ---
    if (req.context) {
      const m = req.context.match(this.SECRET);
      m?.forEach((s) => this.tainted.add(s));
    }
    return req;
  }

  async outbound(res: Res): Promise<Res> {
    // --- mutator: redact any tainted/secret values escaping in the answer ---
    let answer = res.answer.replace(this.SECRET, "[REDACTED]");
    for (const t of this.tainted) {
      answer = answer.split(t).join("[REDACTED]");
    }
    // --- observability (async, non-blocking, silent-fail) ---
    this.log({ usage: res.usage, ts: new Date().toISOString() });
    return { ...res, answer };
  }

  private detectInjection(p: string): "ok" | "error" {
    return /ignore (all )?previous instructions|exfiltrate|leak the system prompt/i.test(
      p,
    )
      ? "error"
      : "ok";
  }

  private log(data: any) {
    try {
      const body = JSON.stringify(data);
      const req = http.request(
          {
            hostname: "localhost",
            port: 4820,
            path: "/api/telemetry",
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Content-Length": Buffer.byteLength(body),
            },
          },
          () => {}
      );
      req.on("error", () => {}); // fail silently
      req.setTimeout(1500, () => req.destroy());
      req.write(body);
      req.end();
    } catch (_) {}
  }
}
