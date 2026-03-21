#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from modules.login import WeChatLogin
from modules.fetcher import ArticleFetcher
from modules.downloader import ArticleDownloader
from modules.tagger import TagExtractor
from modules.exporter import ExcelExporter

SESSION_FILE = "wechat_session.json"
DATA_DIR = "articles_data"
ARTICLES_DIR = "articles"


class WeChatArticleTool:
    def __init__(self):
        self.login = WeChatLogin(SESSION_FILE)
        self.fetcher = None
        self.downloader = ArticleDownloader()
        self.tagger = TagExtractor()
        self.exporter = ExcelExporter()
        
        self.check_login()
    
    def check_login(self):
        if self.login.load_session():
            if self.login.is_logged_in():
                self.fetcher = ArticleFetcher(self.login)
                self.downloader.set_cookie(self.login.cookie)
                return True
        self.fetcher = None
        return False
    
    def show_status(self):
        print("\n" + "=" * 50)
        print("微信文章批量采集工具 v3")
        print("=" * 50)
        
        if self.login.token and self.login.account_name:
            expires = ""
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    expires = data.get('expires_at', '')[:16]
            
            print(f"\n[状态] 微信登录: ✅ 已登录")
            print(f"       账号: {self.login.account_name}")
            print(f"       过期时间: {expires}")
        else:
            print(f"\n[状态] 微信登录: ❌ 未登录")
        
        print()
        accounts = self._get_accounts()
        if accounts:
            print(f"[📚] 已采集 {len(accounts)} 个公众号:")
            for acc in accounts:
                print(f"     - {acc['name']}: {acc['count']} 篇文章")
        else:
            print("[📚] 暂无已采集的公众号")
        
        print()
    
    def _get_accounts(self):
        accounts = []
        data_dir = Path(DATA_DIR)
        if data_dir.exists():
            for f in data_dir.glob('*_list.json'):
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    accounts.append({
                        'name': data.get('account_name', f.stem.replace('_list', '')),
                        'count': data.get('total_count', 0),
                        'file': str(f)
                    })
        return accounts
    
    def menu_login(self):
        print("\n" + "=" * 50)
        print("📱 微信登录")
        print("=" * 50)
        
        if self.login.load_session():
            if self.login.is_logged_in():
                print(f"\n[✅] 已登录为: {self.login.account_name}")
                print("[💡] 凭证仍然有效，无需重新登录")
                
                choice = input("\n是否重新登录? (y/N): ").strip().lower()
                if choice != 'y':
                    return True
        
        if self.login.login():
            self.fetcher = ArticleFetcher(self.login)
            self.downloader.set_cookie(self.login.cookie)
            print(f"\n[✅] 登录成功!")
            return True
        else:
            print(f"\n[❌] 登录失败")
            return False
    
    def menu_fetch(self):
        if not self.login.token:
            print("\n[❌] 请先登录")
            input("\n按回车继续...")
            return
        
        print("\n" + "=" * 50)
        print("🔍 采集文章列表")
        print("=" * 50)
        
        account_name = input("\n请输入要采集的公众号名称: ").strip()
        if not account_name:
            print("[❌] 公众号名称不能为空")
            return
        
        print("\n请选择下载范围:")
        print("  1) 全量下载 - 下载所有历史文章")
        print("  2) 最近一年 - 下载近12个月的文章")
        print("  3) 最近半年 - 下载近6个月的文章")
        print("  4) 最近3个月 - 下载近3个月的文章")
        print("  5) 最近1个月 - 下载近30天的文章")
        print("  6) 最近 N 篇 - 指定下载数量")
        
        scope_map = {
            '1': 'all',
            '2': 'year',
            '3': 'half_year',
            '4': 'quarter',
            '5': 'month',
            '6': 'custom'
        }
        
        scope_choice = input("\n请输入选项: ").strip()
        scope = scope_map.get(scope_choice, 'all')
        
        limit = 100
        if scope == 'custom':
            try:
                limit = int(input("请输入要采集的文章数量: ").strip())
            except ValueError:
                limit = 100
        
        print(f"\n[🚀] 开始采集公众号「{account_name}」的文章...")
        print(f"     范围: {scope}")
        
        data_file = self.fetcher.fetch_with_filter(account_name, scope, limit)
        
        if data_file:
            print(f"\n[✅] 采集完成!")
            
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count = len(data.get('articles', []))
                print(f"     共获取 {count} 篇文章")
        
        input("\n按回车继续...")
    
    def menu_download(self):
        accounts = self._get_accounts()
        
        if not accounts:
            print("\n[❌] 暂无已采集的公众号，请先采集文章")
            input("\n按回车继续...")
            return
        
        print("\n" + "=" * 50)
        print("📥 下载文章")
        print("=" * 50)
        
        print("\n请选择要下载的公众号:")
        for i, acc in enumerate(accounts, 1):
            print(f"  {i}) {acc['name']} ({acc['count']}篇)")
        
        choice = input("\n请输入选项: ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(accounts):
                raise ValueError()
            account_name = accounts[idx]['name']
        except ValueError:
            print("[❌] 无效选项")
            return
        
        print("\n请选择下载范围:")
        print("  1) 全部 - 下载所有文章")
        print("  2) 未下载 - 只下载未下载的文章")
        
        scope_choice = input("\n请输入选项: ").strip()
        scope = 'unfinished' if scope_choice == '2' else 'all'
        
        json_file = Path(DATA_DIR) / f"{account_name}_list.json"
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        
        if scope == 'unfinished':
            articles = [a for a in articles if not a.get('downloaded')]
        
        if not articles:
            print("\n[📭] 没有需要下载的文章")
            return
        
        print(f"\n[🚀] 开始下载 {len(articles)} 篇文章...")
        print(f"     保存目录: {self.downloader.articles_dir / account_name}")
        print(f"     冷却时间: {self.downloader.min_interval}-{self.downloader.max_interval}秒")
        print(f"     断点续传: 已启用")
        print("\n[Ctrl+C] 可随时中断，已下载的文章会自动跳过\n")
        
        try:
            result = self.downloader.download_articles(account_name, articles)
            
            self.downloader.update_json_file(account_name, articles)
            
            print(f"\n{'='*50}")
            print(f"[📊] 下载统计:")
            print(f"     成功: {result['success']}")
            print(f"     失败: {result['failed']}")
            print(f"     跳过: {result['skipped']}")
            
        except KeyboardInterrupt:
            print("\n\n[⚠️] 下载已中断")
            print("[💾] 已下载的文章状态已保存")
        
        input("\n按回车继续...")
    
    def menu_tags(self):
        accounts = self._get_accounts()
        
        if not accounts:
            print("\n[❌] 暂无已采集的公众号")
            input("\n按回车继续...")
            return
        
        print("\n" + "=" * 50)
        print("🏷️ 提取文章标签")
        print("=" * 50)
        
        print("\n请选择要提取标签的公众号:")
        for i, acc in enumerate(accounts, 1):
            print(f"  {i}) {acc['name']}")
        
        choice = input("\n请输入选项: ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(accounts):
                raise ValueError()
            account_name = accounts[idx]['name']
        except ValueError:
            print("[❌] 无效选项")
            return
        
        print(f"\n[🚀] 开始提取标签...")
        
        title_to_tags = self.tagger.extract_tags_for_account(account_name)
        
        print(f"\n{'='*50}")
        print(f"[📊] 标签提取完成，共处理 {len(title_to_tags)} 篇文章")
        
        for title, tags in list(title_to_tags.items())[:3]:
            print(f"\n{title[:40]}...")
            print(f"  标签: {', '.join(tags)}")
        
        input("\n按回车继续...")
    
    def menu_export(self):
        accounts = self._get_accounts()
        
        if not accounts:
            print("\n[❌] 暂无已采集的公众号")
            input("\n按回车继续...")
            return
        
        print("\n" + "=" * 50)
        print("📤 导出Excel")
        print("=" * 50)
        
        print("\n请选择导出方式:")
        print("  1) 导出所有公众号")
        print("  2) 导出单个公众号")
        print("  3) 导出汇总表")
        
        choice = input("\n请输入选项: ").strip()
        
        if choice == '1':
            files = self.exporter.export_all()
            print(f"\n[✅] 共导出 {len(files)} 个文件")
        elif choice == '2':
            print("\n请选择要导出的公众号:")
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}) {acc['name']}")
            
            sub_choice = input("\n请输入选项: ").strip()
            try:
                idx = int(sub_choice) - 1
                if idx < 0 or idx >= len(accounts):
                    raise ValueError()
                account_name = accounts[idx]['name']
                self.exporter.export_account(account_name)
            except ValueError:
                print("[❌] 无效选项")
        elif choice == '3':
            self.exporter.export_summary()
        else:
            print("[❌] 无效选项")
        
        input("\n按回车继续...")
    
    def menu_status(self):
        accounts = self._get_accounts()
        
        print("\n" + "=" * 50)
        print("📊 查看状态")
        print("=" * 50)
        
        if not accounts:
            print("\n[📭] 暂无已采集的公众号")
        else:
            for acc in accounts:
                json_file = Path(DATA_DIR) / f"{acc['name']}_list.json"
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    articles = data.get('articles', [])
                    total = len(articles)
                    downloaded = sum(1 for a in articles if a.get('downloaded'))
                    with_tags = sum(1 for a in articles if a.get('tags'))
                    
                    print(f"\n📰 {acc['name']}")
                    print(f"   文章总数: {total}")
                    print(f"   已下载: {downloaded} ({downloaded*100//max(total,1)}%)")
                    print(f"   已打标签: {with_tags}")
                    print(f"   采集时间: {data.get('fetched_at', '')[:16]}")
        
        print()
    
    def run(self):
        while True:
            self.show_status()
            
            print("=" * 50)
            print("1) 📱 微信登录")
            print("2) 🔍 采集文章列表")
            print("3) 📥 下载文章")
            print("4) 🏷️ 提取文章标签")
            print("5) 📤 导出Excel")
            print("6) 📊 查看状态")
            print("0) ❌ 退出")
            print("=" * 50)
            
            choice = input("\n请输入选项: ").strip()
            
            if choice == '1':
                self.menu_login()
            elif choice == '2':
                self.menu_fetch()
            elif choice == '3':
                self.menu_download()
            elif choice == '4':
                self.menu_tags()
            elif choice == '5':
                self.menu_export()
            elif choice == '6':
                self.menu_status()
            elif choice == '0':
                print("\n[👋] 再见!")
                break
            else:
                print("\n[❌] 无效选项")


def main():
    tool = WeChatArticleTool()
    tool.run()


if __name__ == "__main__":
    main()
