# Known limitations

## Minecraft

Large creative-world projects are a new requirement, not an available feature.
Current shelters are 3–7 blocks wide/deep with 2–4-block walls and a 192-cell
ceiling. Island terraforming, broad architectural composition, an editable material/
component catalog and multi-session large-build execution have no qualifying proof.
Earlier owner acceptance was for the bounded foundation and does not establish
these capabilities.

The headless companion operates its own character in a local Java practice world.
It supports bounded movement/following, resource gathering, saved places and
protection areas, crafting, wooden shelters and revisions. Terrain, resource
availability and reserved return travel can cause partial work or refused sites.
Memory is descriptive and scoped to a world; recall may be incomplete and saved
structures need fresh inspection before action. See [usage](minecraft.md).

Bedrock, arbitrary servers, unrestricted exploration, combat/progression and
reliable stone-tool chains are outside the supported ordinary workflow.
The separate native-camera Minecraft integration remains limited to setup and
small camera requests; its movement, placement and wall actions are disabled.

## Creative-building target

The next goal is a general companion that helps a Minecraft novice create imagined
or reference-inspired worlds: setup guidance, understandable materials/components,
editable designs, shaped terrain, varied architecture/interiors/objects, durable
work across sessions and conversational expansion. A replica-style island is an
example, not a franchise-specific mode. The same implementation must handle a
materially different project. Native items and assembled decorative approximations
must be distinguished from working mechanisms.

Creative is the proposed first route to avoid resource grinding, subject to the
owner's project choices. Existing Survival functionality remains separate. Scale,
fidelity, runtime/usage budgets and any privileged construction approach require an
explicit project contract and feasibility measurement. Completion requires the whole
approved project, actual-world and installed-app verification, usable exploration,
data preservation and new owner acceptance. A small demo or the old acceptance
cannot substitute. Public/paid distribution remains a separate scope decision.

## Older integrations

- Mario adaptive play supports a bounded World 1-1 segment, coaching and specific
  demonstrations. Arbitrary levels/tactics and complete coin coverage are unverified.
- Stardew watering depends on recognized views, tools, resource readings, visible
  targets and clear return routes. Arbitrary farms, upgraded tools and automatic
  refill are unsupported. The public CLI is inspection-only; broader reconnaissance
  and cave delegation are not reliable ordinary workflows.
- OpenTTD is a narrow paused-company loan-repayment reference using local Ollama.
- Experimental adapters are declarative contributor fixtures, not native gameplay.

## Platform, inference and operation

The desktop application targets macOS. Native capture/input integrations need
separately installed games and OS permissions. Headless Minecraft does not need
those permissions. Linux CI checks offline contracts, not native desktop behavior.
An AI provider must be explicitly configured; advertised availability does not
guarantee valid inference. Screenshot-dependent actions require verified vision
metadata. No automatic
provider fallback is used.

The HTTP server is loopback-only with no TLS, accounts or multi-user isolation.
Do not expose it through a proxy, tunnel or LAN bind. No hosted deployment,
central backup service or independent job scheduler is provided.

Source changes do not update installed applications. Local packaging requires
additional runtime/assets and a stable signing identity; see
[development](development.md#local-review-packaging). Closing a browser does not
stop the server. Stop or Quit explicitly, and verify reported cleanup failures.
