#!/bin/bash
# すみながしアプリ初回デプロイスクリプト
# アイコン生成 → git初期化 → GitHub publicリポ作成 → push → Pages有効化 まで一括実行
set -euo pipefail
cd "$(dirname "$0")"

REPO="suminagashi-baby"
OWNER="$(gh api user --jq .login)"

echo "=== 1/5 アイコンPNG生成 ==="
python3 gen_icons.py

echo "=== 2/5 git 初期化・コミット ==="
if [ ! -d .git ]; then
  git init -b main
fi
git add -A
git commit -m "1歳から遊べる墨流しマーブリングPWA 初版

タッチで墨滴・なぞって墨流し・ボタンなしの幼児向け設計。
PWA（manifest + Service Worker）でiPadホーム画面から
フルスクリーン・オフライン起動できるようにする。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" || echo "(コミット済み・変更なし)"

echo "=== 3/5 GitHubリポ作成 & push ==="
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "(リポ既存 → push のみ)"
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --push \
    --description "1歳から遊べる墨流しマーブリングPWA"
fi

echo "=== 4/5 GitHub Pages 有効化 ==="
gh api "repos/$OWNER/$REPO/pages" -X POST \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  && echo "Pages を有効化した" \
  || echo "(既に有効化済み)"

echo "=== 5/5 Pages 状態 ==="
gh api "repos/$OWNER/$REPO/pages" --jq '"URL: " + .html_url + "  status: " + .status'

echo ""
echo "=== 完了 ==="
echo "数分後に上記URLで配信開始。iPadのSafariで開いて共有→「ホーム画面に追加」"
