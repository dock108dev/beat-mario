# AI provider configuration

The application selects one provider for ordinary Minecraft, Mario and Stardew
language/gameplay inference. Game tools, Review/Start, Stop, control epochs and save
protections remain on the app machine. Model replies are proposals, not tool calls.

## Configure the normal launcher

Set `~/Library/Application Support/Game Companion/ai-provider.json`, or set
`AI_CONFIG_FILE` to another file. The source launcher and a desktop build containing
this integration read the same file. Restart the app after changing settings.
The file may contain these keys:

```json
{
  "provider": "openai-compatible",
  "app": "game-companion",
  "base_url": "http://127.0.0.1:11434/v1",
  "api_key": "ollama",
  "model": "your-exact-installed-tag",
  "timeout_seconds": 240,
  "max_tokens": 512,
  "temperature": 0.3,
  "reasoning_effort": "none",
  "stream": true
}
```

This is a configuration example, not a claim that a model is installed. Use the
explicit server/model you intend, including any application-specific gateway path.
The base URL must be loopback or a literal private-network address. No proxy,
redirect, cloud fallback or server scanning is used. Keep credentials outside Git.
Unencrypted HTTP on a LAN exposes requests to that network; choose a trusted server
and network. No browser-to-model connection is made.

Environment overrides are `AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`,
`AI_TIMEOUT_SECONDS`, `AI_MAX_TOKENS`, `AI_TEMPERATURE`, `AI_REASONING_EFFORT` and
`AI_STREAM`. `ollama` selects the same OpenAI-compatible inference transport as
`openai-compatible`. These names share one transport; no alternate provider is loaded.
Unset configuration disables AI; invalid configuration does not select a fallback.
There is no production default or deployment change.

## Discovery and capability boundaries

Readiness requires the exact tag from `<base_url>/models` and its local identity
from `/api/tags` on the same configured origin. `/api/show` verifies screenshot
capability. Missing vision metadata disables image requests while text requests
remain usable. Advertised readiness is not a tested inference result. No model
is downloaded automatically. A cloud/remote-model indication is refused.

Each metadata request has a 5-second socket timeout. An optional `/api/show`
timeout or connection failure leaves verified text readiness available and vision
unavailable; required model/tag discovery failures still prevent inference.
Inference uses the configured timeout (up to 240 seconds) as both its socket
timeout and overall request deadline, including the worker's before/after identity
checks. Those identity requests retain their 5-second metadata limit. There is no
15-second chat disconnect timer. Remote gateways may impose additional limits.

Profile-qualified native activities retain their exact `backend_id`; selecting
another tag does not requalify them. Those activities require native Ollama
metadata/chat support and verified vision, and remain unavailable on mismatch.
Their existing finite task/call budgets and disposable workers remain in place.
Provider allocation measurements refer to the configured server, not another local
Ollama instance. No image-generation feature is present; screenshot understanding
is the only image input path.

## Structured inference and cancellation

Requests use `/chat/completions`, strict JSON-schema output, bounded context and at
most one PNG/JPEG screenshot. Streams are assembled on the backend; partial text
never grants authority. Tool calls, truncated replies, model/identity changes and
locally invalid schema results are rejected. No automatic retry or provider
substitution is made. A 512-token budget can be insufficient for a large plan;
truncation remains a visible failure rather than a partially executed plan.

Stop kills the app's request worker and discards late output. This does not prove
remote GPU computation stopped. Existing shorter gameplay/profile deadlines still
apply independently. Usage is recorded only when the server supplies it; absent
usage is unknown, not zero. Developer task generation and route-patch packets do
not invoke this provider. Engineering packets use `lab engineering-task`, the
`engineering_task` source kind and the `engineering_tasks/` session directory.
Regenerate older development packets before applying a route patch.
