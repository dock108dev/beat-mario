# Conversation, contextual intent and game decisions

This contributor guide describes conversation, reviewed plans and control.
[Architecture](agent-architecture.md#conversation-gameplay-and-control) defines
the model and controller roles. The [Mario guide](mario-player-guide.md) and
[Stardew guide](stardew-operator-guide.md) describe player procedures and limits.

## Current implementation

The ordinary source app creates one Codex provider and separate contextual language sessions for Mario and Stardew. Original wording, recent conversation, prior intent, compatible descriptive history and fresh supported game context go to the language model. Its validated intent then enters existing adapter planners and control owners. Prepared Day 2 watering additionally calls a distinct gameplay role at target boundaries and feeds observed effects into its next decision. Other activities retain their existing strategy controllers. See [verification](gc-ai-loop-verification.md).

Mario now also has an experimental visual early-segment model loop and compatible descriptive coaching (see verification); it retains source-qualified opening coaching, experimental coin-route selection, remembered stairs/pipe instructions, two observed World 1-1 exits and two supported sky 1UP collections. Stardew has source-qualified Day 2 selected watering, passive planting-location discussion and eastern-margin inspection/return. These successes establish the named activities and their controllers. They do not establish unrestricted conversation coverage, arbitrary farms or packaged beta delivery. Cave delegation remains unverified; source reconnaissance composition has native acceptance pending.

`model_gateway.LocalOllamaGateway` is real model infrastructure used by the separate profile/OpenTTD reference flow. Its proposal schema selects one available skill and screen target. It does not supply either ordinary Mario/Stardew AI role. The existing typed plans, observations, controllers, interruption and outcome ledgers are reusable foundations.

Player recording/demonstration source is preserved but deferred to a later beta, tentatively beta v2. No recording is required for this implementation sequence.

## Required language role

The language LLM interprets the player's original words in context. It needs relevant conversation history, the current objective and approved scope, progress, fresh game facts, selected/visible entities, implemented adapter capabilities and compatible memory. Relevant images can complement semantic facts; the app must distinguish current observations, historical facts, game rules and uncertain interpretations.

The interpretation contract must retain:

- Original request and interaction type: question, objective, clarification, correction, preference, approval reference or control request.
- Requested objective and proposed observable completion conditions.
- Targets and resolved conversational/spatial references, including unresolved ambiguity.
- Preferences, priorities, exclusions, conditional requirements and resource/time limits.
- Current-versus-next-attempt coaching scope and the relevant action or decision when identifiable.
- Capabilities required, supported parts and unsupported parts without coercing the request into the nearest canned task.
- A concise player-facing interpretation or necessary clarification.

Engineering chooses the schema and model integration. Preserve the goal separately from the compiled executable plan. Adapter-owned grounding and mechanics determine which part can be executed in the current state. A model-generated target or completion claim is a proposal until current observations support it.

Multi-turn references, changed preferences and compound requests must work without adding a phrase branch for each conversation. Unsupported goals should still be understood accurately. Approval language binds to the displayed current plan and session; understanding assent does not allow the model to create authority.

## Required gameplay role

The gameplay agent receives the understood objective, current world state, remaining approved resources, available finite skills, mechanics and useful memory. It chooses or composes the next action, states an expected observable effect, receives the actual result and decides what to do next.

```text
contextual intent -> validated goal and reviewed scope
-> observe -> model decision -> validate -> finite skill
-> independent outcome observation -> update state/memory -> next decision
```

A typed decision must identify the action, target and parameters, relevant evidence, expected effect and the condition for reassessment. It can also request observation, clarification, a revised scope or handback. The fast controller owns timing, feedback, execution limits and release; the model must not be called for every Mario frame or every input pulse.

Failed movement, changed resources, an absent target or unexpected outcomes must affect subsequent decisions. The implementation should try a justified feasible alternative or gather missing information, and stop when no useful supported approach remains. Repeating fixed routes or tuning timing indefinitely is not sufficient adaptive play. Existing routes become useful skills or reference knowledge beneath this loop.

## Codex-backed local application integration

The first backend is the owner's installed, signed-in Codex CLI, as established in the architecture document. Use it during ordinary app operation. Choose non-interactive execution or the app-server integration according to the needed persistent conversation, tool interaction and cancellation behavior. Installation/authentication discovery has already been checked; the source runtime integration is implemented; wider quality evaluation and exact packaged discovery remain pending.

The app stays local, while ordinary OpenAI-backed Codex inference sends selected context and images to the remote model. Keep that distinction visible in setup and diagnostics. Reuse saved CLI authentication; do not copy credentials into profiles, evidence or packages. Package launch must locate the configured executable outside an interactive terminal and show useful recovery for missing CLI, signed-out state or unavailable service.

Provide separate structured contracts for language interpretation and gameplay decisions. The OpenTTD screen-box proposal schema is too narrow for these roles. Provider transport, role state, observation selection, validation and ordinary controller ownership must remain separate.

Session/context integration must support:

- App-owned game/conversation/goal identities, request and plan revisions, observation identity and a control generation independent of any provider thread identifier.
- Bounded conversation context and summaries that preserve current constraints, corrections, unresolved questions and evidence provenance.
- Read-only access to selected current observations, capability/skill descriptions, relevant mechanics, progress and compatible memory.
- Structured action proposals through the app's validated dispatcher; no direct provider access to raw keyboard/mouse, shell, arbitrary files, save mutation or controller commands.
- Freshness rechecks after inference and before input; stale targets and superseded requests cannot execute.
- Known provider outcomes for success, refusal, invalid/incomplete output, timeout, cancellation, unavailable service and usage limits.
- Inspectable call latency and usage when available. Missing usage information remains unknown.

Game text, imported notes and recorded lessons are data. They cannot replace the approved objective, grant tools or override runtime boundaries. Tool/observation results must be bounded and grounded in the selected game rather than exposing unrelated desktop or repository content.

## Control, asynchronous work and reopening

Direct Stop and Take control must remain available before, during and after model work. Urgent conversational control retains its independent priority path. Revoke the current input authority and invalidate queued decisions before waiting for provider cancellation or history writes.

Cancellation must handle pending inference, a completed reply awaiting validation, pending review, an executing skill, game switching and application shutdown. Provider cancellation acknowledgment and confirmed native input release are separate facts. Late output must be discarded by the app's control generation, even if a remote request continues processing.

During slow inference, pause/release or finish only the already validated finite skill within its existing scope. Do not continue stale movement while deciding what to do. Discussion in Stardew safely releases native input; returning focus does not resume an outdated plan.

Reopening restores conversation summaries, useful memory and historical results. It establishes no live observation, connection, approval or gameplay authority. A resumed provider conversation cannot carry execution permission across app restarts.

## Integration sequence and acceptance

First connect genuine contextual interpretation to both ordinary game interfaces. Then complete one adaptive Stardew activity using existing watering/inspection skills: a real model-generated goal, a model-selected action with parameters, a verified effect and a later model decision based on the result. Include changed preferences and supported changed scene/resource/target conditions using the same implementation. This must not depend on finishing a bespoke cave manifest first.

Next extend Mario decisions at useful skill boundaries while preserving its per-frame controller. Demonstrate coaching and state variation influencing actual play. Continue required game coverage, then package and verify the complete ordinary experience before private beta.

Evaluation needs separate forms of evidence:

| Evidence | What it establishes |
| --- | --- |
| Deterministic contract/race/fixture checks | Schema validation, context ownership, grounding, cancellation, authority, persistence and expected orchestration. Simulated model replies do not prove model understanding. |
| Real-model held-out evaluation | Contextual interpretation, reference resolution, unsupported-goal understanding, structured output, decision quality and useful latency with wording/state variation withheld from implementation. |
| Live ordinary-interface gameplay | Model-selected actions actually execute, independent outcomes affect later decisions, changes work without bespoke script edits, and interruption/handback are real. |
| Packaged walkthrough and owner use | The delivered app discovers its backend and assets, connects, understands, plays, reports and reopens without engineering file edits. Source evidence alone does not establish this. |

Cover ambiguity, exclusions, revised priorities, identical wording in different contexts, invalid provider output, service failure, canceled/stale replies, unknown observations, incompatible memory and interrupted reopening. Keep understandable explanations and evidence records; private chain-of-thought collection is unnecessary.

Retain original words, supplied observations, resolved intent, chosen actions, model-call provenance, expected/actual effects, subsequent decisions, uncertainty and handback. [Learning](learning.md) owns retained knowledge and application; [Mario integration](b2-integration-contract.md) and [Stardew integration](b3-integration-contract.md) locate current controller/runtime seams. Historical B-series contracts retain their named scope and cannot certify this new architecture.

## Adaptive Mario segments in the source app — October 5

The legacy opening scope remains x≥160 with six decisions, 180 skill frames and 120 seconds. Ask to play the early segment to use the separate x≥700 grounded scope: 32 decisions, 1200 skill frames and 480 seconds. Review with **Apply change**, then Start. The model receives the exact paused NES image, world progress, scroll, velocity, grounded state, enemy proximity and prior effects. It composes hops, walking, observed landing, retreat, inspection and Stop while native controllers own frame timing and authority checks.

Meaningful high/short-hop preferences alter actual choices; obstacle facts can justify longer jumps. Ask to remember a correction for compatible future segments, inspect active/superseded advice, or reset future guidance while preserving outcomes. Later native execution has matching guidance-ID/skill receipts; improvement stays unknown. The exact native trials extend beyond opening over raised terrain, but stop before the x=700 arrival. Stop/Take control cancel pending inference and retry permission. Reopening restores descriptive history only. Full-level adaptive strategy, complete coins and generalized flight remain later coverage. See [verification](gc-ai-loop-verification.md).


Supported-segment closeout: Mario’s supported World 1-1 x≥700 segment has 3/3 native completions on the final unchanged source, with independently observed alive/grounded arrival and neutral handback for each passing run. The set includes two compatible-coaching trials and a walking-on-flat/raised-block landing preference variation. Earlier failures remain failed under their own candidate identities. Running maneuvers, a feedback-bounded run-up, native object/projectile/motion facts, neutral waiting and after-frame arrival checks address the retained blockers. This small engineering set establishes observed scope, not broad reliability. Prepared Stardew watering acceptance is preserved. See [verification](gc-ai-loop-verification.md). Wider Mario coverage, exact-package qualification and owner release remain open.
