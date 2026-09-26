#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON:-python}"

echo "== git whitespace =="
tracked_whitespace="$(git grep -nI -E '[[:blank:]]+$' -- . || true)"
if [[ -n "${tracked_whitespace}" ]]; then
  echo "Tracked files contain trailing whitespace:"
  echo "${tracked_whitespace}"
  exit 1
fi
git diff --check
git diff --cached --check

echo "== bash syntax =="
bash -n scripts/validate_phase0.sh

echo "== ruff lint =="
"${python_bin}" -m ruff check src tests scripts/security_check.py

echo "== tracked generated-file guard =="
tracked_generated="$(
  git ls-files \
    'artifacts/*' \
    'evidence/*' \
    'build/*' \
    'dist/*' \
    'data/attempts/*' \
    'data/screenshots/*' \
    'data/variants/*.yaml' \
    'data/variants/backups/*' \
    'data/variants/promotions/*' \
    'public/assets/local/*' \
    ':(exclude)public/assets/local/.gitkeep' \
    '*.nes' \
    '*.fds' \
    '*.sav' \
    '*.state' \
    '*.fc?' \
    '*.fm2' \
    '*.pyc' \
    '__pycache__/*' \
    '.pytest_cache/*' \
    '*.egg-info/*' \
    '.coverage' \
    'htmlcov/*' || true
)"

if [[ -n "${tracked_generated}" ]]; then
  echo "Generated or local-only files are tracked:"
  echo "${tracked_generated}"
  exit 1
fi

echo "== tracked credential and game-asset scan =="
"${python_bin}" scripts/security_check.py

echo "== ignored runtime artifact visibility =="
git status --short --ignored

echo "== tests =="
"${python_bin}" -m pytest -q

echo "== active goal contract =="
"${python_bin}" -m smb3_agent goal validate data/goals/world_8_double_whistle.yaml

echo "== active segment catalog =="
"${python_bin}" -m smb3_agent segment validate \
  data/segments/world_8_double_whistle.yaml \
  --goal world_8_double_whistle

echo "== deterministic goal status =="
"${python_bin}" -m smb3_agent goal status world_8_double_whistle

echo "== Game Companion renders =="
route_lab_tmp="$(mktemp -d "${TMPDIR:-/tmp}/smb3-route-lab.XXXXXX")"
player_html="${route_lab_tmp}/player.html"
route_lab_html="${route_lab_tmp}/lab.html"
stardew_html="${route_lab_tmp}/stardew.html"
cleanup_route_lab() {
  rm -f -- "${player_html}" "${route_lab_html}" "${stardew_html}"
  rmdir -- "${route_lab_tmp}"
}
trap cleanup_route_lab EXIT

"${python_bin}" -m smb3_agent lab ui-render --output "${player_html}"
"${python_bin}" -m smb3_agent lab ui-render --view lab --output "${route_lab_html}"
"${python_bin}" -m smb3_agent stardew operator-render --output "${stardew_html}"
if [[ ! -s "${player_html}" ]]; then
  echo "Game Companion player render is empty: ${player_html}"
  exit 1
fi
if [[ ! -s "${route_lab_html}" ]]; then
  echo "Game Companion Lab render is empty: ${route_lab_html}"
  exit 1
fi
if [[ ! -s "${stardew_html}" ]]; then
  echo "Stardew operator render is empty: ${stardew_html}"
  exit 1
fi

player_contract=(
  "data-testid=\"companion-shell\""
  "data-testid=\"game-identity\""
  "data-testid=\"observed-state\""
  "data-testid=\"objective-profile\""
  "data-testid=\"mode-tell\""
  "data-testid=\"mode-show\""
  "data-testid=\"mode-do\""
  "data-testid=\"protected-decisions\""
  "data-testid=\"stop-point\""
  "data-testid=\"activity\""
  "data-testid=\"take-control\""
  "data-testid=\"handoff\""
  "Open Game Companion Lab"
)

for expected in "${player_contract[@]}"; do
  if ! grep -Fq -- "${expected}" "${player_html}"; then
    echo "Game Companion player render is missing: ${expected}"
    exit 1
  fi
done

route_lab_contract=(
  "Game Companion Lab"
  "Mario adapter"
  "Run World 8 Route"
  "World 2 Map"
  "First Whistle (World 2)"
  "Warp Zone 5 / 6 / 7"
  "Second Whistle (Warp Zone)"
  "Warp Zone World 8"
  "World 8 Pipe"
  "World 8 Map"
  "primary-button"
  "secondary-button"
  "segmented-control"
  "segment-active"
  "route-item-selected"
  "status-failed"
  "status-learned"
  "status-validation"
)

for expected in "${route_lab_contract[@]}"; do
  if ! grep -Fq -- "${expected}" "${route_lab_html}"; then
    echo "Game Companion Lab render is missing: ${expected}"
    exit 1
  fi
done

stardew_contract=(
  "data-testid=\"stardew-operator\""
  "data-testid=\"save-identity\""
  "data-testid=\"input-owner\""
  "data-testid=\"crop-progress\""
  "data-testid=\"final-position\""
  "copied save only"
  "Controls remain disabled"
)

for expected in "${stardew_contract[@]}"; do
  if ! grep -Fq -- "${expected}" "${stardew_html}"; then
    echo "Stardew operator render is missing: ${expected}"
    exit 1
  fi
done

echo "Game Companion player, Lab, and Stardew operator render contracts passed"
