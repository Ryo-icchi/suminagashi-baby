#!/bin/bash
# 視覚検証スクリプト v3: フレッシュプロファイル + キャッシュバスト + console取得 + ハング対策
# 出力: /tmp/sumi_shot.png + /tmp/sumi_console.log
set -euo pipefail
cd "$(dirname "$0")"

lsof -ti :8765 | xargs kill 2>/dev/null || true
rm -f /tmp/sumi_shot.png
python3 -m http.server 8765 >/dev/null 2>&1 &
SERVER_PID=$!
PROFILE=$(mktemp -d)
trap 'kill $SERVER_PID 2>/dev/null || true; rm -rf "$PROFILE"' EXIT
sleep 1

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
[ -x "$CHROME" ] || { echo "ERROR: Chrome/Edge が見つからない"; exit 1; }

TS=$(date +%s)
"$CHROME" --headless=new --user-data-dir="$PROFILE" --enable-unsafe-swiftshader \
  --enable-logging=stderr --hide-scrollbars --window-size=1366,768 \
  --screenshot=/tmp/sumi_shot.png \
  "http://localhost:8765/index.html?demo&v=$TS" 2>/tmp/sumi_console.log &
CPID=$!
# screenshot 出力を最大30秒待ち、Chrome居残りは kill（前回ハング対策）
for i in $(seq 30); do [ -f /tmp/sumi_shot.png ] && break; sleep 1; done
sleep 2
kill $CPID 2>/dev/null || true

echo "--- スクリーンショット ---"
ls -la /tmp/sumi_shot.png 2>/dev/null || echo "(撮影失敗)"
echo "--- SUMI マーカー ---"
grep -o 'SUMI[^"]*' /tmp/sumi_console.log | head -20 || echo "(マーカーなし)"
echo "OK"
