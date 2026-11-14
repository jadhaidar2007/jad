#!/usr/bin/env bash
# Builds dist/jw_ainpc_v<version>.zip containing only the resource (no tests/dev files).
# Runs lint + tests + boot simulation first; refuses to package if any fail.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(grep -E "^version '" jw_ainpc/fxmanifest.lua | cut -d"'" -f2)
luacheck jw_ainpc
busted
lua5.4 tools/boot_sim.lua > /dev/null
if grep -rEn "sk-ant-[A-Za-z0-9]|sk-[A-Za-z0-9]{20,}" jw_ainpc; then echo "API key found in resource, aborting"; exit 1; fi
mkdir -p dist
rm -f "dist/jw_ainpc_v${VERSION}.zip"
cp LICENSE jw_ainpc/LICENSE
zip -qr "dist/jw_ainpc_v${VERSION}.zip" jw_ainpc -x '*.DS_Store'
rm jw_ainpc/LICENSE
echo "built dist/jw_ainpc_v${VERSION}.zip"
unzip -l "dist/jw_ainpc_v${VERSION}.zip" | tail -1
