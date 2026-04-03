#!/usr/bin/env python3
"""
Markdown → WordPress Gutenberg ブロック形式 変換スクリプト
使い方: python3 scripts/md_to_gutenberg.py input.md > output.html
"""
import re
import sys


def apply_inline(text):
    """インライン要素の変換"""
    # **bold**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # *italic*
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # `code`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def build_table(table_lines):
    """Markdown テーブル → wp:table ブロック"""
    rows = []
    for line in table_lines:
        # セパレータ行をスキップ (|---|---|)
        if re.match(r'^\|[\s\-\|:]+\|$', line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)

    if not rows:
        return ''

    thead_cells = ''.join(f'<th>{apply_inline(c)}</th>' for c in rows[0])
    thead = f'<thead><tr>{thead_cells}</tr></thead>'

    tbody_rows = ''
    for row in rows[1:]:
        cells = ''.join(f'<td>{apply_inline(c)}</td>' for c in row)
        tbody_rows += f'<tr>{cells}</tr>'
    tbody = f'<tbody>{tbody_rows}</tbody>' if tbody_rows else ''

    return (
        '<!-- wp:table -->\n'
        f'<figure class="wp-block-table"><table>{thead}{tbody}</table></figure>\n'
        '<!-- /wp:table -->'
    )


def md_to_gutenberg(md):
    lines = md.split('\n')
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # H1（記事タイトルはWPのpost_titleで設定済みなのでスキップ）
        if re.match(r'^# [^#]', line):
            i += 1
            continue

        # H2
        if line.startswith('## '):
            text = apply_inline(line[3:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":2}} -->\n'
                f'<h2 class="wp-block-heading">{text}</h2>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # H3
        if line.startswith('### '):
            text = apply_inline(line[4:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":3}} -->\n'
                f'<h3 class="wp-block-heading">{text}</h3>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # H4
        if line.startswith('#### '):
            text = apply_inline(line[5:].strip())
            blocks.append(
                f'<!-- wp:heading {{"level":4}} -->\n'
                f'<h4 class="wp-block-heading">{text}</h4>\n'
                f'<!-- /wp:heading -->'
            )
            i += 1
            continue

        # 区切り線
        if line.strip() in ('---', '***', '___'):
            blocks.append(
                '<!-- wp:separator -->\n'
                '<hr class="wp-block-separator has-alpha-channel-opacity"/>\n'
                '<!-- /wp:separator -->'
            )
            i += 1
            continue

        # テーブル
        if '|' in line and i + 1 < len(lines) and re.match(r'^\|[\s\-\|:]+\|', lines[i + 1]):
            table_lines = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            block = build_table(table_lines)
            if block:
                blocks.append(block)
            continue

        # 番号なしリスト
        if re.match(r'^[-*] ', line):
            items = []
            while i < len(lines) and re.match(r'^[-*] ', lines[i]):
                item = apply_inline(lines[i][2:].strip())
                items.append(f'<!-- wp:list-item --><li>{item}</li><!-- /wp:list-item -->')
                i += 1
            items_html = '\n'.join(items)
            blocks.append(
                f'<!-- wp:list -->\n'
                f'<ul class="wp-block-list">{items_html}</ul>\n'
                f'<!-- /wp:list -->'
            )
            continue

        # 番号付きリスト
        if re.match(r'^\d+\. ', line):
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                item = apply_inline(re.sub(r'^\d+\. ', '', lines[i]).strip())
                items.append(f'<!-- wp:list-item --><li>{item}</li><!-- /wp:list-item -->')
                i += 1
            items_html = '\n'.join(items)
            blocks.append(
                f'<!-- wp:list {{"ordered":true}} -->\n'
                f'<ol class="wp-block-list">{items_html}</ol>\n'
                f'<!-- /wp:list -->'
            )
            continue

        # 引用ブロック
        if line.startswith('> '):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('> '):
                quote_lines.append(lines[i][2:])
                i += 1
            text = apply_inline(' '.join(quote_lines))
            blocks.append(
                f'<!-- wp:quote -->\n'
                f'<blockquote class="wp-block-quote"><p>{text}</p></blockquote>\n'
                f'<!-- /wp:quote -->'
            )
            continue

        # コードブロック
        if line.startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # closing ```
            code = '\n'.join(code_lines)
            blocks.append(
                f'<!-- wp:code -->\n'
                f'<pre class="wp-block-code"><code>{code}</code></pre>\n'
                f'<!-- /wp:code -->'
            )
            continue

        # 空行
        if line.strip() == '':
            i += 1
            continue

        # 段落（複数行をまとめる）
        para_lines = []
        while i < len(lines):
            l = lines[i]
            if (l.strip() == '' or l.startswith('#') or re.match(r'^[-*] ', l)
                    or re.match(r'^\d+\. ', l) or l.startswith('> ')
                    or l.startswith('```') or l.strip() in ('---', '***', '___')
                    or ('|' in l and i + 1 < len(lines) and re.match(r'^\|[\s\-\|:]+\|', lines[i + 1] if i + 1 < len(lines) else ''))):
                break
            para_lines.append(l)
            i += 1

        if para_lines:
            text = apply_inline('<br>'.join(para_lines))
            blocks.append(
                f'<!-- wp:paragraph -->\n'
                f'<p>{text}</p>\n'
                f'<!-- /wp:paragraph -->'
            )

    return '\n\n'.join(blocks)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使い方: python3 md_to_gutenberg.py input.md', file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        content = f.read()

    # YAMLフロントマターを除去
    content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

    # 関連記事TODOプレースホルダーを除去（記事が揃うまで非表示）
    content = re.sub(r'\[関連記事: TODO[^\]]*\]\n?', '', content)

    print(md_to_gutenberg(content))
