#!/bin/bash
# WordPress REST API 経由で記事を下書き投稿するスクリプト
# 使い方: bash scripts/post-to-wp.sh [記事ファイルパス]
# 例: bash scripts/post-to-wp.sh articles/draft/meo/xxx.md

MD_FILE=$1
export WP_URL="https://chiiki-dx.net"
export WP_USER="sugi274h"
export WP_APP_PASS="890SMwngaSSgTFdUfkPjiGF4"
NOTIFY_EMAIL="sugimuraeiji32@gmail.com"

if [ -z "$MD_FILE" ]; then
  echo "使い方: bash scripts/post-to-wp.sh [記事ファイルパス]"
  exit 1
fi

if [ ! -f "$MD_FILE" ]; then
  echo "エラー: ファイルが見つかりません: $MD_FILE"
  exit 1
fi

TITLE=$(grep '^title:' "$MD_FILE" | head -1 | sed 's/^title: *//')
STATUS=$(grep '^status:' "$MD_FILE" | head -1 | sed 's/^status: *//')

# すでに投稿済みならスキップ
if [ "$STATUS" = "wp-posted" ]; then
  echo "スキップ: すでにWP投稿済みです ($MD_FILE)"
  exit 0
fi

echo "変換中: $TITLE"

# Markdown → Gutenberg HTML 変換
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUTENBERG_FILE=$(mktemp /tmp/wp_gutenberg_XXXXXX.html)
python3 "$SCRIPT_DIR/md_to_gutenberg.py" "$MD_FILE" > "$GUTENBERG_FILE"

if [ ! -s "$GUTENBERG_FILE" ]; then
  echo "エラー: Gutenberg変換に失敗しました"
  rm -f "$GUTENBERG_FILE"
  exit 1
fi

echo "投稿中: $TITLE"

# REST API 経由でWPに投稿
POST_ID=$(python3 "$SCRIPT_DIR/wp_api_post.py" "$MD_FILE" "$GUTENBERG_FILE" 2>/tmp/wp_api_error.log)
rm -f "$GUTENBERG_FILE"

if [ -z "$POST_ID" ] || echo "$POST_ID" | grep -q "^ERROR"; then
  echo "エラー: WP REST API 投稿失敗"
  cat /tmp/wp_api_error.log >&2

  # エラーをWP下書きとして記録
  ERR_BODY=$(cat /tmp/wp_api_error.log 2>/dev/null | head -5 | tr '"' "'" | tr '\n' ' ')
  curl -s -X POST "${WP_URL}/wp-json/wp/v2/posts" \
    -u "${WP_USER}:${WP_APP_PASS}" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"[自動投稿エラー] ${TITLE}\",\"content\":\"${ERR_BODY}\",\"status\":\"draft\"}" \
    > /dev/null 2>&1 || true

  exit 1
fi

echo "✅ WP下書き投稿完了!"
echo "   投稿ID: $POST_ID"
echo "   確認: ${WP_URL}/wp-admin/post.php?post=${POST_ID}&action=edit"

# ステータスを wp-posted に更新（Linux/Mac 両対応）
python3 - << PYEOF
import re
path = "$MD_FILE"
post_id = "$POST_ID"
content = open(path, encoding="utf-8").read()
content = re.sub(r"^status: \w+", "status: wp-posted", content, flags=re.MULTILINE, count=1)
content = re.sub(r"^(status: wp-posted)", rf"\1\nwp_post_id: {post_id}", content, flags=re.MULTILINE, count=1)
open(path, "w", encoding="utf-8").write(content)
PYEOF

# git commit & push（CCR環境ではgit失敗しても続行）
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"
git add "$MD_FILE"
git commit -m "WP投稿完了: $TITLE (ID: $POST_ID)" || true
git push || true

echo "✅ 完了!"
