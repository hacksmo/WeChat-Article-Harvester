import os
import json
import time
import re
import requests
import random
from datetime import datetime, timedelta
from pathlib import Path
from dateutil import parser as date_parser
from urllib.parse import urlparse, parse_qs

ROOT_DIR = "WeChatArticles"

def get_account_dir(account_name: str) -> Path:
    """获取公众号根目录"""
    return Path(ROOT_DIR) / account_name

def get_account_articles_dir(account_name: str) -> Path:
    """获取公众号文章目录"""
    return get_account_dir(account_name) / "articles"

def get_account_data_file(account_name: str) -> Path:
    """获取公众号JSON文件路径"""
    return get_account_dir(account_name) / "data.json"


def check_article_status(url: str, cookie: str = "", timeout: int = 15) -> tuple:
    """
    检测文章是否可访问 (使用 GET 请求检查页面内容)
    
    Args:
        url: 文章URL
        cookie: 微信登录Cookie
        timeout: 请求超时时间(秒)
        
    Returns:
        (is_available: bool, reason: str)
        - is_available: True 表示文章可访问, False 表示已删除/不可访问
        - reason: 状态原因
    """
    if not url:
        return (False, "URL为空")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        if cookie:
            headers['Cookie'] = cookie
        
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        content = resp.text
        
        if resp.status_code == 404:
            return (False, "404-文章已被删除")
        
        if resp.status_code >= 500:
            return (False, f"{resp.status_code}-服务器错误")
        
        content_lower = content.lower()
        
        if '网页不存在' in content or 'page not found' in content_lower:
            return (False, "页面不存在")
        
        if 'ghost' in content_lower:
            return (False, "ghost-文章已失效")
        
        if '"errmsg":"dead"' in content:
            return (False, "dead-文章已失效")
        
        if 'mp_profile_iframe' in content and len(content) < 5000:
            return (False, "外部链接/小程序")
        
        if '此内容因违规无法显示' in content or '内容无法显示' in content:
            return (False, "内容违规被屏蔽")
        
        if 'rich_media_content' not in content and '#js_content' not in content:
            if '链接不存在' in content or '内容已删除' in content or '已失效' in content:
                return (False, "文章内容已失效")
            if len(content) < 10000:
                return (False, "无法获取文章内容")
        
        return (True, "")
        
    except requests.exceptions.Timeout:
        return (False, "请求超时")
    except requests.exceptions.ConnectionError:
        return (False, "连接失败")
    except Exception as e:
        return (False, f"检测异常:{str(e)[:30]}")

class ArticleFetcher:
    def __init__(self, login_module):
        self.login = login_module
        self.base_url = "https://mp.weixin.qq.com"
        self.session = requests.Session()
        self.data_dir = Path(ROOT_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_headers(self) -> dict:
        return {
            'Cookie': self.login.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': f'{self.base_url}/cgi-bin/home'
        }
    
    def search_account(self, account_name: str) -> dict:
        print(f"\n[🔍] 搜索公众号: {account_name}")
        
        url = f"{self.base_url}/cgi-bin/searchbiz"
        params = {
            'action': 'search_biz',
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
            'token': self.login.token,
            'query': account_name
        }
        
        try:
            resp = self.session.get(url, params=params, headers=self.get_headers(), timeout=15)
            data = resp.json()
            
            if data.get('base_resp', {}).get('ret') == 0:
                list_data = data.get('list', [])
                if list_data:
                    account = list_data[0]
                    print(f"[✅] 找到公众号: {account.get('nickname', '')}")
                    return {
                        'fakeid': account.get('fakeid', ''),
                        'biz': account.get('biz', ''),
                        'nickname': account.get('nickname', ''),
                        'alias': account.get('alias', '')
                    }
            
            print(f"[❌] 未找到公众号: {account_name}")
            return None
            
        except Exception as e:
            print(f"[❌] 搜索失败: {e}")
            return None
    
    def fetch_article_list(self, fakeid: str, biz: str = '', max_count: int = 1000, cutoff: float = 0) -> list:
        print(f"\n[📋] 开始获取文章列表...")
        
        articles = []
        offset = 0
        count = 5
        
        while len(articles) < max_count:
            params = {
                'sub': 'list',
                'search_field': 'null',
                'begin': offset,
                'count': count,
                'query': '',
                'fakeid': fakeid,
                'type': '101_1',
                'free_publish_type': 1,
                'sub_action': 'list_ex',
                'token': self.login.token,
                'lang': 'zh_CN',
                'f': 'json',
                'ajax': 1,
            }
            
            try:
                print(f"  [📄] 获取文章列表 (偏移 {offset})...")
                url = f"{self.base_url}/cgi-bin/appmsgpublish"
                resp = self.session.get(url, params=params, headers=self.get_headers(), timeout=15)
                data = resp.json()
                
                base_resp = data.get('base_resp', {})
                if base_resp.get('ret') != 0:
                    print(f"  [❌] API返回错误: {base_resp.get('err_msg', 'unknown')}")
                    break
                
                publish_page = data.get('publish_page', {})
                if isinstance(publish_page, str):
                    publish_page = json.loads(publish_page)
                
                publish_list = publish_page.get('publish_list', [])
                
                if not publish_list:
                    print(f"  [📭] 没有更多文章了")
                    break
                
                oldest_ts = None
                for item in publish_list:
                    publish_info = item.get('publish_info', {})
                    if isinstance(publish_info, str):
                        publish_info = json.loads(publish_info)
                    
                    appmsgex = publish_info.get('appmsgex', [])
                    for article_data in appmsgex:
                        article = self._parse_publish_article(article_data)
                        if article:
                            ts = article.get('create_time', 0)
                            if oldest_ts is None or ts < oldest_ts:
                                oldest_ts = ts
                            articles.append(article)
                
                print(f"  [✅] 本次获取 {len(publish_list)} 条记录，累计 {len(articles)} 篇")
                
                if cutoff > 0 and oldest_ts and oldest_ts < cutoff:
                    print(f"  [🛑] 已到达截止时间，停止采集")
                    break
                
                offset += count
                time.sleep(2)
                
            except Exception as e:
                print(f"  [❌] 获取失败: {e}")
                break
        
        return articles
    
    def _get_appmsg_token(self) -> str:
        # 优先使用登录模块中已获取的 appmsg_token
        if self.login.appmsg_token:
            return self.login.appmsg_token
        
        # 如果没有，尝试从页面获取
        try:
            url = f"{self.base_url}/cgi-bin/appmsg"
            params = {
                'action': 'home',
                'token': self.login.token,
                'lang': 'zh_CN'
            }
            resp = self.session.get(url, params=params, headers=self.get_headers(), timeout=10)
            
            match = re.search(r'"appmsg_token"\s*:\s*"([^"]+)"', resp.text)
            if match:
                self.login.appmsg_token = match.group(1)
                return self.login.appmsg_token
        except:
            pass
        return ""
    
    def _parse_article(self, item: dict) -> dict:
        try:
            create_time_str = item.get('create_time', '0')
            if isinstance(create_time_str, str) and create_time_str.isdigit():
                create_time = int(create_time_str)
            else:
                create_time = 0
            
            if create_time:
                publish_date = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_date = ''
            
            # Try to get URL from multi_item
            content_url = ''
            multi_item = item.get('multi_item', [])
            if multi_item and isinstance(multi_item, list):
                mi = multi_item[0]
                content_url = mi.get('content_url', '')
                if not content_url:
                    content_url = mi.get('source_url', '')
                if content_url:
                    content_url = content_url.replace('\\/', '/').replace('\\', '')
            
            # Fallback to direct field
            if not content_url:
                content_url = item.get('content_url', '')
                if content_url:
                    content_url = content_url.replace('\\/', '/').replace('\\', '')
            
            aid = item.get('aid', '')
            file_id = item.get('file_id', '')
            
            return {
                'aid': aid,
                'file_id': file_id,
                'title': item.get('title', ''),
                'url': content_url,
                'digest': item.get('digest', ''),
                'author': item.get('author', ''),
                'publish_date': publish_date,
                'create_time': create_time,
                'cover': item.get('img_url', ''),
                'read_count': self._get_read_count(aid),
                'is_original': item.get('is_original', 0) == 1,
                'tags': [],
                'downloaded': False,
                'local_path': None,
                'downloaded_at': None
            }
        except Exception as e:
            print(f"  [⚠️] 解析文章失败: {e}")
            return None
    
    def _parse_publish_article(self, article_data: dict) -> dict:
        try:
            create_time = article_data.get('create_time', 0)
            if create_time:
                publish_date = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_date = ''
            
            link = article_data.get('link', '')
            if link:
                link = link.replace('\\/', '/').replace('\\', '')
            
            aid = article_data.get('aid', '')
            
            # 从链接中解析出关键参数
            biz, mid, sn, idx = '', '', '', ''
            if link:
                parsed_url = urlparse(link)
                query_params = parse_qs(parsed_url.query)
                biz = query_params.get('__biz', [''])[0]
                mid = query_params.get('mid', [''])[0]
                sn = query_params.get('sn', [''])[0]
                idx = query_params.get('idx', [''])[0]
            
            return {
                'aid': aid,
                'title': article_data.get('title', ''),
                'url': link,
                'biz': biz,
                'mid': mid,
                'sn': sn,
                'idx': idx,
                'digest': article_data.get('digest', ''),
                'author': article_data.get('author', ''),
                'publish_date': publish_date,
                'create_time': create_time,
                'cover': article_data.get('cover', ''),
                'read_count': 0,
                'like_count': 0,
                'is_original': False,
                'tags': [],
                'downloaded': False,
                'local_path': None,
                'downloaded_at': None
            }
        except Exception as e:
            print(f"  [⚠️] 解析文章失败: {e}")
            return None
    
    def fetch_read_counts(self, articles: list) -> tuple:
        if not self.login.appmsg_token:
            print("[❌] 缺少 appmsg_token，无法获取阅读量")
            return (0, 0, [])

        print("\n" + "="*50)
        print("📊 开始更新文章阅读量...")
        print("="*50)
        
        updated_count = 0
        failed_count = 0
        failed_articles = []
        
        total = len(articles)
        
        for i, article in enumerate(articles):
            # 跳过已获取阅读量的
            if article.get('read_count', 0) > 0 or article.get('like_count', 0) > 0:
                continue

            print(f"[{i+1}/{total}] 更新: {article.get('title', '')[:30]}...", end=" ", flush=True)

            try:
                url = f"{self.base_url}/mp/getappmsgext"
                params = {
                    'f': 'json',
                    'appmsg_token': self.login.appmsg_token,
                    'x5': '0'
                }
                data = {
                    'is_only_read': '1',
                    'is_temp_url': '0',
                    'appmsg_type': '9',
                    '__biz': article.get('biz', ''),
                    'mid': article.get('mid', ''),
                    'sn': article.get('sn', ''),
                    'idx': article.get('idx', ''),
                    'scene': '126',
                    'title': article.get('title', ''),
                    'ct': article.get('create_time', ''),
                }
                
                resp = self.session.post(
                    url, 
                    params=params, 
                    data=data, 
                    headers=self.get_headers(), 
                    timeout=15
                )
                
                if resp.status_code == 200:
                    read_data = resp.json()
                    if read_data.get('base_resp', {}).get('errmsg') == 'ok':
                        stats = read_data.get('appmsgstat', {})
                        article['read_count'] = stats.get('read_num', 0)
                        article['like_count'] = stats.get('like_num', 0)
                        print(f"✅ 读: {article['read_count']}, 赞: {article['like_count']}")
                        updated_count += 1
                    else:
                        print(f"❌ API错误: {read_data.get('base_resp', {}).get('errmsg', '未知')}")
                        failed_count += 1
                        failed_articles.append(article['title'])
                else:
                    print(f"❌ HTTP {resp.status_code}")
                    failed_count += 1
                    failed_articles.append(article['title'])
                
                # 严格控制频率
                time.sleep(random.uniform(8, 15))

            except Exception as e:
                print(f"❌ 请求异常: {e}")
                failed_count += 1
                failed_articles.append(article['title'])
                time.sleep(15)

        return (updated_count, failed_count, failed_articles)
    
    def save_articles(self, account_name: str, articles: list, biz: str = '', fakeid: str = '') -> str:
        account_dir = get_account_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)
        data_file = get_account_data_file(account_name)
        
        existing_articles = []
        if data_file.exists():
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                existing_articles = existing_data.get('articles', [])
            except Exception:
                existing_articles = []
        
        existing_keys = {a.get('url', '') or a.get('title', '') for a in existing_articles}

        merged = {}
        for a in existing_articles:
            key = a.get('url', '') or a.get('title', '')
            if key:
                merged[key] = a

        for a in articles:
            key = a.get('url', '') or a.get('title', '')
            if key and key not in existing_keys:
                merged[key] = a
        
        merged_list = list(merged.values())
        
        data = {
            'account_name': account_name,
            'biz': biz,
            'fakeid': fakeid,
            'fetched_at': datetime.now().isoformat(),
            'total_count': len(merged_list),
            'articles': merged_list
        }
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        new_count = len(articles)
        total_count = len(merged_list)
        print(f"\n[💾] 文章列表已保存: 本次获取 {new_count} 篇，合并后共 {total_count} 篇")
        return str(data_file)
    
    def save_deleted_articles(self, account_name: str, deleted_articles: list) -> str:
        """保存已删除的文章列表"""
        account_dir = get_account_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)
        
        deleted_file = account_dir / "deleted.json"
        
        data = {
            'account_name': account_name,
            'fetched_at': datetime.now().isoformat(),
            'deleted_count': len(deleted_articles),
            'deleted_articles': deleted_articles
        }
        
        with open(deleted_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[🗑️] 已删除文章已记录到: {deleted_file}")
        return str(deleted_file)
    
    def load_deleted_articles(self, account_name: str) -> dict:
        """加载已删除的文章列表"""
        deleted_file = get_account_dir(account_name) / "deleted.json"
        
        if not deleted_file.exists():
            return None
        
        with open(deleted_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_articles(self, account_name: str) -> dict:
        data_file = get_account_data_file(account_name)
        
        if not data_file.exists():
            print(f"[❌] 未找到文章列表: {data_file}")
            return None
        
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def fetch_with_filter(self, account_name: str, scope: str = 'all', limit: int = 100) -> str:
        if not self.login.token:
            print("[❌] 请先登录")
            return None
        
        account_info = self.search_account(account_name)
        if not account_info:
            return None
        
        fakeid = account_info['fakeid']
        biz = account_info.get('biz', '')
        
        cutoff = 0
        if scope == 'month':
            cutoff = (datetime.now() - timedelta(days=30)).timestamp()
        elif scope == 'quarter':
            cutoff = (datetime.now() - timedelta(days=90)).timestamp()
        elif scope == 'half_year':
            cutoff = (datetime.now() - timedelta(days=180)).timestamp()
        elif scope == 'year':
            cutoff = (datetime.now() - timedelta(days=365)).timestamp()
        
        print(f"\n[🚀] 开始采集文章列表...")
        
        if scope == 'custom':
            articles = self.fetch_article_list(fakeid, biz, max_count=limit)
            articles = articles[:limit]
        elif cutoff > 0:
            articles = self.fetch_article_list(fakeid, biz, max_count=1000, cutoff=cutoff)
        else:
            articles = self.fetch_article_list(fakeid, biz, max_count=1000)
        
        for i, article in enumerate(articles):
            article['seq'] = i + 1
        
        return self.save_articles(account_name, articles, biz, fakeid)
    
    def get_all_accounts(self) -> list:
        accounts = []
        if not self.data_dir.exists():
            return accounts
        for subdir in self.data_dir.iterdir():
            if subdir.is_dir():
                data_file = subdir / "data.json"
                if data_file.exists():
                    with open(data_file, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        accounts.append({
                            'name': data.get('account_name', subdir.name),
                            'count': data.get('total_count', 0),
                            'fetched_at': data.get('fetched_at', ''),
                            'file': str(data_file)
                        })
        return accounts


def main():
    from .login import WeChatLogin
    
    login = WeChatLogin()
    if not login.login():
        return
    
    fetcher = ArticleFetcher(login)
    
    account_name = input("\n请输入要采集的公众号名称: ").strip()
    if not account_name:
        return
    
    data_file = fetcher.fetch_with_filter(account_name)
    
    if data_file:
        print(f"\n[✅] 采集完成! 共获取 {len(fetcher.load_articles(account_name)['articles'])} 篇文章")


if __name__ == "__main__":
    main()
