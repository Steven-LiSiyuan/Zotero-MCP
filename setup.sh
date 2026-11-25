#!/usr/bin/env bash
# Install zotero-mcp-server and register it with Claude Code (Zotero Web API mode).
#
# Usage:
#   ZOTERO_LIBRARY_ID=<your userID> ./setup.sh
#
# API key:
#   - Claude Code cloud sessions: store the key as a network secret for host
#     api.zotero.org; the proxy injects it, so the default placeholder
#     "proxy-injected" is used here and no real key is ever written to disk.
#   - Your own computer: export ZOTERO_API_KEY=<your key> before running
#     (it is then stored in ~/.claude.json, never in this repo).
set -euo pipefail

: "${ZOTERO_LIBRARY_ID:?Set ZOTERO_LIBRARY_ID to your Zotero userID (https://www.zotero.org/settings/keys)}"
ZOTERO_API_KEY="${ZOTERO_API_KEY:-proxy-injected}"
ZOTERO_LIBRARY_TYPE="${ZOTERO_LIBRARY_TYPE:-user}"

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv tool install zotero-mcp-server

claude mcp remove zotero -s user >/dev/null 2>&1 || true
claude mcp add zotero -s user \
  -e ZOTERO_LOCAL=false \
  -e ZOTERO_API_KEY="$ZOTERO_API_KEY" \
  -e ZOTERO_LIBRARY_ID="$ZOTERO_LIBRARY_ID" \
  -e ZOTERO_LIBRARY_TYPE="$ZOTERO_LIBRARY_TYPE" \
  -- "$HOME/.local/bin/zotero-mcp" serve

claude mcp list | grep zotero
