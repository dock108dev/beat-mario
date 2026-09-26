# Local Game Companion Lab Assets

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
