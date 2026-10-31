#!/usr/bin/env bash
# Build the double-click executable for Live Response.
# Output: <project root>/live-response — run it and the console opens in your browser.
#
# Prerequisites (one time):
#   pip install pyinstaller
#
# Usage:
#   ./scripts/build_exe.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m PyInstaller \
  --name live-response \
  --onefile \
  --add-data "soar/static:soar/static" \
  run.py

mv -f dist/live-response live-response
echo ""
echo "Build complete: $(pwd)/live-response"
echo "Run it to start the server and open the web console automatically."
echo "Keep it in the project root so config/ and playbooks/ are found."
