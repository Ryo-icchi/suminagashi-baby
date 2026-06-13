#!/bin/bash
# アイコン生成: 実アプリの ?icon モード（実エンジンで綺麗に構図した墨流し＋中央の緋鯉・
# UI非表示・凍結）を headless Chrome で撮影し、実レンダリングをそのままアイコンにする。
# → アプリの実際の見た目と完全一致する（手描き近似による「アイコン詐欺」を避ける）。
# 旧 gen_icons.py（手描き近似）は本方式に置き換え（2026-06-13）。
set -euo pipefail
cd "$(dirname "$0")"

lsof -ti :8765 | xargs kill 2>/dev/null || true
python3 -m http.server 8765 >/dev/null 2>&1 &
SERVER_PID=$!
PROFILE=$(mktemp -d)
trap 'kill $SERVER_PID 2>/dev/null || true; chmod -R u+w "$PROFILE" 2>/dev/null; rm -rf "$PROFILE" 2>/dev/null || true' EXIT
sleep 1

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
[ -x "$CHROME" ] || { echo "ERROR: Chrome/Edge が見つからない"; exit 1; }

TS=$(date +%s)
SRC="$(mktemp).png"
"$CHROME" --headless=new --user-data-dir="$PROFILE" --enable-unsafe-swiftshader \
  --hide-scrollbars --window-size=1024,1024 --virtual-time-budget=3000 \
  --screenshot="$SRC" "http://localhost:8765/index.html?icon&v=$TS" 2>/dev/null

[ -f "$SRC" ] || { echo "ERROR: 撮影失敗"; exit 1; }
for s in 512 192 180; do
  cp "$SRC" "icon-$s.png"
  sips -z "$s" "$s" "icon-$s.png" >/dev/null
done
rm -f "$SRC"
echo "wrote icon-180/192/512.png（実アプリ ?icon 撮影より）"
