#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " ⚡ Installing SUPER SOAR (Autonomous Incident Responder)"
echo "=========================================================="

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p var /etc/soar config

# Generate SSH keys for out-of-band management if absent
if [ ! -f config/id_ed25519 ]; then
    echo "[*] Generating Ed25519 keypair for remote SSH containment..."
    ssh-keygen -t ed25519 -N "" -f config/id_ed25519 -C "super-soar-responder"
    echo "    Public key generated at config/id_ed25519.pub"
    echo "    (Append this public key to /root/.ssh/authorized_keys or soar service user on target servers)"
fi

# Generate Go Agent HMAC Secret
if [ ! -f config/agent.key ]; then
    echo "[*] Generating HMAC secret for Go proxy agent..."
    openssl rand -hex 32 > config/agent.key
    chmod 600 config/agent.key
fi

# Build Go Agent if Go is available
if command -v go >/dev/null 2>&1; then
    echo "[*] Compiling Go Proxy Agent binary..."
    mkdir -p var/bin
    (cd agent && go build -ldflags="-s -w" -o ../var/bin/super-agent .)
    echo "    Binary created: var/bin/super-agent"
fi

echo "=========================================================="
echo " [✓] Installation complete! Launch with: ./scripts/run.sh"
echo "=========================================================="
