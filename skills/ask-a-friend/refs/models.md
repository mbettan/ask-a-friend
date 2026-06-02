# Friend Catalog (lazy-loaded)

## Google (first-party)

| alias         | model                                 | strength        |
| ------------- | ------------------------------------- | --------------- |
| (default)     | gemini-2.5-pro                        | reasoning, code |
| @friend:fast  | gemini-2.5-flash                      | cheap, quick    |
| @friend:think | gemini-2.5-pro (high thinking budget) | hard math/logic |

## Model Garden (third-party)

| alias          | model                                       |
| -------------- | ------------------------------------------- |
| @friend:llama  | publishers/meta/models/llama-3.3-70b        |
| @friend:claude | publishers/anthropic/models/claude-sonnet-4 |

## Custom endpoints

Defined in ~/.config/ask-a-friend/config.json under "aliases".
Format: projects/PROJ/locations/LOC/endpoints/ID

## Resolution

alias → config.json → models.md table → error if unknown.
IAM filters: unauthorized models hidden from list_friends.
