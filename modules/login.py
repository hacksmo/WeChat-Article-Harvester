import os
import sys
import json
import time
import re
import requests
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs

SESSION_FILE = "wechat_session.json"

SESSION_FILE = "wechat_session.json"


class WeChatLogin:
    def __init__(self, session_file: str = SESSION_FILE):
        self.session_file = session_file
        self.session = requests.Session()
        self.base_url = "https://mp.weixin.qq.com"
        self.token = None
        self.cookie = None
        self.uin = None
        self.fakeid = None
        self.account_name = None
        self.auth_key = None
        self.uuid = None
        self.appmsg_token = None
        
    def load_session(self) -> bool:
        if not os.path.exists(self.session_file):
            return False
        
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            expires_at = datetime.fromisoformat(data.get('expires_at', '2000-01-01'))
            if expires_at > datetime.now():
                self.token = data.get('token')
                self.cookie = data.get('cookie')
                self.uin = data.get('uin')
                self.fakeid = data.get('fakeid')
                self.account_name = data.get('account_name')
                self.auth_key = data.get('auth_key')
                self.uuid = data.get('uuid')
                self.appmsg_token = data.get('appmsg_token')
                return True
            else:
                print("[⏰] 登录凭证已过期，请重新登录")
                return False
        except Exception as e:
            print(f"[❌] 加载登录凭证失败: {e}")
            return False
    
    def save_session(self):
        session_data = {
            'token': self.token,
            'cookie': self.cookie,
            'uin': self.uin,
            'fakeid': self.fakeid,
            'account_name': self.account_name,
            'auth_key': self.auth_key,
            'uuid': self.uuid,
            'appmsg_token': self.appmsg_token,
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        print(f"[💾] 登录凭证已保存到 {self.session_file}")
    
    def is_logged_in(self) -> bool:
        if not self.token or not self.cookie:
            return False
        
        try:
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            url = f"{self.base_url}/cgi-bin/home?t=home/index&lang=zh_CN&token={self.token}"
            resp = self.session.get(url, headers=headers, timeout=10)
            
            if '错误的令牌' in resp.text:
                return False
            
            return resp.status_code == 200
        except:
            return False
    
    def login(self) -> bool:
        # This method is now the entry point for a user-initiated login.
        # It directly asks for the login method.
        print("\n请选择登录方式：")
        print("  1) 自动浏览器扫码登录 (推荐)")
        print("  2) 手动复制 Cookie 登录")
        
        choice = input("\n请输入选项 (1/2): ").strip()
        
        if choice == '1':
            return self.login_with_playwright()
        elif choice == '2':
            return self.manual_login()
        else:
            print("[❌] 无效选项")
            return False
    
    def fetch_appmsg_token(self) -> bool:
        """从登录后的页面获取 appmsg_token"""
        try:
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            # 访问素材管理页面
            url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=main/app_msg_list&action=list&lang=zh_CN&token={self.token}"
            resp = self.session.get(url, headers=headers, timeout=10)
            
            # 查找 appmsg_token
            match = re.search(r'"appmsg_token"\s*[=:]\s*"([^"]+)"', resp.text)
            if match:
                self.appmsg_token = match.group(1)
                print(f"[✅] appmsg_token 获取成功")
                self.save_session()
                return True
            
            print("[⚠️] 无法获取 appmsg_token，请手动获取")
            return False
            
        except Exception as e:
            print(f"[❌] 获取 appmsg_token 失败: {e}")
            return False
    
    def get_appmsg_token_manual(self) -> bool:
        """手动获取 appmsg_token"""
        print("\n" + "-"*50)
        print("📋 获取 appmsg_token")
        print("-"*50)
        
        print("\n请按以下步骤操作：")
        print("  1. 确保已成功登录公众号后台")
        print("  2. 在浏览器中打开以下链接：")
        print(f"     https://mp.weixin.qq.com/cgi-bin/appmsg?t=main/app_msg_list&action=list&lang=zh_CN&token={self.token}")
        print("  3. 按 F12 打开开发者工具")
        print("  4. 搜索 'appmsg_token'")
        print("  5. 复制引号中的值")
        
        token = input("\n请输入 appmsg_token: ").strip()
        
        if token:
            self.appmsg_token = token
            self.save_session()
            print("[✅] appmsg_token 已保存")
            return True
        
        return False
    
    def browser_login(self) -> bool:
        print("\n" + "-"*50)
        print("📱 浏览器扫码登录")
        print("-"*50)
        
        print("\n请按以下步骤操作：")
        print("  1. 程序会打开浏览器到微信登录页面")
        print("  2. 使用微信扫描二维码")
        print('  3. 在手机上点击"确认登录"')
        print("  4. 登录成功后，浏览器会跳转到公众号后台")
        print("  5. 复制浏览器地址栏的完整 URL")
        print("  6. 同时按 F12 -> Network -> 刷新页面")
        print("  7. 找到任意请求，复制请求头的 Cookie")
        
        print("\n[🌐] 正在打开登录页面...")
        webbrowser.open("https://mp.weixin.qq.com/")
        
        print("\n" + "-"*30)
        print("请粘贴登录后的 URL 和 Cookie:")
        print("-"*30)
        
        url = input("URL: ").strip()
        cookie = input("Cookie: ").strip()
        
        if not url or not cookie:
            print("[❌] URL 和 Cookie 不能为空")
            return False
        
        if 'token=' in url:
            start = url.find('token=') + 6
            end = url.find('&', start)
            if end == -1:
                self.token = url[start:]
            else:
                self.token = url[start:end]
        
        self.cookie = cookie
        
        if self.is_logged_in():
            self.account_name = self._get_account_name()
            
            # 获取 appmsg_token
            print("\n[🔄] 正在获取 appmsg_token...")
            self.fetch_appmsg_token()
            
            self.save_session()
            print(f"\n[✅] 登录成功!")
            print(f"[👤] 账号: {self.account_name}")
            return True
        else:
            print("[❌] 登录验证失败，请检查 Cookie 和 URL 是否正确")
            return False
    
    def manual_login(self) -> bool:
        print("\n" + "-"*50)
        print("📋 手动复制 Cookie 登录")
        print("-"*50)
        
        print("\n请按以下步骤操作：")
        print("  1. 在浏览器中打开 https://mp.weixin.qq.com")
        print("  2. 登录你的微信公众号后台")
        print("  3. 登录成功后，按 F12 打开开发者工具")
        print("  4. 切换到 Network (网络) 标签")
        print("  5. 刷新页面，找到任意一个请求")
        print("  6. 复制请求的完整 URL (包含 token)")
        print("  7. 复制请求头的 Cookie 字段")
        
        print("\n" + "-"*30)
        print("请粘贴登录后的 URL 和 Cookie:")
        print("-"*30)
        
        url = input("URL: ").strip()
        cookie = input("Cookie: ").strip()
        
        if not url or not cookie:
            print("[❌] URL 和 Cookie 不能为空")
            return False
        
        if 'token=' in url:
            start = url.find('token=') + 6
            end = url.find('&', start)
            if end == -1:
                self.token = url[start:]
            else:
                self.token = url[start:end]
        
        self.cookie = cookie
        
        if self.is_logged_in():
            self.account_name = self._get_account_name()
            
            # 获取 appmsg_token
            print("\n[🔄] 正在获取 appmsg_token...")
            if not self.fetch_appmsg_token():
                self.get_appmsg_token_manual()
            
            self.save_session()
            print(f"\n[✅] 登录成功!")
            print(f"[👤] 账号: {self.account_name}")
            return True
        else:
            print("[❌] 登录验证失败，请确保登录成功后再复制 URL 和 Cookie")
            return False

    def login_with_playwright(self) -> bool:
        print("\n" + "="*50)
        print("📱 自动浏览器登录 (目前微信限制较严，推荐手动复制Cookie)")
        print("="*50)
        
        # 不要在这里删掉旧 session，万一失败了还能用
        # self.logout()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(no_viewport=True)
                page = context.new_page()
                
                print("[🌐] 正在打开登录页面，请扫码...")
                page.goto("https://mp.weixin.qq.com/")
                
                print("[⏳] 等待扫码登录...")
                # 等待登录成功并跳转到后台首页
                page.wait_for_url("https://mp.weixin.qq.com/cgi-bin/home?t=home/index**", timeout=120000)
                print("[✅] 登录成功!")
                
                # 从URL中提取主 token
                url = page.url
                self.token = parse_qs(urlparse(url).query).get('token', [None])[0]
                
                # 从浏览器上下文中获取完整的 cookie
                cookies = context.cookies()
                self.cookie = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                
                # 我们不再强求 appmsg_token，因为它对获取【他人】文章阅读量没用
                self.appmsg_token = None

                context.close()
                browser.close()

                if self.token and self.cookie:
                    self.account_name = self._get_account_name()
                    self.save_session()
                    print(f"\n[👤] 账号: {self.account_name}")
                    return True
                else:
                    print("[❌] 自动登录失败：未能获取到凭证。")
                    return False

        except Exception as e:
            print(f"[❌] Playwright 登录时出错: {e}")
            print("[💡] 请选择 手动复制 Cookie 登录")
            return False

    def _get_account_name(self) -> str:
        try:
            url = f"{self.base_url}/cgi-bin/home?t=home/index&lang=zh_CN&token={self.token}"
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            resp = self.session.get(url, headers=headers, timeout=10)
            
            if '错误' not in resp.text and resp.status_code == 200:
                name_match = re.search(r'"nick_name"\s*:\s*"([^"]+)"', resp.text)
                if name_match:
                    return name_match.group(1)
        except:
            pass
        return "未知账号"
    
    def logout(self):
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
            print("[👋] 已退出登录")
    
    def get_headers(self) -> dict:
        return {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': f'{self.base_url}/cgi-bin/home'
        }
    
    def get_params(self) -> dict:
        params = {
            'token': self.token,
            'lang': 'zh_CN',
        }
        if self.appmsg_token:
            params['appmsg_token'] = self.appmsg_token
        return params


def main():
    login = WeChatLogin()
    
    if login.login():
        print("\n[✅] 登录成功!")
        print(f"[👤] 账号: {login.account_name}")
        if login.appmsg_token:
            print(f"[🔑] appmsg_token: {login.appmsg_token[:20]}...")
        else:
            print("[⚠️] appmsg_token 未获取，请在下一步中获取")
    else:
        print("\n[❌] 登录失败")


if __name__ == "__main__":
    main()
