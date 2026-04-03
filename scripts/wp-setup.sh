#!/bin/bash
# WordPress新規サイト標準セットアップスクリプト
# 使い方: bash scripts/wp-setup.sh [ドメイン名] [サイトタイトル] [サイト説明]
# 例: bash scripts/wp-setup.sh example.net "サイト名" "サイト説明"

DOMAIN=$1
TITLE=$2
DESCRIPTION=$3
WP_PATH="/home/yuzu0313/www/$DOMAIN"
WP_CLI="php ~/wp-cli.phar --path=$WP_PATH"
SWELL_ZIP="/home/yuzu0313/tmp_swell.zip"

if [ -z "$DOMAIN" ]; then
  echo "使い方: bash wp-setup.sh [ドメイン名] [サイトタイトル] [サイト説明]"
  exit 1
fi

echo "=== WordPress セットアップ開始: $DOMAIN ==="

# 1. Swellテーマをアップロード＆展開
echo "--- Swellテーマをアップロード中 ---"
cd "/Users/sugimuraeiji/Local Sites/rocket-studio/app/public/wp-content/themes"
zip -r /tmp/swell.zip swell swell_child -x "*.DS_Store" > /dev/null 2>&1
scp /tmp/swell.zip sakura-chiiki:$SWELL_ZIP
ssh sakura-chiiki "cd $WP_PATH/wp-content/themes && unzip -o $SWELL_ZIP && rm $SWELL_ZIP"

# 2. 不要プラグイン削除
echo "--- 不要プラグインを削除中 ---"
ssh sakura-chiiki "$WP_CLI plugin delete vk-blocks vk-block-patterns vk-all-in-one-expansion-unit vk-post-author-display vk-dynamic-if-block vk-plugin-list vk-fullsite-installer snow-monkey-forms simple-page-ordering codepress-admin-columns breadcrumb-navxt advanced-database-cleaner wp-super-cache ts-webfonts-for-sakura 2>/dev/null; echo 'done'"

# 3. 必須プラグインインストール＆有効化
echo "--- 必須プラグインをインストール中 ---"
ssh sakura-chiiki "
$WP_CLI plugin install seo-by-rank-math --activate 2>/dev/null
$WP_CLI plugin install wordfence --activate 2>/dev/null
$WP_CLI plugin install wp-fastest-cache --activate 2>/dev/null
$WP_CLI plugin install contact-form-7 --activate 2>/dev/null
$WP_CLI plugin install really-simple-ssl --activate 2>/dev/null
$WP_CLI plugin install shortpixel-image-optimiser --activate 2>/dev/null
$WP_CLI plugin install xo-security --activate 2>/dev/null
echo 'done'
"

# 4. Swellテーマ有効化
echo "--- Swellテーマを有効化中 ---"
ssh sakura-chiiki "$WP_CLI theme activate swell_child"

# 5. 基本設定
echo "--- 基本設定を適用中 ---"
ssh sakura-chiiki "
$WP_CLI option update blogname '$TITLE'
$WP_CLI option update blogdescription '$DESCRIPTION'
$WP_CLI option update timezone_string 'Asia/Tokyo'
$WP_CLI option update date_format 'Y年n月j日'
$WP_CLI option update time_format 'H:i'
$WP_CLI option update permalink_structure '/%postname%/'
$WP_CLI option update default_comment_status 'closed'
$WP_CLI option update default_ping_status 'closed'
$WP_CLI option update comment_moderation '1'
$WP_CLI option update siteurl 'https://$DOMAIN'
$WP_CLI option update home 'https://$DOMAIN'
echo 'done'
"

echo "=== セットアップ完了: https://$DOMAIN ==="
echo ""
echo "【手動設定が必要な項目】"
echo "  1. XO Security: ログインURLをランダム文字列に変更、CAPTCHAをひらがなに設定"
echo "     → https://$DOMAIN/wp-admin/options-general.php?page=xo-security"
echo "  2. Rank Math: 初期ウィザードを完了、サイトマップ有効化"
echo "     → https://$DOMAIN/wp-admin/admin.php?page=rank-math"
echo "  3. GTM: コンテナ作成 → head/bodyタグをfunctions.phpに追加（手動）"
echo "  4. GTM内でGA4タグを設定"
echo "  5. Google Search Console: サイト登録・サイトマップ送信"
echo "     → https://search.google.com/search-console"
echo "  5. Really Simple SSL: SSL有効化確認"
echo "  6. お問い合わせページ作成（CF7フォーム埋め込み）"
echo "  7. カテゴリ作成: サイトの3本柱に合わせたカテゴリ"
