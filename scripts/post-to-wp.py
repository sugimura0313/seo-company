#!/usr/bin/env python3
"""
WordPressに記事を下書き投稿するスクリプト
使い方: python3 scripts/post-to-wp.py articles/draft/meo/xxx.md
"""

import sys
import os
import json
import base64
import re
import ssl
from urllib.request import urlopen, Request
from urllib.error import URLError

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# .envから認証情報を読み込む
def load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    # 環境変数も参照（リモートエージェント用）
    for key in ['WP_URL', 'WP_USER', 'WP_APP_PASSWORD']:
        if key in os.environ:
            env[key] = os.environ[key]
    return env

def parse_frontmatter(content):
    """YAMLフロントマターを解析する"""
    meta = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()
    return meta, body

def markdown_to_blocks(md_content):
    """MarkdownをWordPressブロックエディタ用HTMLに変換"""
    # 見出し変換
    content = re.sub(r'^# (.+)$', r'<!-- wp:heading {"level":1} -->\n<h1>\1</h1>\n<!-- /wp:heading -->', md_content, flags=re.MULTILINE)
    content = re.sub(r'^## (.+)$', r'<!-- wp:heading -->\n<h2>\1</h2>\n<!-- /wp:heading -->', content, flags=re.MULTILINE)
    content = re.sub(r'^### (.+)$', r'<!-- wp:heading {"level":3} -->\n<h3>\1</h3>\n<!-- /wp:heading -->', content, flags=re.MULTILINE)

    # 太字
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)

    # 区切り線
    content = re.sub(r'^---$', r'<!-- wp:separator -->\n<hr class="wp-block-separator"/>\n<!-- /wp:separator -->', content, flags=re.MULTILINE)

    # テーブル（簡易変換）
    lines = content.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if '|' in line and i + 1 < len(lines) and '|' in lines[i+1] and re.match(r'[\|\s\-:]+', lines[i+1]):
            # テーブル開始
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1
            html = '<!-- wp:table -->\n<figure class="wp-block-table"><table><tbody>'
            for j, tl in enumerate(table_lines):
                if j == 1 and re.match(r'[\|\s\-:]+', tl):
                    continue
                cells = [c.strip() for c in tl.split('|') if c.strip()]
                tag = 'th' if j == 0 else 'td'
                html += '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>'
            html += '</tbody></table></figure>\n<!-- /wp:table -->'
            result.append(html)
        else:
            result.append(line)
            i += 1

    content = '\n'.join(result)

    # 段落変換（空行で区切られたテキスト）
    paragraphs = content.split('\n\n')
    blocks = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<!-- wp:'):
            blocks.append(p)
        elif p.startswith('-') or p.startswith('*'):
            items = '\n'.join(f'<li>{re.sub(r"^[-*]\s*", "", line)}</li>' for line in p.split('\n') if line.strip())
            blocks.append(f'<!-- wp:list -->\n<ul>{items}</ul>\n<!-- /wp:list -->')
        else:
            blocks.append(f'<!-- wp:paragraph -->\n<p>{p}</p>\n<!-- /wp:paragraph -->')

    return '\n\n'.join(blocks)

def post_to_wordpress(md_file_path):
    env = load_env()
    wp_url = env.get('WP_URL', '').rstrip('/')
    wp_user = env.get('WP_USER', '')
    wp_pass = env.get('WP_APP_PASSWORD', '').replace(' ', '')

    if not all([wp_url, wp_user, wp_pass]):
        print("エラー: .envにWP_URL, WP_USER, WP_APP_PASSWORDを設定してください")
        sys.exit(1)

    # 記事ファイルを読み込む
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    meta, body = parse_frontmatter(content)
    title = meta.get('title', os.path.basename(md_file_path))
    meta_desc = meta.get('meta_description', '')

    # Markdownをブロックに変換
    wp_content = markdown_to_blocks(body)

    # 認証ヘッダー
    credentials = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()

    # カテゴリ判定
    category_map = {'meo': 'MEO・集客', 'lawyer': '士業Web集客', 'subsidy': '補助金・助成金', 'security': 'セキュリティ', 'maintenance': '保守・メンテナンス', 'performance': '表示速度改善'}
    file_category = os.path.basename(os.path.dirname(md_file_path))
    category_name = category_map.get(file_category, '未分類')

    # 投稿データ
    post_data = {
        'title': title,
        'content': wp_content,
        'status': 'draft',
        'meta': {
            'rank_math_description': meta_desc
        },
        'excerpt': meta_desc
    }

    # REST APIに投稿
    api_url = f"{wp_url}/wp-json/wp/v2/posts"
    req = Request(
        api_url,
        data=json.dumps(post_data).encode('utf-8'),
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urlopen(req, context=ssl_context) as response:
            result = json.loads(response.read())
            post_id = result.get('id')
            post_url = result.get('link')
            print(f"✅ WordPress下書き投稿完了!")
            print(f"   投稿ID: {post_id}")
            print(f"   タイトル: {title}")
            print(f"   確認URL: {wp_url}/wp-admin/post.php?post={post_id}&action=edit")

            # ステータスをwp-postedに更新
            with open(md_file_path, 'r') as f:
                file_content = f.read()
            file_content = file_content.replace('status: draft', f'status: wp-posted\nwp_post_id: {post_id}')
            with open(md_file_path, 'w') as f:
                f.write(file_content)

    except URLError as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使い方: python3 scripts/post-to-wp.py [記事ファイルパス]")
        sys.exit(1)
    post_to_wordpress(sys.argv[1])
