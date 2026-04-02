#!/bin/bash
# GitHubの新着記事をWordPressに下書き投稿するスクリプト
# 使い方: bash scripts/post-to-wp.sh [記事ファイルパス]
# 例: bash scripts/post-to-wp.sh articles/draft/meo/xxx.md

MD_FILE=$1
WP_PATH="/home/yuzu0313/www/chiiki-dx.net"
WP_CLI="php ~/wp-cli.phar --path=$WP_PATH"

if [ -z "$MD_FILE" ]; then
  echo "使い方: bash scripts/post-to-wp.sh [記事ファイルパス]"
  exit 1
fi

if [ ! -f "$MD_FILE" ]; then
  echo "エラー: ファイルが見つかりません: $MD_FILE"
  exit 1
fi

# YAMLフロントマターから情報を取得
TITLE=$(grep '^title:' "$MD_FILE" | head -1 | sed 's/^title: *//')
META_DESC=$(grep '^meta_description:' "$MD_FILE" | head -1 | sed 's/^meta_description: *//')
KEYWORD=$(grep '^keyword:' "$MD_FILE" | head -1 | sed 's/^keyword: *//')
STATUS=$(grep '^status:' "$MD_FILE" | head -1 | sed 's/^status: *//')

# すでに投稿済みならスキップ
if [ "$STATUS" = "wp-posted" ]; then
  echo "スキップ: すでにWP投稿済みです ($MD_FILE)"
  exit 0
fi

# 本文を取得（フロントマター除去）
CONTENT=$(awk '/^---/{c++;if(c==2){found=1;next}} found{print}' "$MD_FILE")

echo "投稿中: $TITLE"

# 記事をWP-CLI経由でサーバーに投稿
POST_ID=$(ssh sakura-chiiki "$WP_CLI post create \
  --post_title='$TITLE' \
  --post_status='draft' \
  --post_type='post' \
  --porcelain" 2>/dev/null)

if [ -z "$POST_ID" ]; then
  echo "エラー: 投稿に失敗しました"
  exit 1
fi

# 本文をアップロードして更新
CONTENT_FILE=$(mktemp)
echo "$CONTENT" > "$CONTENT_FILE"
scp -q "$CONTENT_FILE" sakura-chiiki:/tmp/wp_post_content.md

ssh sakura-chiiki "
CONTENT=\$(cat /tmp/wp_post_content.md)
$WP_CLI post update $POST_ID --post_content=\"\$CONTENT\"
$WP_CLI post meta update $POST_ID rank_math_description '$META_DESC'
$WP_CLI post meta update $POST_ID rank_math_focus_keyword '$KEYWORD'
rm /tmp/wp_post_content.md
" 2>/dev/null

rm "$CONTENT_FILE"

echo "✅ WP下書き投稿完了!"
echo "   投稿ID: $POST_ID"
echo "   タイトル: $TITLE"
echo "   確認: https://chiiki-dx.net/wp-admin/post.php?post=$POST_ID&action=edit"

# ステータスをwp-postedに更新
sed -i '' "s/^status: draft/status: wp-posted/" "$MD_FILE"
sed -i '' "/^status: wp-posted/a\\
wp_post_id: $POST_ID" "$MD_FILE"

# git commit & push
cd "$(dirname "$0")/.."
git add "$MD_FILE"
git commit -m "WP投稿完了: $TITLE (ID: $POST_ID)"
git push

echo "✅ 完了!"
