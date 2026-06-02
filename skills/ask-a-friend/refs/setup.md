# Setup (lazy-loaded)

## 1. Auth (pick one)

```bash
gcloud auth application-default login          # ADC, dev
export GOOGLE_APPLICATION_CREDENTIALS=key.json # service account, CI
```

## 2. Project

```bash
export AGENT_PLATFORM_PROJECT_ID=my-project
export AGENT_PLATFORM_LOCATION=global
```

## 3. Verify

```bash
ask-friend list                # should print available friends
```

## 4. Config file (optional)

~/.config/ask-a-friend/config.json

```json
{
  "default": "gemini-2.5-pro",
  "fallback": "gemini-2.5-flash",
  "aliases": { "@friend:architect": "projects/.../endpoints/123" }
}
```

## Troubleshoot

- 403 → check IAM `aiplatform.endpoints.predict`.
- 404 model → wrong location or model not deployed in region.
- timeout → fallback fires automatically; see refs/brevity.md for token guard.
