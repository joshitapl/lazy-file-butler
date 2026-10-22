#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python app.py
elif [[ -x ../sloth/.venv/bin/python ]]; then
  ../sloth/.venv/bin/python app.py
else
  print 'One-time setup needed. Run these commands in this folder:'
  print 'python3 -m venv .venv'
  print 'source .venv/bin/activate'
  print 'pip install -r requirements.txt'
  print 'python app.py'
  read '?Press Enter to close.'
fi
