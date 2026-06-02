// MCP server exposing ask_a_friend + list_friends, routed to Agent Platform.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { Interceptor } from "./interceptor.js";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { spawn } from "child_process";
import { fileURLToPath } from "url";

// Resolve __dirname in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CFG = (() => {
  try {
    return JSON.parse(
      fs.readFileSync(
        path.join(os.homedir(), ".config/ask-a-friend/config.json"),
        "utf8",
      ),
    );
  } catch {
    return {
      default: "gemini-pro",
      fallback: "gemini-flash",
      aliases: {},
    };
  }
})();

const icept = new Interceptor();
const server = new McpServer({ name: "ask-a-friend", version: "1.0.0" });

function runPythonBackend(args: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, "..", "scripts", "ask_friend.py");
    const child = spawn("python3", [scriptPath], {
      stdio: ["inherit", "pipe", "inherit"], // Map stdin directly to terminal for interactive HIL inputs
      env: {
        ...process.env,
        ASK_FRIEND_INPUT_PAYLOAD: JSON.stringify(args)
      }
    });

    let stdoutData = "";
    child.stdout.on("data", (data) => {
      stdoutData += data.toString();
    });

    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python backend exited with code ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdoutData.trim()));
      } catch (e) {
        reject(new Error(`Failed to parse Python backend JSON response: ${stdoutData}`));
      }
    });

    child.on("error", (err) => {
      reject(err);
    });
  });
}

// Node.js fallback caller if python execution fails
async function callAgentPlatformNode(args: any): Promise<any> {
  let GoogleAuth;
  try {
    const module = await import("google-auth-library");
    GoogleAuth = module.GoogleAuth;
  } catch (e) {
    throw new Error("Google Auth Library dependency missing in Node context. Install google-auth-library.");
  }

  const auth = new GoogleAuth({
    scopes: "https://www.googleapis.com/auth/cloud-platform"
  });
  const client = await auth.getClient();
  const tokenResponse = await client.getAccessToken();
  const accessToken = tokenResponse.token;

  if (!accessToken) {
    throw new Error("Failed to acquire Google Cloud access token.");
  }

  const project = process.env.AGENT_PLATFORM_PROJECT_ID || process.env.ASK_FRIEND_AGENT_PLATFORM_PROJECT || process.env.VERTEX_PROJECT_ID || process.env.ASK_FRIEND_VERTEX_PROJECT || "your-gcp-project-id";
  const location = process.env.AGENT_PLATFORM_LOCATION || process.env.ASK_FRIEND_AGENT_PLATFORM_LOCATION || process.env.VERTEX_LOCATION || process.env.ASK_FRIEND_VERTEX_LOCATION || "us-central1";
  const model = args.friend_model === "auto" || !args.friend_model ? "gemini-3.5-flash" : args.friend_model;

  const BREVITY = `Terse. Technical substance exact. Only fluff die.
Drop articles, filler, pleasantries, hedging. Fragments OK. Code unchanged.
Pattern: [thing] [action] [reason]. [next step]. Answer directly. No preamble.`;

  const fullPrompt = `${BREVITY}\n\nTask Type: ${args.task_type}\n\nQuery:\n${args.prompt}\n\n--- CONTEXT ---\n${args.context || ""}`;

  let url = "";
  let payload = {};

  if (model.includes("claude") || model.includes("anthropic")) {
    const cleanModel = model.includes("sonnet") ? "claude-3-5-sonnet-v2" : "claude-3-opus";
    url = `https://${location}-aiplatform.googleapis.com/v1/projects/${project}/locations/${location}/publishers/anthropic/models/${cleanModel}:rawPredict`;
    payload = {
      anthropic_version: "vertex-2023-10-16",
      max_tokens: args.max_tokens || 1024,
      messages: [{ role: "user", content: fullPrompt }]
    };
  } else {
    const cleanModel = model === "gemini-pro" ? "gemini-3.5-flash" : model;
    url = `https://${location}-aiplatform.googleapis.com/v1/projects/${project}/locations/${location}/publishers/google/models/${cleanModel}:generateContent`;
    payload = {
      contents: [{ role: "user", parts: [{ text: fullPrompt }] }],
      generationConfig: { maxOutputTokens: args.max_tokens || 1024 }
    };
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json; charset=utf-8"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Agent Platform HTTP error ${response.status}: ${errText}`);
  }

  const data: any = await response.json();
  let answer = "";

  if (model.includes("claude") || model.includes("anthropic")) {
    answer = data.content?.[0]?.text || "";
  } else {
    answer = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
  }

  return {
    status: "ok",
    cached: false,
    friend: model,
    answer: answer
  };
}

server.tool(
  "ask_a_friend",
  {
    task_type: z.enum(["code_review", "build_tests", "second_opinion", "security_audit", "spec_critique"]),
    prompt: z.string(),
    context: z.string().optional(),
    friend_model: z.enum(["auto", "gemini-pro", "claude-garden", "gpt-garden", "custom_endpoint"]).optional(),
    require_approval: z.boolean().optional(),
    use_cache: z.boolean().optional(),
    max_tokens: z.number().optional()
  },
  async (args) => {
    // Inbound validations
    const req = await icept.inbound({
      friend_model: args.friend_model,
      task_type: args.task_type,
      prompt: args.prompt,
      context: args.context
    });

    let result: any;
    try {
      // Primary execution: spawn python backend
      result = await runPythonBackend({
        task_type: args.task_type,
        prompt: req.prompt,
        context: req.context,
        friend_model: req.friend_model || "auto",
        require_approval: args.require_approval,
        use_cache: args.use_cache,
        max_tokens: args.max_tokens
      });
    } catch (e: any) {
      // Fallback execution: run native node fetch caller
      try {
        result = await callAgentPlatformNode({
          task_type: args.task_type,
          prompt: req.prompt,
          context: req.context,
          friend_model: req.friend_model || "auto",
          max_tokens: args.max_tokens
        });
      } catch (nodeErr: any) {
        return {
          content: [{
            type: "text",
            text: `Error running ask_a_friend: Python failure: ${e.message}. Node fallback failure: ${nodeErr.message}`
          }]
        };
      }
    }

    // Handle non-OK result statuses cleanly (errors and cancellations)
    if (result.status !== "ok") {
      return {
        content: [{
          type: "text",
          text: `Friend call failed or was cancelled: ${result.reason || result.status || "No reason provided."}`
        }]
      };
    }

    // Outbound redaction + logging
    const out = await icept.outbound({
      answer: result.answer,
      usage: result.usage
    });

    return { content: [{ type: "text", text: out.answer }] };
  }
);

server.tool("list_friends", {}, async () => {
  const friends = [
    "gemini-pro",
    "claude-garden",
    "gpt-garden",
    "custom_endpoint",
    ...Object.keys(CFG.aliases || {}),
  ];
  return { content: [{ type: "text", text: friends.join("\n") }] };
});

async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

run().catch((err) => {
  console.error("MCP server connection error:", err);
  process.exit(1);
});
