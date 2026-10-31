#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC1091
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export SOAR_AGENT_KEY="$(cat config/agent.key 2>/dev/null || echo 'super_secret_agent_key_default')"

echo "Starting Super SOAR engine..."
exec python3 -m soar --config config/config.yaml "$@"
