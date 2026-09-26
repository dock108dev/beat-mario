#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  print 'The local Python environment is missing. Restore it using README.md before requesting a verified shutdown.'
  exit 1
fi
exec .venv/bin/python scripts/launch_companion.py --stop
