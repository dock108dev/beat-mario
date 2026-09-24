# Game Companion UI design

Updated September 23, 2026. Shared Glass UI Starter 02; presentation-only adaptation of the existing Starter 01 styling.

## For future contributors

Start with [local design requirements](ui-design-requirements.md). If you have the optional shared `ui-templates` folder, review its gallery (`index.html`) and template guide (`README.md`). The source folder on the owner's Mac is `/Users/michaelfuscoletti/Desktop/ui-templates`; it is not included in this repository. It contains dashboard, list/table, form/setup, settings, detail, state/dialog, and native Godot starters.

Use light cool glass, slate text, blue actions, restrained depth, rounded controls, and system typography as the default. Do not reintroduce the generic beige/green/yellow template. Preserve explicit semantic success, caution, error, unavailable, and unknown states. Readability and the task's layout outrank decoration.

The shared folder is a design reference, not a runtime dependency. Project assets are checked in locally and can run without the Desktop folder. If you receive this repository alone, this local requirements copy and the implementation describe the baseline. Request the source template folder when you need the full gallery. Template revisions are adopted deliberately, never silently synchronized.

## This project's adaptation

Catalog, Mario/Stardew workspace, lab, and onboarding receive the shared visual layer. CSS is embedded by the existing page renderer to preserve its content-security policy and package portability. Stop/reclaim remains visibly destructive/red; capability availability, execution authorization, and game drivers are unchanged.

Implementation: src/smb3_agent/glass_ui.py; lab_ui.py; stardew_adapter.py.

The ordinary chooser puts selection before capability details. Mario puts plan review beside conversation, keeps Stop/Take control above the entire page, and groups saved routes, earlier messages and older tools in named disclosures. Setup blockers, pending changes, requested/applied speed and completion uncertainty stay visible. Legacy play tools open automatically when a live observation or Show session exists. Stardew states its inspection-only limit before its disabled controls. No stored values, authority rules, gameplay or persistence contracts changed.

The Starter 02 dashboard/form examples and matched comparison informed the grouping; the gallery's chrome was not copied. Runtime styles remain embedded and local. Existing body typography is retained, supporting conversation labels are enlarged to 14px, and primary controls remain at least 44px. See [matched synthetic previews and checks](ui-verification.md).

## Review and status

See [UI adoption verification](ui-verification.md). Source changes and technical/visual checks do not establish owner acceptance, a new release, live-data qualification, or acceptance of an older frozen candidate. Existing project-specific gates remain separate.
