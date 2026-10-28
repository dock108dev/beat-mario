# Game Companion engineering plan

Updated October 27, 2026. The [Beta 1 plan](beta-1-plan.md) is the canonical
implementation plan. It replaces the prior Mario/Stardew and native Minecraft
camera/wall work orders.

Deliver Minecraft first: a headless bot with its own character, a live game view
beside chat, Codex CLI conversation and gameplay reasoning, concurrent chat/play,
useful travel/gather/craft/build work, interruption and session memory.

MC-B1-01's [headless foundation](mc-b1-01-headless.md) passed local bot checks;
the human-client walkthrough is deferred at the owner's request. Start with
MC-B1-02: integrate Codex CLI and the first concurrent chat/play session using
that bridge. See [live evidence](mc-b1-01-evidence-20261027.md).
Follow MC-B1-03 through MC-B1-06 for broader gameplay, persistence and delivery.

Reuse provider, storage, lifecycle and shell foundations selectively. Do not make
native capture, calibration, focused windows or old Mario/Stardew checks a
prerequisite. Old modules and test contracts retain their historical meanings;
new functionality needs a distinct adapter and focused live evidence.

The second goal is an NES emulator companion. Stardew has no active work.

[Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) ·
[Next session](private-beta-pm-handoff.md) · [Dated status](current-engineering-status.md).
