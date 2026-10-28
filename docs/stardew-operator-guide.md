# Stardew companion

The older Stardew integration provides selected-copy preparation, observed plans
and bounded watering at `/stardew`. It is separate from headless Minecraft and
requires macOS native capture/input permissions and compatible game views.

## Ordinary farm workflow

Configure the supported game installation, select the recognized farm and approve
an isolated copy. Check the selected save and copy destination before preparation.
Refresh the farm view, describe the request, inspect the proposed targets and limits,
then explicitly approve Start. Preparation is not permission to water.

Watering depends on readable resources, a recognized standard spring farmhouse,
supported clothing/view/basic can, visible dry newly planted seeds and clear
approach/return paths. Arbitrary farms, mature crops, automatic refill and upgraded
tools are unsupported. Copied-save identity and current observation must match the
request; changing views invalidates old coordinates.

Stop/Take control releases input and cancels continuation. A guarded stop can leave
return incomplete. Verify the reported outcome rather than assuming the character
returned home. Saved history never restores a reviewed plan or permission to act.

## Prepared profiles and engineering use

Prepared farm profiles are separate explicit regression inputs. Their save/view
requirements do not widen the ordinary workflow. Use only disposable copies for
native tests and keep original saves intact. See [runtime configuration](runtime-and-configuration.md)
for `STARDEW_REGRESSION_SAVE` and associated settings.

The public Stardew CLI is inspection-only: commands do not select or copy a save,
launch gameplay, or send input. Use `python -m smb3_agent stardew --help` to inspect
its supported command surface. Broader reconnaissance, planting and cave delegation
are not established as reliable ordinary activities.

## Recovery

Close menus and refresh the supported view if recognition fails. A changed window,
unknown resources or mismatched save is a refusal, not permission to retry old
coordinates. Provider failure leaves direct controls available. Keep failed,
partial and completed work distinct; see [error handling](error-handling.md).
