# Mario Player Guide

Game Companion is a local Mario companion. The main page is the player product;
`/lab` is a secondary engineering surface.

The ordinary workspace now includes [conversation and custom-route controls](b2-conversation-guide.md): review the real base fallback, start a bounded plan, type while it plays, inspect pending/applied revisions and retain named variants.

The combined Game Companion catalog is at `/`. Select Mario there to enter this
same workspace at `/mario`. Switching to or from another adapter is explicit
and is refused until active modes stop, input is neutral, evidence is retained,
and player handback is confirmed. No Mario observation, authority, route state,
or evidence classification transfers to another adapter.

## First use

Game Companion uses the existing local Mario configuration and verifies a
supported identity before starting. The player can select a configured local
path through the first-use screen when needed.

FCEUX must be available locally. Confirm that its normal keyboard or controller
mapping is ready, then choose one session:

- **Observe only** — you play; Companion watches and tracks. This launches the
  structurally read-only observer and has no agent-input path.
- **Observe with the option to allow Do later** — adds the takeover-capable
  controller path, but sends no agent input until you explicitly authorize one
  goal against the current visible process and state.

Setup and launch errors stay in the setup card. Retry refuses to duplicate an
active product session.

## Player workspace

The top workspace keeps the current Mario connection, input owner, checkpoint,
observation freshness, objective, progress, timing, comparison, next action,
and mode links together. Normal actions update the workspace in place and
retain scroll, focus while editing, and open technical details.
Background refresh also preserves keyboard focus on the same uniquely matched
link, button, or disclosure without activating it. A removed, disabled, or
ambiguous control does not transfer focus to a different action.

- **Observe** — you play; Companion watches and tracks. Stop observation leaves
  the game running under player control.
- **Tell** — ask for advice at Minimal, Guided, or Full detail. Facts are labeled
  as observed, accepted knowledge, reference facts, derived patterns, candidate
  suggestions, or unknown.
- **Show** — start a separate visible review-only demonstration. Use **Stop
  Demonstration** to end it. Your game is unchanged, and Show cannot claim your
  completion.
- **Do** — review the exact session/process, goal, accepted executable solution,
  scope, stop condition, timeout, protected resources, and stop rules. The
  action **Hand This Goal to Companion** creates fresh same-process authority.
- **Take Control Now** — while Do is active, this control remains visible. It
  requests immediate neutral input and verified handback before play resumes.
- **History** — review sessions, level runs, player/agent/mixed records,
  comparison compatibility, deaths/recovery, learning, candidates, rejected or
  rolled-back changes, and evidence status.

## Advice and learning truth

Quiet never offers unsolicited help. On-request responds only when asked.
Proactive may offer deduplicated help only from fresh supported state and the
selected profile. Ignoring advice is not treated as helpfulness or rejection;
only an explicit response changes a learned preference.

“Fastest locally observed” is not a world record. A candidate is not
executable. Approval means approved for later validation. Only a separately
promoted, replay-safe accepted solution can drive Do. The cumulative V2.5–V2.14
release-candidate validation remains deferred to the consolidated campaign.

## Failure and recovery

Every product recovery card states what happened, whether the game may still
be running, who owns input, whether agent input stopped, the safe next action,
whether evidence was retained, and whether retry creates a fresh attempt.
Unknown ownership, stale observation, unsupported checkpoints, expired
authorization, protected-resource conflicts, process loss, neutralization or
handback failure, incompatible references, corrupt local indexes, and evidence
mismatch fail closed.

The product persists only appropriate local selections, player preferences,
and history. It never restores expired authorization, an active control epoch,
stale process ownership, reclaim state, or a prior write-capable path without
fresh process verification.
