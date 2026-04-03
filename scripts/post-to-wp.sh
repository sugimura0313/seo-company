#!/bin/bash
# GitHubの新着記事をWordPressに下書き投稿するスクリプト
# 使い方: bash scripts/post-to-wp.sh [記事ファイルパス]
# 例: bash scripts/post-to-wp.sh articles/draft/meo/xxx.md

MD_FILE=$1
WP_PATH="/home/yuzu0313/www/chiiki-dx.net"
WP_CLI="php ~/wp-cli.phar --path=$WP_PATH"
NOTIFY_EMAIL="sugimuraeiji32@gmail.com"

# エラー通知関数
notify_error() {
  local MESSAGE=$1
  local SUBJECT="[chiiki-dx.net] 自動投稿エラー: $TITLE"
  cat > /tmp/wp_notify.php << NOTIFYEOF
<?php
wp_mail(
  '$NOTIFY_EMAIL',
  '[chiiki-dx.net] 自動投稿エラー: $TITLE',
  "エラーが発生しました。\n\n詳細: $MESSAGE\n\nファイル: $MD_FILE\n\n確認してください。\nhttps://chiiki-dx.net/wp-admin/edit.php"
);
echo 'mail sent';
NOTIFYEOF
  scp -q /tmp/wp_notify.php sakura-chiiki:/tmp/wp_notify.php 2>/dev/null
  ssh sakura-chiiki "$WP_CLI eval-file /tmp/wp_notify.php; rm /tmp/wp_notify.php" 2>/dev/null
  rm -f /tmp/wp_notify.php
}

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
TAGS=$(grep '^tags:' "$MD_FILE" | head -1 | sed 's/^tags: *//')
STATUS=$(grep '^status:' "$MD_FILE" | head -1 | sed 's/^status: *//')

# ファイル名から投稿スラッグを生成（日付部分を除去）
SLUG=$(basename "$MD_FILE" .md | sed 's/-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}$//')

# すでに投稿済みならスキップ
if [ "$STATUS" = "wp-posted" ]; then
  echo "スキップ: すでにWP投稿済みです ($MD_FILE)"
  exit 0
fi

echo "投稿中: $TITLE"

# MarkdownをGutenbergブロック形式に変換
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUTENBERG_FILE=$(mktemp /tmp/wp_gutenberg_XXXXXX.html)
python3 "$SCRIPT_DIR/md_to_gutenberg.py" "$MD_FILE" > "$GUTENBERG_FILE"

if [ ! -s "$GUTENBERG_FILE" ]; then
  echo "エラー: Gutenberg変換に失敗しました"
  rm "$GUTENBERG_FILE"
  notify_error "Gutenberg変換に失敗しました"
  exit 1
fi

# 記事をWP-CLI経由でサーバーに投稿
POST_ID=$(ssh sakura-chiiki "$WP_CLI post create \
  --post_title='$TITLE' \
  --post_status='draft' \
  --post_type='post' \
  --porcelain" 2>/dev/null)

if [ -z "$POST_ID" ]; then
  echo "エラー: 投稿に失敗しました"
  rm "$GUTENBERG_FILE"
  notify_error "WP-CLI post create に失敗しました（SSH接続またはWP-CLIのエラーの可能性）"
  exit 1
fi

# Gutenberg HTMLをサーバーにアップロード
scp -q "$GUTENBERG_FILE" sakura-chiiki:/tmp/wp_gutenberg_content.html
rm "$GUTENBERG_FILE"

# PHPスクリプトを生成してアップロード（特殊文字を安全に処理）
PHP_FILE=$(mktemp /tmp/wp_update_XXXXXX.php)
cat > "$PHP_FILE" <<PHPEOF
<?php
\$post_id = $POST_ID;
\$content = file_get_contents('/tmp/wp_gutenberg_content.html');
wp_update_post(['ID' => \$post_id, 'post_content' => \$content, 'post_name' => '$SLUG']);
update_post_meta(\$post_id, '_aioseo_description', '$META_DESC');
update_post_meta(\$post_id, '_aioseo_keywords', '$KEYWORD');
// タグを設定
\$tags = '$TAGS';
if (\$tags) {
    \$tag_names = array_map('trim', explode(',', \$tags));
    wp_set_post_tags(\$post_id, \$tag_names, false);
}
echo 'updated: ' . strlen(\$content) . ' bytes';
PHPEOF
scp -q "$PHP_FILE" sakura-chiiki:/tmp/wp_update_post.php
rm "$PHP_FILE"

ssh sakura-chiiki "
$WP_CLI eval-file /tmp/wp_update_post.php
rm /tmp/wp_gutenberg_content.html /tmp/wp_update_post.php
" 2>/dev/null

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
