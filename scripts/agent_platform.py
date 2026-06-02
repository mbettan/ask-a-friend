import os
import json
import urllib.request
import urllib.error

# Lazy imports for google-auth to handle missing libraries gracefully
google_auth_available = False
try:
    import google.auth
    import google.auth.transport.requests
    google_auth_available = True
except ImportError:
    pass

BREVITY = (
    "Terse. Technical substance exact. Only fluff die.\n"
    "Drop articles, filler, pleasantries, hedging. Fragments OK. Code unchanged.\n"
    "Pattern: [thing] [action] [reason]. [next step].\n"
    "Answer the dev question directly. No preamble. No summary."
)

MODEL_MAP = {
    "gemini-pro": "gemini-3.5-flash",
    "gemini-flash": "gemini-3.5-flash",
    "claude-garden": "claude-sonnet-4-6",
    "gpt-garden": "gpt-4o"
}

def call_agent_platform(friend_model, task_type, prompt, context, project_id=None, location=None, max_tokens=1024, timeout_ms=30000, insecure_skip_verify=False):
    if not google_auth_available:
        return {
            "status": "error",
            "reason": "The 'google-auth' Python package is missing. Please run 'pip install google-auth' (or renew your SSO credentials via 'gcert' if corporate Airlock is blocking it) to proceed."
        }

    # 1. Resolve credentials and project
    try:
        credentials, resolved_project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        access_token = credentials.token
    except Exception as e:
        return {
            "status": "error",
            "reason": f"Agent Platform auth failed. Check GOOGLE_APPLICATION_CREDENTIALS. Detail: {e}"
        }

    # Resolve Project ID and Location from parameters, environment or config (supporting Agent Platform first, then Vertex)
    project_id = (
        project_id or 
        os.getenv("ASK_FRIEND_AGENT_PLATFORM_PROJECT") or 
        os.getenv("AGENT_PLATFORM_PROJECT_ID") or 
        os.getenv("ASK_FRIEND_VERTEX_PROJECT") or 
        os.getenv("VERTEX_PROJECT_ID") or 
        resolved_project
    )
    location = (
        location or 
        os.getenv("ASK_FRIEND_AGENT_PLATFORM_LOCATION") or 
        os.getenv("AGENT_PLATFORM_LOCATION") or 
        os.getenv("ASK_FRIEND_VERTEX_LOCATION") or 
        os.getenv("VERTEX_LOCATION") or 
        "us-central1"
    )

    if not project_id:
        return {
            "status": "error",
            "reason": "Agent Platform auth failed. No GCP Project ID resolved. Set ASK_FRIEND_AGENT_PLATFORM_PROJECT env var."
        }

    # Build prompt with brevity instruction
    full_prompt = f"{BREVITY}\n\nTask Type: {task_type}\n\nQuery:\n{prompt}"
    if context:
        full_prompt += f"\n\n--- CONTEXT ---\n{context}"

    # Determine endpoint URL and payload based on model family
    url = ""
    payload = {}
    is_claude = False
    is_custom = False

    # Resolve Model Target
    model_target = MODEL_MAP.get(friend_model, friend_model)

    # Custom endpoint vs 3P Garden vs Google
    if friend_model == "custom_endpoint" or model_target.startswith("projects/"):
        is_custom = True
        custom_ep = os.getenv("ASK_FRIEND_CUSTOM_ENDPOINT") or model_target
        if not custom_ep or not custom_ep.startswith("projects/"):
            return {
                "status": "error",
                "reason": "custom_endpoint invalid. Verify config.json path."
            }
        # format: https://{location}-aiplatform.googleapis.com/v1/{custom_ep}:predict
        if location == "global":
            domain = "aiplatform.googleapis.com"
        else:
            domain = f"{location}-aiplatform.googleapis.com"
        url = f"https://{domain}/v1/{custom_ep}:predict"
        payload = {
            "instances": [{"content": full_prompt}],
            "parameters": {
                "maxOutputTokens": max_tokens
            }
        }
    elif "claude" in model_target.lower() or "anthropic" in model_target.lower():
        is_claude = True
        # Map to verified Model Garden publisher model identifiers
        if "sonnet" in model_target.lower():
            clean_model = "claude-sonnet-4-6"
        elif "haiku" in model_target.lower():
            clean_model = "claude-haiku-4-5"
        elif "opus" in model_target.lower():
            clean_model = "claude-opus-4-6"
        else:
            clean_model = "claude-sonnet-4-6"
            
        # Anthropic Claude models are regional, route requests on global to us-east5
        req_location = "us-east5" if location == "global" else location
        url = f"https://{req_location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{req_location}/publishers/anthropic/models/{clean_model}:rawPredict"
        payload = {
            "anthropic_version": "vertex-2023-10-16",
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": full_prompt}
            ]
        }
    else:
        # Google model (Gemini)
        clean_model = model_target
        if clean_model == "gemini-pro":
            clean_model = "gemini-3.5-flash"
        elif clean_model == "gemini-flash":
            clean_model = "gemini-3.5-flash"
        elif not (clean_model.startswith("gemini-") or clean_model.startswith("publishers/google/models/")):
            clean_model = "gemini-3.5-flash" # default fallback

        if location == "global":
            domain = "aiplatform.googleapis.com"
        else:
            domain = f"{location}-aiplatform.googleapis.com"

        url = f"https://{domain}/v1/projects/{project_id}/locations/{location}/publishers/google/models/{clean_model}:generateContent"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens
            }
        }

    # 2. Dispatch the request via urllib
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    try:
        # Enforce strict SSL verification on all outbound connections by default
        # Allow explicit opt-in to bypass SSL for corporate proxy / debugging environments via environment flags
        ssl_ctx = None
        if insecure_skip_verify or os.getenv("ASK_FRIEND_INSECURE_SKIP_VERIFY") == "true" or os.getenv("AGENT_PLATFORM_INSECURE_SKIP_VERIFY") == "true":
            import ssl
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0, context=ssl_ctx) as response:
            res_body = response.read().decode("utf-8")
            data = json.loads(res_body)

        # 3. Parse the response based on model family
        if is_custom:
            predictions = data.get("predictions", [])
            if predictions:
                answer = predictions[0] if isinstance(predictions[0], str) else predictions[0].get("content", "")
            else:
                answer = ""
            usage = {"input_tokens": 0, "output_tokens": 0}
        elif is_claude:
            content_blocks = data.get("content", [])
            text_block = next((b for b in content_blocks if b.get("type") == "text"), None)
            answer = text_block.get("text", "") if text_block else ""
            usage_info = data.get("usage", {})
            usage = {
                "input_tokens": usage_info.get("input_tokens", 0),
                "output_tokens": usage_info.get("output_tokens", 0)
            }
        else:
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content"):
                parts = candidates[0]["content"].get("parts", [])
                answer = "".join(p.get("text", "") for p in parts)
            else:
                answer = ""
            usage_info = data.get("usageMetadata", {})
            usage = {
                "input_tokens": usage_info.get("promptTokenCount", 0),
                "output_tokens": usage_info.get("candidatesTokenCount", 0)
            }

        return {
            "status": "ok",
            "answer": answer,
            "usage": usage
        }

    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            err_detail = e.read().decode("utf-8")
        except Exception:
            err_detail = str(e)

        if status_code == 401 or status_code == 403:
            return {"status": "error", "reason": "Agent Platform auth failed. Check GOOGLE_APPLICATION_CREDENTIALS."}
        elif status_code == 404:
            return {"status": "error", "reason": f"Friend model {friend_model} unavailable. Switch friend_model."}
        elif status_code == 429:
            return {"status": "error", "reason": "Agent Platform quota hit. Wait or reduce call rate."}
        else:
            return {"status": "error", "reason": f"Friend call failed. Status {status_code}. Detail: {err_detail}"}
    except urllib.error.URLError as e:
        if "timeout" in str(e).lower():
            return {"status": "error", "reason": f"Friend timed out ({timeout_ms}ms). Reduce context and retry."}
        return {"status": "error", "reason": f"Friend call failed. Connection error: {e}"}
    except Exception as e:
        return {"status": "error", "reason": f"Friend call failed. Check Agent Platform config and retry. Detail: {e}"}
