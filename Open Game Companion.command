#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  print 'Game Companion needs its local Python environment. See README.md → Source launch.'
  read '?Press Return to close. '
  exit 1
fi
exec .venv/bin/python scripts/launch_companion.py
