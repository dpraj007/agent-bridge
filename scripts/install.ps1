# Install agent-bridge on Windows
$ErrorActionPreference = "Stop"
Write-Host "Installing agent-bridge..."
python -m pip install --upgrade "git+https://github.com/dpraj007/agent-bridge.git"
agent-bridge init
agent-bridge install-skills
Write-Host "Done. Try: agent-bridge sessions list"
