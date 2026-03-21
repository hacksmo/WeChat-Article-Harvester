import os
import json
import time
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dateutil import parser as date_parser

DATA_DIR = "articles_data"

class ArticleFetcher:
    def __init__(self, login_module):
        self.login = login_module
        self.base_url = "https://mp.weixin.qq.com"
        self.session = requests.Session()
        self.data_dir = Path(DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
    
    def get_headers(self) -> dict:
        return {
            'Cookie': self.login.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
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
    
    def fetch_article_list(self, fakeid: str, biz: str = '', max_count: int = 1000) -> list:
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
                
                for item in publish_list:
                    publish_info = item.get('publish_info', {})
                    if isinstance(publish_info, str):
                        publish_info = json.loads(publish_info)
                    
                    appmsgex = publish_info.get('appmsgex', [])
                    for article_data in appmsgex:
                        article = self._parse_publish_article(article_data)
                        if article:
                            articles.append(article)
                
                print(f"  [✅] 本次获取 {len(publish_list)} 条记录，累计 {len(articles)} 篇")
                
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
            
            return {
                'aid': aid,
                'title': article_data.get('title', ''),
                'url': link,
                'digest': article_data.get('digest', ''),
                'author': article_data.get('author', ''),
                'publish_date': publish_date,
                'create_time': create_time,
                'cover': article_data.get('cover', ''),
                'read_count': 0,
                'is_original': False,
                'tags': [],
                'downloaded': False,
                'local_path': None,
                'downloaded_at': None
            }
        except Exception as e:
            print(f"  [⚠️] 解析文章失败: {e}")
            return None
    
    def _get_read_count(self, aid: str) -> int:
        try:
            url = f"{self.base_url}/cgi-bin/appmsg_comment"
            params = {
                'action': 'get_comment_count',
                'msg_id': aid,
                'token': self.login.token,
                'lang': 'zh_CN',
                'f': 'json',
                'ajax': '1'
            }
            resp = self.session.get(url, params=params, headers=self.get_headers(), timeout=10)
            data = resp.json()
            
            if data.get('base_resp', {}).get('ret') == 0:
                return data.get('read_count', 0)
        except:
            pass
        return 0
    
    def save_articles(self, account_name: str, articles: list, biz: str = '', fakeid: str = '') -> str:
        data_file = self.data_dir / f"{account_name}_list.json"
        
        data = {
            'account_name': account_name,
            'biz': biz,
            'fakeid': fakeid,
            'fetched_at': datetime.now().isoformat(),
            'total_count': len(articles),
            'articles': articles
        }
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[💾] 文章列表已保存到: {data_file}")
        return str(data_file)
    
    def load_articles(self, account_name: str) -> dict:
        data_file = self.data_dir / f"{account_name}_list.json"
        
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
        
        print(f"\n[🚀] 开始采集文章列表...")
        
        if scope == 'custom':
            articles = self.fetch_article_list(fakeid, biz, max_count=limit)
        else:
            articles = self.fetch_article_list(fakeid, biz, max_count=1000)
        
        if scope == 'custom':
            articles = articles[:limit]
        elif scope == 'month':
            cutoff = datetime.now() - timedelta(days=30)
            articles = [a for a in articles if a.get('create_time', 0) >= cutoff.timestamp()]
        elif scope == 'quarter':
            cutoff = datetime.now() - timedelta(days=90)
            articles = [a for a in articles if a.get('create_time', 0) >= cutoff.timestamp()]
        elif scope == 'half_year':
            cutoff = datetime.now() - timedelta(days=180)
            articles = [a for a in articles if a.get('create_time', 0) >= cutoff.timestamp()]
        elif scope == 'year':
            cutoff = datetime.now() - timedelta(days=365)
            articles = [a for a in articles if a.get('create_time', 0) >= cutoff.timestamp()]
        
        for i, article in enumerate(articles):
            article['seq'] = i + 1
        
        return self.save_articles(account_name, articles, biz, fakeid)
    
    def get_all_accounts(self) -> list:
        accounts = []
        for f in self.data_dir.glob('*_list.json'):
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                accounts.append({
                    'name': data.get('account_name', f.stem.replace('_list', '')),
                    'count': data.get('total_count', 0),
                    'fetched_at': data.get('fetched_at', ''),
                    'file': str(f)
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
