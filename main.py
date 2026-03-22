#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('LC_ALL', 'C.UTF-8')
if sys.version_info >= (3, 7):
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from modules.login import WeChatLogin
from modules.fetcher import ArticleFetcher
from modules.downloader import ArticleDownloader
from modules.tagger import TagExtractor
from modules.exporter import ExcelExporter
from modules.pdf_converter import export_pdf, export_pdf_all

SESSION_FILE = "wechat_session.json"
ROOT_DIR = "WeChatArticles"


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
        root = Path(ROOT_DIR)
        if root.exists():
            for subdir in root.iterdir():
                if subdir.is_dir():
                    data_file = subdir / "data.json"
                    if data_file.exists():
                        with open(data_file, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                            accounts.append({
                                'name': data.get('account_name', subdir.name),
                                'count': data.get('total_count', 0),
                                'file': str(data_file)
                            })
        return accounts
    
    def menu_login(self):
        print("\n" + "=" * 50)
        print("📱 微信登录")
        print("=" * 50)
        
        # 检查是否已有有效登录
        if self.login.token and self.login.is_logged_in():
            print(f"\n[✅] 已登录为: {self.login.account_name}")
            
            if self.login.appmsg_token:
                print("[🔑] appmsg_token 已存在，可获取阅读量。")
            else:
                print("[⚠️] appmsg_token 不存在，如需获取阅读量，请重新登录。")

            choice = input("\n是否要重新登录 (y/N)? ").strip().lower()
            if choice != 'y':
                return True # 用户选择不重新登录
        
        # 如果未登录，或用户选择重新登录，则执行登录流程
        if self.login.login():
            # 登录成功后，刷新所有依赖登录状态的模块
            self.fetcher = ArticleFetcher(self.login)
            self.downloader.set_cookie(self.login.cookie)
            print(f"\n[✅] 登录流程成功!")
            return True
        else:
            print(f"\n[❌] 登录流程失败")
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
        
        json_file = Path(ROOT_DIR) / account_name / "data.json"
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        
        if scope == 'unfinished':
            articles = [a for a in articles if not a.get('downloaded')]
        
        if not articles:
            print("\n[📭] 没有需要下载的文章")
            return
        
        print(f"\n[🚀] 开始下载 {len(articles)} 篇文章...")
        print(f"     保存目录: {Path(ROOT_DIR) / account_name / 'articles'}")
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
    
    def menu_update_reads(self):
        print("\n" + "=" * 50)
        print("📊 更新文章阅读量 [功能限制]")
        print("=" * 50)
        print("\n[⚠️] 微信的阅读量 API (`/mp/getappmsgext`) 只能在**微信客户端**")
        print("    (如手机微信、PC微信浏览器) 内调用。")
        print("    它需要客户端注入的特定加密参数 (如 `key`, `pass_ticket` 和客户端 `appmsg_token`)。")
        print("    公众号后台获取的 `appmsg_token` 对此 API 无效。")
        print("\n[💡] 如果必须获取阅读量，你需要：")
        print("    1. 使用 Fiddler / Mitmproxy 等抓包工具")
        print("    2. 在 PC 微信中打开一篇文章，拦截请求获取客户端 Token")
        print("    3. 将此 Token 喂给爬虫")
        print("    (这已经超出了本桌面端一键工具的范畴，属于高阶爬虫技术)")
        print("\n" + "=" * 50)
        input("\n按回车返回...")

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
                json_file = Path(ROOT_DIR) / acc['name'] / "data.json"
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
    
    def menu_cleanup(self):
        accounts = self._get_accounts()
        
        print("\n" + "=" * 50)
        print("🗑️ 清理空文件夹")
        print("=" * 50)
        
        if not accounts:
            print("\n[📭] 暂无已采集的公众号")
            return
        
        print("\n选择要清理的公众号:")
        for i, acc in enumerate(accounts, 1):
            print(f"  {i}) {acc['name']}")
        print(f"  0) 全部清理")
        
        choice = input("\n请选择: ").strip()
        
        if choice == '0':
            for acc in accounts:
                print(f"\n清理 {acc['name']}...")
                result = self.downloader.cleanup_and_export_deleted(acc['name'])
                print(f"  删除空文件夹: {len(result['deleted_folders'])} 个")
        elif choice:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(accounts):
                    acc = accounts[idx]
                    print(f"\n清理 {acc['name']}...")
                    result = self.downloader.cleanup_and_export_deleted(acc['name'])
                    print(f"  删除空文件夹: {len(result['deleted_folders'])} 个")
            except ValueError:
                print("[❌] 无效选择")
        
        print()

    def menu_batch(self):
        if not self.login.token:
            print("\n[❌] 请先登录")
            input("\n按回车继续...")
            return

        print("\n" + "=" * 50)
        print("🔄 批量处理多账号")
        print("=" * 50)

        print("\n请输入要处理的公众号名称（支持多种输入方式）:")
        print("  - 逗号分隔: 账号1,账号2,账号3")
        print("  - 逐行输入，空行结束")
        print("  - 输入 0 查看已采集的账号列表\n")

        raw_input = input().strip()

        if not raw_input:
            print("[❌] 输入不能为空")
            return

        if raw_input == '0':
            accounts = self._get_accounts()
            if not accounts:
                print("[📭] 暂无已采集的公众号")
                return
            print("已采集的账号:")
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}) {acc['name']}")
            print("\n请重新运行批量处理并输入账号名")
            return

        account_names = []
        for line in raw_input.split('\n'):
            for part in line.split(','):
                part = part.strip()
                if part:
                    account_names.append(part)

        account_names = [n for n in account_names if n]
        if not account_names:
            print("[❌] 未识别到有效账号名")
            return

        print(f"\n[📋] 将处理以下 {len(account_names)} 个账号:")
        for name in account_names:
            print(f"     - {name}")

        confirm = input("\n确认开始处理 (y/N)? ").strip().lower()
        if confirm != 'y':
            print("[❌] 已取消")
            return

        print(f"\n{'='*60}")
        print(f"🚀 开始批量处理 {len(account_names)} 个账号")
        print(f"    流程: 采集 → 下载 → 标签 → Excel")
        print(f"{'='*60}\n")

        total_stats = {'accounts': 0, 'fetched': 0, 'downloaded': 0, 'failed': 0, 'skipped': 0}

        for i, account_name in enumerate(account_names, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(account_names)}] 处理账号: {account_name}")
            print(f"{'='*60}")

            acc_stats = {'fetched': 0, 'downloaded': 0, 'failed': 0, 'skipped': 0}

            print(f"\n[1/4] 采集文章列表...")
            data_file = self.fetcher.fetch_with_filter(account_name, 'all', 100)
            if not data_file:
                print(f"[❌] 采集失败，跳过此账号")
                continue

            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            articles = data.get('articles', [])
            acc_stats['fetched'] = len(articles)

            pending = [a for a in articles if not a.get('downloaded')]
            if pending:
                print(f"\n[2/4] 下载文章 ({len(pending)} 篇待下载)...")
                print(f"      冷却: {self.downloader.min_interval}-{self.downloader.max_interval}秒")
                try:
                    result = self.downloader.download_articles(account_name, articles)
                    self.downloader.update_json_file(account_name, articles)
                    acc_stats['downloaded'] = result['success']
                    acc_stats['failed'] = result['failed']
                    acc_stats['skipped'] = result['skipped']
                except KeyboardInterrupt:
                    print(f"[⚠️] 下载被中断")
            else:
                print(f"\n[2/4] 下载文章: 无待下载文章")

            print(f"\n[3/4] 提取标签...")
            title_to_tags = self.tagger.extract_tags_for_account(account_name)
            tagged_count = sum(1 for a in articles if title_to_tags.get(a.get('title', '')))
            print(f"      完成 {tagged_count} 篇")

            print(f"\n[4/4] 导出Excel...")
            self.exporter.export_account(account_name)
            print(f"      完成")

            print(f"\n{'='*60}")
            print(f"[📊] {account_name} 摘要:")
            print(f"     采集: {acc_stats['fetched']} 篇")
            print(f"     下载成功: {acc_stats['downloaded']} 篇")
            print(f"     下载失败: {acc_stats['failed']} 篇")
            print(f"     跳过: {acc_stats['skipped']} 篇")
            print(f"{'='*60}")

            total_stats['accounts'] += 1
            total_stats['fetched'] += acc_stats['fetched']
            total_stats['downloaded'] += acc_stats['downloaded']
            total_stats['failed'] += acc_stats['failed']
            total_stats['skipped'] += acc_stats['skipped']

        print(f"\n{'='*60}")
        print(f"[🎉] 批量处理完成!")
        print(f"     处理账号: {total_stats['accounts']} 个")
        print(f"     采集文章: {total_stats['fetched']} 篇")
        print(f"     下载成功: {total_stats['downloaded']} 篇")
        print(f"     下载失败: {total_stats['failed']} 篇")
        print(f"{'='*60}")

        input("\n按回车继续...")

    def menu_pdf(self):
        accounts = self._get_accounts()

        print("\n" + "=" * 50)
        print("📄 导出 PDF")
        print("=" * 50)

        if not accounts:
            print("\n[📭] 暂无已采集的公众号")
            input("\n按回车继续...")
            return

        print("\n请选择导出方式:")
        print("  1) 导出单个公众号的 PDF")
        print("  2) 导出所有公众号的 PDF")

        choice = input("\n请输入选项: ").strip()

        if choice == '1':
            print("\n请选择要导出 PDF 的公众号:")
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}) {acc['name']}")

            sub = input("\n请输入选项: ").strip()
            try:
                idx = int(sub) - 1
                if 0 <= idx < len(accounts):
                    account_name = accounts[idx]['name']
                else:
                    raise ValueError()
            except ValueError:
                print("[❌] 无效选项")
                return

            overwrite_q = input("是否覆盖已有 PDF (y/N)? ").strip().lower()
            overwrite = overwrite_q == 'y'

            print(f"\n[🚀] 开始转换...")
            stats = export_pdf(account_name, overwrite=overwrite)

            print(f"\n{'='*50}")
            print(f"[📊] 转换统计:")
            print(f"     总数: {stats['total']}")
            print(f"     成功: {stats['success']}")
            print(f"     失败: {stats['failed']}")
            print(f"     跳过: {stats['skipped']}")

        elif choice == '2':
            overwrite_q = input("是否覆盖已有 PDF (y/N)? ").strip().lower()
            overwrite = overwrite_q == 'y'

            print(f"\n[🚀] 开始批量转换...")
            stats = export_pdf_all(overwrite=overwrite)

            print(f"\n{'='*50}")
            print(f"[📊] 全部转换统计:")
            print(f"     总数: {stats['total']}")
            print(f"     成功: {stats['success']}")
            print(f"     失败: {stats['failed']}")
            print(f"     跳过: {stats['skipped']}")
        else:
            print("[❌] 无效选项")

        input("\n按回车继续...")

    def run(self):
        while True:
            self.show_status()
            
            print("=" * 50)
            print("A) 🔄 批量处理多账号")
            print("1) 📱 微信登录 (自动/手动)")
            print("2) 🔍 采集文章列表")
            print("3) 📥 下载文章")
            print("4) 🏷️ 提取文章标签")
            print("5) 📤 导出Excel")
            print("6) 📊 查看状态")
            print("7) 🗑️ 清理空文件夹")
            print("8) 📄 导出PDF")
            print("0) ❌ 退出")
            print("=" * 50)
            
            choice = input("\n请输入选项: ").strip()
            
            if choice.lower() == 'a':
                self.menu_batch()
            elif choice == '1':
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
            elif choice == '7':
                self.menu_cleanup()
            elif choice == '8':
                self.menu_pdf()
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
