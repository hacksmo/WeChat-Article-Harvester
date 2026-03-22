import os
import re
import json
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import markdown
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).parent.parent
ARTICLES_ROOT = ROOT_DIR / "WeChatArticles"
PDF_ROOT = ROOT_DIR / "WeChatPDFs"
STATIC_DIR = ROOT_DIR / "static"


def _normalize(s: str) -> str:
    return ''.join(s.split())


def _resolve_account_name(account_name: str) -> str:
    if not ARTICLES_ROOT.exists():
        return account_name
    for folder in ARTICLES_ROOT.iterdir():
        if folder.is_dir() and (_normalize(folder.name) == _normalize(account_name)):
            return folder.name
    return account_name


def normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.strip()
    title = re.sub(r'[<>:"/\\|?*]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title


def resolve_image_paths(md_content: str, article_dir: str) -> str:
    img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'

    def replace_img(match):
        alt_text = match.group(1)
        img_path = match.group(2)

        if img_path.startswith(('http://', 'https://', 'data:')):
            return match.group(0)

        full_path = os.path.join(article_dir, img_path)

        if os.path.exists(full_path):
            try:
                with open(full_path, 'rb') as f:
                    img_data = f.read()

                ext = os.path.splitext(img_path)[1].lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mime_type = mime_types.get(ext, 'image/jpeg')
                b64_data = base64.b64encode(img_data).decode('utf-8')
                return f'![{alt_text}](data:{mime_type};base64,{b64_data})'
            except Exception:
                return match.group(0)

        return match.group(0)

    return re.sub(img_pattern, replace_img, md_content)


def parse_markdown(md_content: str) -> Dict[str, str]:
    result = {
        'title': '',
        'author': '',
        'date': '',
        'content': md_content
    }

    lines = md_content.split('\n')
    content_lines = []
    past_header = False

    for line in lines:
        if line.startswith('# '):
            if not result['title']:
                result['title'] = line[2:].strip()
            past_header = True
        elif '**作者**' in line and ':' in line:
            match = re.search(r'\*\*作者\*\*\s*:\s*(.+)', line)
            if match:
                result['author'] = match.group(1).strip()
            past_header = True
        elif '**发布日期**' in line and ':' in line:
            match = re.search(r'\*\*发布日期\*\*\s*:\s*(.+)', line)
            if match:
                result['date'] = match.group(1).strip()
            past_header = True
        elif line.strip() == '---' and not past_header:
            past_header = True
        elif past_header:
            content_lines.append(line)
        else:
            past_header = True
            content_lines.append(line)

    result['content'] = '\n'.join(content_lines).strip()

    while result['content'].startswith('---') or result['content'].startswith('\n---'):
        result['content'] = result['content'].lstrip('-').lstrip('\n').strip()

    if not result['title']:
        result['title'] = '无标题文章'

    return result


def generate_html(article_info: Dict[str, str], stylesheet: str = "") -> str:
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'codehilite'])

    content_html = md.convert(article_info['content'])

    meta_parts = []
    if article_info['author']:
        meta_parts.append(f'<span class="author">作者: {article_info["author"]}</span>')
    if article_info['date']:
        meta_parts.append(f'<span class="date">发布日期: {article_info["date"]}</span>')

    meta_html = ''
    if meta_parts:
        meta_html = f'<div class="article-meta">{" | ".join(meta_parts)}</div>'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article_info['title']}</title>
    <style>
        {stylesheet}
    </style>
</head>
<body>
    <div class="article-title">{article_info['title']}</div>
    {meta_html}

    <hr>

    <div class="article-content">
        {content_html}
    </div>
</body>
</html>'''

    return html


def find_markdown_file(article_dir: str) -> Optional[str]:
    for f in os.listdir(article_dir):
        if f.endswith('.md'):
            return os.path.join(article_dir, f)
    return None


def _load_stylesheet() -> str:
    css_path = STATIC_DIR / "pdf_styles.css"
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def convert_to_pdf(
    article_dir: str,
    output_dir: Path,
    stylesheet: str,
    source_name: str = ''
) -> Tuple[bool, str]:
    md_file = find_markdown_file(article_dir)
    if not md_file:
        return False, "未找到 Markdown 文件"

    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        md_content = resolve_image_paths(md_content, article_dir)

        article_info = parse_markdown(md_content)
        article_info['source'] = source_name

        html_content = generate_html(article_info, stylesheet)

        folder_name = os.path.basename(article_dir)
        pdf_name = folder_name + '.pdf'
        pdf_path = output_dir / pdf_name

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')

            page.pdf(
                path=str(pdf_path),
                format='A4',
                margin={
                    'top': '2cm',
                    'bottom': '2cm',
                    'left': '2cm',
                    'right': '2cm'
                },
                print_background=True
            )
            browser.close()

        return True, ""

    except Exception as e:
        return False, str(e)


def process_articles(
    articles_dir: Path,
    output_dir: Path,
    stylesheet: str,
    overwrite: bool = False
) -> Dict[str, int]:
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0
    }

    if not articles_dir.exists():
        return stats

    account_name = articles_dir.parent.name

    for article_dir in sorted(articles_dir.iterdir()):
        if not article_dir.is_dir():
            continue

        md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
        if not md_files:
            continue

        stats['total'] += 1
        article_name = article_dir.name

        pdf_name = article_name + '.pdf'
        pdf_path = output_dir / pdf_name

        if pdf_path.exists() and not overwrite:
            stats['skipped'] += 1
            continue

        print(f"  [{stats['total']}] {article_name}", end=' ... ')

        success, error = convert_to_pdf(
            str(article_dir),
            output_dir,
            stylesheet,
            account_name
        )

        if success:
            stats['success'] += 1
            print("OK")
        else:
            stats['failed'] += 1
            print(f"FAIL ({error})")

    return stats


def export_pdf(account_name: str, overwrite: bool = False) -> Dict[str, int]:
    stylesheet = _load_stylesheet()
    actual_name = _resolve_account_name(account_name)

    account_dir = ARTICLES_ROOT / actual_name
    articles_dir = account_dir / "articles"
    account_pdfs = PDF_ROOT / actual_name
    account_pdfs.mkdir(parents=True, exist_ok=True)

    print(f"\n文章目录: {articles_dir}")
    print(f"PDF输出:  {account_pdfs}")

    return process_articles(articles_dir, account_pdfs, stylesheet, overwrite)


def export_pdf_all(overwrite: bool = False) -> Dict[str, int]:
    stylesheet = _load_stylesheet()

    if not ARTICLES_ROOT.exists():
        print(f"[!] 目录不存在: {ARTICLES_ROOT}")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    accounts = [d.name for d in ARTICLES_ROOT.iterdir() if d.is_dir()]

    if not accounts:
        print("[!] 没有找到已采集的公众号")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    print(f"\n找到 {len(accounts)} 个公众号: {', '.join(accounts)}")
    print(f"PDF统一输出目录: {PDF_ROOT}\n")

    overall = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    for account_name in accounts:
        print(f"\n{'='*50}")
        print(f"正在转换: {account_name}")
        print(f"{'='*50}")

        actual_name = _resolve_account_name(account_name)
        account_articles = ARTICLES_ROOT / actual_name / "articles"
        account_pdfs = PDF_ROOT / actual_name
        account_pdfs.mkdir(parents=True, exist_ok=True)

        stats = process_articles(account_articles, account_pdfs, stylesheet, overwrite)

        overall['total'] += stats['total']
        overall['success'] += stats['success']
        overall['failed'] += stats['failed']
        overall['skipped'] += stats['skipped']

        print(f"  小计: 成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}")

    return overall
