import os
import sys
import json
import time
import random
import shutil
import subprocess
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from bs4 import BeautifulSoup

ROOT_DIR = "WeChatArticles"
M2W_PATH = "./m2w"

def get_account_dir(account_name: str) -> Path:
    return Path(ROOT_DIR) / account_name

def get_account_articles_dir(account_name: str) -> Path:
    return get_account_dir(account_name) / "articles"

def get_account_data_file(account_name: str) -> Path:
    return get_account_dir(account_name) / "data.json"


SESSION_FILE = "wechat_session.json"


def _load_session_cookie() -> str:
    """从session文件自动加载cookie"""
    try:
        session_file = Path(SESSION_FILE)
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie = data.get('cookie', '')
            if cookie:
                return cookie
    except Exception:
        pass
    return ''


class ArticleDownloader:
    def __init__(
        self,
        cookie: str = "",
        m2w_path: str = M2W_PATH,
        min_interval: int = 3,
        max_interval: int = 5
    ):
        if not cookie:
            cookie = _load_session_cookie()
        self.cookie = cookie
        self.m2w_path = m2w_path
        self.root_dir = Path(ROOT_DIR)
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.session = requests.Session()
        
        self.root_dir.mkdir(parents=True, exist_ok=True)
    
    def set_cookie(self, cookie: str):
        self.cookie = cookie
    
    def _sanitize_filename(self, filename: str) -> str:
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        return filename[:100]
    
    def _wait(self, verification_hit: bool = False):
        if verification_hit:
            interval = random.uniform(30, 60)
            print(f"    ⏰ 风控触发，等待 {int(interval)} 秒...")
        else:
            interval = random.uniform(self.min_interval, self.max_interval)
        time.sleep(interval)
    
    def _check_m2w(self) -> bool:
        if not os.path.exists(self.m2w_path):
            return False
        return True

    def _verify_md_content(self, article_dir: Path) -> bool:
        """验证下载的markdown内容是否正常（大于500字节）"""
        md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
        if not md_files:
            return False
        return md_files[0].stat().st_size >= 500

    def _download_with_webfetch(self, url: str, article_dir: Path, title: str = '') -> tuple:
        """通过webfetch API下载文章内容（第三层兜底）"""
        try:
            import urllib.request
            import urllib.parse
            
            api_url = "https://autoglm-api.zhipuai.cn/agentdr/v1/assistant/skills/open-link"
            
            token_url = "http://127.0.0.1:53699/get_token"
            try:
                req = urllib.request.Request(token_url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    token = resp.read().decode()
            except Exception:
                return (False, 'webfetch_unavailable', 'webfetch服务未运行，请开启AutoGLM扩展')
            
            auth = token if token.startswith('Bearer ') else f'Bearer {token}'
            
            post_data = urllib.parse.urlencode({'url': url}).encode()
            req = urllib.request.Request(
                api_url,
                data=post_data,
                headers={
                    'Authorization': auth,
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                import json
                data = json.loads(resp.read().decode())
            
            text = data.get('data', {}).get('text', '')
            if not text:
                return (False, 'webfetch', 'webfetch返回内容为空')
            
            md_content = f"# {title}\n\n" if title else "# 无标题\n\n"
            md_content += text
            
            md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
            if md_files:
                md_file = md_files[0]
            else:
                md_file = article_dir / f"{article_dir.name}.md"
            
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            return (True, 'webfetch', '')
            
        except Exception as e:
            return (False, 'webfetch', f'webfetch异常: {str(e)[:80]}')
    
    def download_single(self, url: str, save_dir: Path, title: str = '', publish_date: str = '') -> tuple:
        folder_name = self._sanitize_filename(title) if title else 'article'
        if publish_date:
            folder_name = f"{publish_date}_{folder_name}"
        
        article_dir = save_dir / folder_name
        article_dir.mkdir(parents=True, exist_ok=True)
        
        if self.cookie:
            return self._download_with_http(url, article_dir, title, publish_date)
        elif self._check_m2w():
            success, err = self._download_with_m2w(url, article_dir)
            return (success, 'm2w', err if err else '使用m2w下载成功')
        else:
            return (False, 'no_method', '无可用下载方式')
    
    def _download_with_m2w(self, url: str, article_dir: Path) -> tuple:
        try:
            cmd = [self.m2w_path, url, str(article_dir), '--image=save']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return (False, f'm2w exit {result.returncode}: {result.stderr[:100]}')
            
            md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
            if not md_files:
                return (False, 'm2w未生成markdown文件')
            
            md_file = md_files[0]
            size = md_file.stat().st_size
            
            if size < 500:
                return (False, f'markdown内容过少({size}B)，可能被隐藏内容')
            
            return (True, '')
            
        except Exception as e:
            return (False, str(e))
    
    def _download_with_http(self, url: str, article_dir: Path, title: str = '', publish_date: str = '') -> tuple:
        try:
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://mp.weixin.qq.com/',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            resp = self.session.get(url, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                return (False, 'http_error', f'HTTP {resp.status_code}')
            
            content = resp.text
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 先检查是否有标准文章内容
            content_elem = soup.find('div', id='js_content')
            if not content_elem:
                content_elem = soup.find('div', class_='rich_media_content')
            
            # 如果有内容，说明可以下载
            if content_elem:
                if not self._parse_and_save(content, article_dir, title, publish_date):
                    return (False, 'parse_error', '解析保存失败')
                return (True, 'success', '')
            
            # 没有标准内容，检查原因
            if '环境异常' in content or '系统繁忙' in content:
                return (False, 'verification', '触发风控，需要验证')
            
            if '网页不存在' in content or 'dead' in content.lower():
                return (False, 'deleted', '文章已被删除')
            
            # 检查是否外部链接/小程序
            if soup.find('div', class_='mp_profile_iframe') or 'mp_profile_iframe' in content:
                return (False, 'external', '外部链接/小程序内容')
            
            return (False, 'unknown', '无法解析文章内容')
            if not content_elem:
                content_elem = soup.find('div', class_='rich_media_content')
            
            if not content_elem:
                # 检查是否是外链文章
                if 'mp_profile_iframe' in content or '小程序' in content:
                    return (False, 'external', '外部链接/小程序内容，无法直接下载')
                return (False, 'unknown', '无法解析文章内容')
            
            if not self._parse_and_save(content, article_dir, title, publish_date):
                return (False, 'parse_error', '解析保存失败')
            
            return (True, 'success', '')
            
        except Exception as e:
            return (False, 'exception', f'请求异常: {str(e)[:50]}')
    
    def _parse_and_save(self, html: str, article_dir: Path, title: str = '', publish_date: str = '') -> bool:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            if not title:
                title_elem = soup.find('h1', class_='rich_media_title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            author_elem = soup.find('a', class_='rich_media_meta rich_media_meta_link rich_media_meta_nickname')
            if not author_elem:
                author_elem = soup.find('span', class_='rich_media_meta rich_media_meta_nickname')
            author = author_elem.get_text(strip=True) if author_elem else ''
            
            # 优先使用传入的 publish_date，否则尝试从页面提取
            date_str = publish_date
            if not date_str:
                date_elem = soup.find('em', id='publish_time')
                if not date_elem:
                    date_elem = soup.find('span', class_='rich_media_meta rich_media_meta_text')
                date_str = date_elem.get_text(strip=True) if date_elem else ''
            
            content_elem = soup.find('div', id='js_content')
            if not content_elem:
                content_elem = soup.find('div', class_='rich_media_content')
            if not content_elem:
                content_elem = soup.find('div', class_='weui-article')
            if not content_elem:
                content_elem = soup.find('div', id='img-content')
            
            if not content_elem:
                # Fallback: try to extract any text content
                main_content = soup.find('div', class_='rich_media_inner')
                if main_content:
                    content_elem = main_content
            
            md_content = ""
            img_count = 0
            
            if content_elem:
                for img in content_elem.find_all('img'):
                    original_src = img.get('data-src') or img.get('src', '')
                    if 'mmbiz.qpic.cn' in original_src or 'weixin.qq.com' in original_src or 'mmecoa' in original_src:
                        img_count += 1
                        local_name = f"img_{img_count:03d}.jpg"
                        local_path = article_dir / local_name
                        self._download_image(original_src, local_path)
                        img['src'] = local_name
                        if img.get('data-src'):
                            img['data-src'] = local_name
                
                md_content = self._html_to_markdown(str(content_elem))
            else:
                # No standard content found - might be external link or special content
                print(f"[⚠️] 无法解析标准内容，可能是外链或特殊格式")
                md_content = "> 此文章为外链或小程序内容，无法直接下载\\n> 请访问原文查看"
            
            # 文件名包含日期
            safe_title = self._sanitize_filename(title)[:50] if title else 'article'
            if date_str:
                md_filename = f"{date_str}_{safe_title}.md"
            else:
                md_filename = f"{safe_title}.md"
            md_file = article_dir / md_filename
            
            with open(md_file, 'w', encoding='utf-8') as f:
                if title:
                    f.write(f"# {title}\n\n")
                if author:
                    f.write(f"**作者**: {author}\n\n")
                if date_str:
                    f.write(f"**发布日期**: {date_str}\n\n")
                f.write("---\n\n")
                f.write(md_content)
            
            return True
            
        except Exception as e:
            print(f"[❌] 解析失败: {e}")
            return False
    
    def _download_image(self, url: str, save_path: Path) -> bool:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://mp.weixin.qq.com/',
            }
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                return True
        except:
            pass
        return False
    
    def _html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        
        for tag in soup.find_all(['style', 'script', 'xml']):
            tag.decompose()
        
        lines = []
        for elem in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'blockquote', 'li']):
            text = elem.get_text(strip=True)
            if not text:
                continue
            
            if elem.name in ['h1', 'h2', 'h3', 'h4']:
                level = elem.name[1]
                lines.append(f"\n{'#' * int(level)} {text}\n")
            elif elem.name == 'blockquote':
                lines.append(f"\n> {text}\n")
            elif elem.name == 'li':
                lines.append(f"- {text}\n")
            else:
                lines.append(text + "\n\n")
        
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src', '')
            alt = img.get('alt', 'image')
            if src:
                lines.append(f"![{alt}]({src})\n")
        
        result = '\n'.join(lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
    
    def download_articles(
        self,
        account_name: str,
        articles: list,
        scope: str = 'all',
        limit: int = 100,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        if not self._check_m2w() and not self.cookie:
            print("[❌] 没有可用的下载方式（m2w工具或Cookie）")
            return {'success': 0, 'failed': 0, 'skipped': 0}

        has_cookie = bool(self.cookie)
        
        account_dir = get_account_articles_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)
        
        filtered_articles = self._filter_articles(articles, scope, limit)
        
        success = 0
        failed = 0
        skipped = 0
        
        total = len(filtered_articles)
        
        for i, article in enumerate(filtered_articles):
            title = article.get('title', 'untitled')
            url = article.get('url', '')
            
            if not url:
                article['remark'] = '无URL'
                print(f"[⚠️] 文章 {i+1}/{total}: 无URL，跳过")
                continue
            
            if article.get('downloaded') and article.get('local_path'):
                print(f"[⏭️] 文章 {i+1}/{total}: 已下载，跳过 - {title[:30]}...")
                skipped += 1
                continue
            publish_date = article.get('publish_date', '')[:10]
            
            print(f"\n[📥] [{i+1}/{total}] 正在下载: {title[:40]}...")

            result, reason_code, reason_msg = self.download_single(url, account_dir, title, publish_date)
            
            folder_name = self._sanitize_filename(title)[:50]
            if publish_date:
                folder_name = f"{publish_date}_{folder_name}"
            article_dir = account_dir / folder_name
            
            if result and not self._verify_md_content(article_dir):
                import shutil
                if has_cookie:
                    print(f"[⚠️] m2w内容过少，尝试HTTP...")
                    if article_dir.exists():
                        shutil.rmtree(article_dir)
                    article_dir.mkdir(parents=True, exist_ok=True)
                    result, reason_code, reason_msg = self._download_with_http(url, article_dir, title, publish_date)
                    if not self._verify_md_content(article_dir):
                        print(f"[⚠️] HTTP内容也过少，尝试webfetch...")
                        if article_dir.exists():
                            shutil.rmtree(article_dir)
                        article_dir.mkdir(parents=True, exist_ok=True)
                        result, reason_code, reason_msg = self._download_with_webfetch(url, article_dir, title)
                else:
                    print(f"[⚠️] m2w内容过少，尝试webfetch...")
                    if article_dir.exists():
                        shutil.rmtree(article_dir)
                    article_dir.mkdir(parents=True, exist_ok=True)
                    result, reason_code, reason_msg = self._download_with_webfetch(url, article_dir, title)
            
            if result and not self._verify_md_content(article_dir):
                result = False
                reason_msg = '所有下载方式内容都过少，文章可能被限制'
            
            if result:
                article['downloaded'] = True
                article['local_path'] = str(article_dir)
                article['downloaded_at'] = datetime.now().isoformat()
                article['remark'] = ''
                success += 1
                
                md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
                if md_files:
                    md_file = md_files[0]
                    print(f"[✅] 已保存: {md_file.name} ({md_file.stat().st_size} bytes)")
            else:
                article['downloaded'] = False
                article['remark'] = reason_msg
                
                if reason_code == 'verification':
                    print(f"[⚠️] 需要验证/风控: {reason_msg}")
                    self._wait(verification_hit=True)
                elif reason_code == 'deleted':
                    print(f"[❌] 文章被删/违规: {reason_msg}")
                elif reason_code == 'external':
                    print(f"[⚠️] 外部链接: {reason_msg}")
                elif reason_code == 'webfetch_unavailable':
                    print(f"[⚠️] {reason_msg}")
                else:
                    print(f"[❌] 下载失败: {reason_msg}")
                failed += 1
            
            if progress_callback:
                progress_callback(i + 1, total, article)
            
            if reason_code != 'verification':
                self._wait()
        
        return {
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'total': total
        }
    
    def _filter_articles(self, articles: list, scope: str, limit: int) -> list:
        if scope == 'custom':
            return articles[:limit]
        return articles
    
    def update_json_file(self, account_name: str, articles: list):
        json_file = get_account_data_file(account_name)
        
        if not json_file.exists():
            print(f"[⚠️] 未找到JSON文件: {json_file}")
            return
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        existing_titles = {a.get('title'): a for a in data.get('articles', [])}
        
        for article in articles:
            title = article.get('title')
            if title in existing_titles:
                existing_titles[title].update(article)
        
        data['articles'] = list(existing_titles.values())
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[💾] JSON文件已更新: {json_file}")
    
    def get_downloaded_status(self, account_name: str) -> dict:
        json_file = get_account_data_file(account_name)
        
        if not json_file.exists():
            return {'total': 0, 'downloaded': 0}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        total = len(articles)
        downloaded = sum(1 for a in articles if a.get('downloaded'))
        
        return {'total': total, 'downloaded': downloaded}
    
    def cleanup_empty_folders(self, account_name: str) -> list:
        """
        清理公众号下的空文件夹
        
        Returns:
            被删除的空文件夹列表
        """
        account_dir = get_account_articles_dir(account_name)
        if not account_dir.exists():
            return []
        
        deleted_folders = []
        
        for item in account_dir.iterdir():
            if item.is_dir():
                files = list(item.iterdir())
                if len(files) == 0:
                    deleted_folders.append(str(item))
                    item.rmdir()
                    print(f"[🗑️] 删除空文件夹: {item.name}")
        
        return deleted_folders
    
    def cleanup_and_export_deleted(self, account_name: str) -> dict:
        """
        清理空文件夹并导出删除的文章信息
        
        Returns:
            {
                'deleted_folders': list of deleted folder paths,
                'deleted_articles': list of deleted article info
            }
        """
        deleted_folders = self.cleanup_empty_folders(account_name)
        
        json_file = get_account_data_file(account_name)
        deleted_articles = []
        
        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for article in data.get('articles', []):
                if article.get('downloaded'):
                    local_path = article.get('local_path')
                    if local_path and not Path(local_path).exists():
                        article['downloaded'] = False
                        article['remark'] = '文件夹已删除'
                        deleted_articles.append({
                            'title': article.get('title', ''),
                            'url': article.get('url', ''),
                            'publish_date': article.get('publish_date', ''),
                            'remark': '文件夹已删除'
                        })
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {
            'deleted_folders': deleted_folders,
            'deleted_articles': deleted_articles
        }


def main():
    account_name = input("请输入公众号名称: ").strip()
    if not account_name:
        return
    
    downloader = ArticleDownloader()
    
    json_file = get_account_data_file(account_name)
    if not json_file.exists():
        print(f"[❌] 未找到文章列表，请先采集文章")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    articles = data.get('articles', [])
    
    print(f"\n[📋] 共 {len(articles)} 篇文章")
    print(f"[📁] 保存目录: {get_account_articles_dir(account_name)}")
    
    result = downloader.download_articles(account_name, articles)
    
    downloader.update_json_file(account_name, articles)
    
    print(f"\n{'='*50}")
    print(f"[📊] 下载统计:")
    print(f"  - 成功: {result['success']}")
    print(f"  - 失败: {result['failed']}")
    print(f"  - 跳过: {result['skipped']}")


if __name__ == "__main__":
    main()
