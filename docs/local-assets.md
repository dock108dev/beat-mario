# Local Game Companion Lab Assets

## Successor private-beta resource work

GC-D1 in the [engineering plan](private-beta-engineering.md) must inventory required code/data/images/helpers and resolve them in the personal Mac app. Existing ignored Stardew farm/profile registrations, calibration manifests and retained samples cannot be an unexplained setup dependency. Adopt/create them through product setup or include eligible app-owned resources with a complete dependency manifest.

Separate read-only packaged data from writable user profiles/variants/history. Include the FCEUX Lua controllers and required Python/native/OCR resources or explicit tested prerequisites. Use an explicit release inventory rather than copying ignored personal art, runtime evidence and developer data along with all data/public files.

Games, primary saves and credentials remain separately owned. Captures sent for selected model inference are different from files included in the app or feedback report. The retained art/fixture descriptions below remain optional/reference uses.

Optional artwork and engineering-asset reference. The [private-beta engineering plan](private-beta-engineering.md) and [quick start](private-beta-quick-start.md) describe current engineering priorities and retained review-package prerequisites. New GC4 Mario/Stardew delivery must include or guide creation of the actual setup assets it needs; ignored assets do not establish tester availability.

Game Companion Lab can use local-only images from:

```text
public/assets/local/
```

Files in that directory are ignored by git except `.gitkeep`, allowing the
local route lab to use personal reference art without tracking it.

Supported optional filenames:

- `leaf_icon.png`
- `map_icon.png`
- `level_icon.png`
- `whistle_icon.png`
- `fortress_icon.png`
- `airship_icon.png`
- `king_icon.png`
- `toad_house_icon.png`
- `spade_icon.png`
- `hammer_bro_icon.png`

If a file is missing, Game Companion Lab renders a CSS text fallback and remains
fully usable.

## Unattended regression assets

The unattended runner does not place protected runtime inputs in this directory or any other
artifact namespace. The Mario provider records only a local identity; it does
not copy, track, embed, export, or upload source content. Stardew uses only a dedicated regression fixture
proven disjoint from every configured owner-save root, then creates a fresh
disposable copy inside the exact run directory.

Unattended artifacts live only below `artifacts/unattended-regression/` and
remain separate from accepted Mario evidence, reliability, Show, owner pilots,
and primary saves. Symlinked assets/fixtures and path escapes are refused.

## Experimental adapter assets

Experimental scaffolds are declarative contributor material, not runtime inputs.
Only `adapter.yaml`, `README.md`, and the five named JSON fixtures may exist in
the bounded scaffold/install inventory. Saves, owner-game screenshots,
executables, scripts, dependencies, credentials, URLs, and personal data are
refused. The tracked `Fixture Quest` sample contains synthetic JSON only.

Installed manifests live below the local Game Companion application-support
root. Adapter evidence and history use separate namespaces so exact removal can
preserve them. Neither scaffolding nor conformance reads a save, window, or
live game process.
