#!/usr/bin/env python3
"""
WordPress REST API 投稿ヘルパー
使い方: python3 wp_api_post.py <md_file> <gutenberg_file>
環境変数: WP_URL, WP_USER, WP_APP_PASS
"""
import sys
import json
import os
import ssl
import base64
import re
import urllib.request
import urllib.parse
import urllib.error


def _ssl_context():
    """certifi があれば使い、なければシステム証明書で SSL コンテキストを作る"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def auth_headers(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def api_get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=_ssl_context()) as resp:
        return json.load(resp)


def api_post(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, context=_ssl_context()) as resp:
        return json.load(resp)


def get_category_id(wp_url, headers, slug):
    """カテゴリslugからIDを取得"""
    url = f"{wp_url}/wp-json/wp/v2/categories?slug={urllib.parse.quote(slug)}&per_page=5"
    cats = api_get(url, headers)
    return cats[0]["id"] if cats else None


def get_or_create_tag(wp_url, headers, name):
    """タグ名からIDを取得、なければ作成"""
    name = name.strip()
    if not name:
        return None
    url = f"{wp_url}/wp-json/wp/v2/tags?search={urllib.parse.quote(name)}&per_page=20"
    tags = api_get(url, {k: v for k, v in headers.items() if k != "Content-Type"})
    for tag in tags:
        if tag["name"] == name:
            return tag["id"]
    result = api_post(f"{wp_url}/wp-json/wp/v2/tags", headers, {"name": name})
    return result["id"]


def detect_category_slug(md_file):
    """ファイルパスからカテゴリslugを判定"""
    path = md_file.replace("\\", "/")
    for slug in ["meo", "lawyer", "subsidy", "subsidy-national", "subsidy-job", "subsidy-startup"]:
        if f"/{slug}/" in path:
            return slug
    return None


def parse_frontmatter(md_file):
    """YAMLフロントマターをパース"""
    meta = {}
    with open(md_file, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta


def main():
    if len(sys.argv) < 3:
        print("Usage: wp_api_post.py <md_file> <gutenberg_file>", file=sys.stderr)
        sys.exit(1)

    md_file = sys.argv[1]
    gutenberg_file = sys.argv[2]

    wp_url  = os.environ.get("WP_URL", "").rstrip("/")
    user    = os.environ.get("WP_USER", "")
    pw      = os.environ.get("WP_APP_PASS", "")

    if not all([wp_url, user, pw]):
        print("ERROR: WP_URL / WP_USER / WP_APP_PASS が未設定", file=sys.stderr)
        sys.exit(1)

    headers = auth_headers(user, pw)

    # Gutenberg HTML 読み込み
    with open(gutenberg_file, encoding="utf-8") as f:
        content = f.read()

    # フロントマター取得
    meta = parse_frontmatter(md_file)
    title    = meta.get("title", "")
    meta_desc = meta.get("meta_description", "")
    keyword  = meta.get("keyword", "")
    tags_str = meta.get("tags", "")
    slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", os.path.basename(md_file).replace(".md", ""))

    # カテゴリID取得
    cat_slug = detect_category_slug(md_file)
    cat_ids = []
    if cat_slug:
        cat_id = get_category_id(wp_url, headers, cat_slug)
        if cat_id:
            cat_ids = [cat_id]

    # タグID取得／作成
    tag_ids = []
    if tags_str:
        for tag_name in tags_str.split(","):
            try:
                tid = get_or_create_tag(wp_url, headers, tag_name)
                if tid:
                    tag_ids.append(tid)
            except Exception:
                pass

    # 投稿作成
    payload = {
        "title":      title,
        "content":    content,
        "slug":       slug,
        "status":     "draft",
        "meta": {
            "_aioseo_description": meta_desc,
            "_aioseo_keywords":    keyword,
        },
    }
    if cat_ids:
        payload["categories"] = cat_ids
    if tag_ids:
        payload["tags"] = tag_ids

    try:
        result = api_post(f"{wp_url}/wp-json/wp/v2/posts", headers, payload)
        print(result["id"])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
