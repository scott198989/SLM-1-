#!/usr/bin/env bash
# Run INSIDE an already approved/created Pod. Does not rent hardware or access your account.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 12), "Select a Python >=3.12 Pod template"'
test -d /workspace || { echo 'Expected persistent /workspace mount; verify Pod storage before proceeding.' >&2; exit 1; }
case "$PWD" in /workspace/*) ;; *) echo 'Clone the project under persistent /workspace first.' >&2; exit 1;; esac
python3 -m venv .venv
.venv/bin/python -m pip install 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cu128
.venv/bin/python -m pip install -r requirements-tested.txt -e .
.venv/bin/python -m forge1 doctor
.venv/bin/python -m pytest -q
echo 'Bootstrap complete. Run a bounded benchmark before authorizing a long training job.'
echo 'This script does not verify that /workspace is a network volume; check the Pod configuration.'
