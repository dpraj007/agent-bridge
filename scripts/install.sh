#!/usr/bin/env bash
set -euo pipefail
echo "Installing agent-bridge..."
python3 -m pip install --upgrade "git+https://github.com/dpraj007/agent-bridge.git"
agent-bridge init
agent-bridge install-skills
echo "Done. Try: agent-bridge sessions list"
