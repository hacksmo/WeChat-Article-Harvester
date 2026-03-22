# 微信文章批量采集工具技术文档

## 项目概述

WeChat-Article-Harvester 是一款基于微信公众号后台 API 的文章批量采集工具，支持扫码登录、历史文章采集、本地 Markdown 下载（含图片）、标签提取、Excel 导出和 PDF 转换。

**GitHub**: https://github.com/hacksmo/WeChat-Article-Harvester

---

## 核心功能

| 模块 | 文件 | 说明 |
|------|------|------|
| 微信登录 | `modules/login.py` | 扫码登录，获取 Cookie 和 Token |
| 文章采集 | `modules/fetcher.py` | 调用公众号后台 API 获取文章列表 |
| 文章下载 | `modules/downloader.py` | 三层兜底下载策略 |
| 标签提取 | `modules/tagger.py` | 基于 jieba 分词和关键词库打标签 |
| Excel 导出 | `modules/exporter.py` | 数据导出 + 失败记录 |
| PDF 转换 | `modules/pdf_converter.py` | Markdown → HTML → PDF |

---

## 目录结构

```
WeChat-Article-Harvester/
├── main.py
├── requirements.txt
├── modules/
│   ├── login.py          # 扫码登录
│   ├── fetcher.py        # 公众号 API 采集
│   ├── downloader.py     # 三层下载策略
│   ├── tagger.py         # 标签提取
│   ├── exporter.py       # Excel 导出
│   ├── pdf_converter.py  # PDF 转换
│   └── pdf_config.py    # PDF 样式配置
├── static/
│   └── pdf_styles.css    # PDF CSS 样式
├── WeChatArticles/       # 文章数据 (gitignored)
├── WeChatPDFs/           # PDF 输出 (gitignored)
├── old/                  # 历史归档 (gitignored)
├── wechat_session.json   # 登录会话 (gitignored)
└── m2w                   # 文章抓取工具 (需手动下载)
```

---

## 数据存储

### 文章目录（`WeChatArticles/`）

按公众号名树形存储，每个账号一个文件夹，文件夹内按日期-标题组织：

```
WeChatArticles/
├── Helen育学园/
│   ├── 2025-01-15_宝宝发热怎么办/
│   │   ├── 2025-01-15_宝宝发热怎么办.md
│   │   └── images/
│   └── data.json         # 该账号的文章列表
├── 硬核水墨/
└── 安工聊港卡炒港股/
```

### PDF 目录（`WeChatPDFs/`）

按公众号名独立存放，与 Markdown 文章一一对应：

```
WeChatPDFs/
├── Helen育学园/           # 116 个 PDF
├── 硬核水墨/               # 44 个 PDF
└── 安工聊港卡炒港股/         # 191 个 PDF
```

---

## 三层下载策略

这是本工具的核心设计，解决了微信公众号文章正文被 CSS 隐藏导致下载内容不完整的难题。

### 问题背景

部分微信公众号文章正文使用 CSS `visibility: hidden; opacity: 0;` 包裹，JavaScript 执行后才显示。直接请求或使用普通工具只能拿到框架和标题，无法获取正文内容。

- **m2w 直接下载**：生成 ~11B 的空框架文件
- **HTTP 请求解析**：返回 ~195B 的标题，缺失正文

### 解决方案架构

```
download_single(url)
│
├─ 尝试 m2w（本地 Chrome 渲染）
│  ├─ 失败 → 尝试 HTTP
│  └─ 成功 → 验证内容 ≥500B?
│             ├─ 是 → 返回
│             └─ 否 → 清理目录，尝试 HTTP
│
├─ 尝试 HTTP（直接请求文章接口）
│  ├─ 失败 → 尝试 webfetch
│  └─ 成功 → 验证内容 ≥500B?
│             ├─ 是 → 返回
│             └─ 否 → 尝试 webfetch
│
└─ 尝试 webfetch（AutoGLM API 渲染）
   ├─ 失败 → 标记失败，返回错误
   └─ 成功 → 写入 Markdown，返回
```

### 各层实现

#### 第一层：m2w（推荐）

调用 `wechatmp2markdown` 工具，使用本地 Chrome 浏览器渲染页面后抓取内容。支持保存图片到本地，生成标准 Markdown 格式。

**前提**：从 [wechatmp2markdown releases](https://github.com/fengxxc/wechatmp2markdown/releases) 下载工具，重命名为 `m2w` 放入项目根目录。

macOS 需要移除安全限制：
```bash
xattr -cr ./m2w
```

**优点**：无需登录 Cookie，离线可用，图片本地化
**缺点**：macOS 有安全拦截，需要额外处理

#### 第二层：HTTP（需要 Cookie）

直接调用微信公众号文章接口，带上登录后的 Cookie 和 token 参数。速度最快，但依赖登录状态。

**前提**：通过菜单 1 扫码登录，会话保存在 `wechat_session.json`

**优点**：速度快，不依赖外部工具
**缺点**：需要有效的 Cookie（有效期约 2 小时）

#### 第三层：webfetch（需要 AutoGLM 扩展）

通过 AutoGLM 浏览器扩展的 API（端口 53699）渲染页面，获取完整正文内容。

**前提**：Chrome 浏览器安装并开启 AutoGLM 扩展

**优点**：能处理绝大多数被隐藏的文章内容
**缺点**：依赖特定扩展，非通用方案

### 内容验证

每个层级下载后都会验证内容完整性：
```python
def _verify_md_content(self, article_dir: Path) -> bool:
    md_files = list(article_dir.glob('*.md'))
    if not md_files:
        return False
    return md_files[0].stat().st_size >= 500
```

小于 500 字节的 Markdown 文件被认为是内容不完整，自动尝试下一层。

---

## Cookie 自动加载

`ArticleDownloader` 初始化时会自动从 `wechat_session.json` 加载 Cookie：

```python
def _load_session_cookie() -> str:
    session_file = Path("wechat_session.json")
    if session_file.exists():
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('cookie', '')
    return ''
```

这意味着用户只需登录一次，后续下载无需重复扫码。

---

## PDF 转换流程

```
Markdown 文件 → 解析标题/日期/正文 → HTML 模板渲染 → Playwright 截图 → PDF 输出
```

### 样式配置

- 标题居中、居左混排
- 正文 1.6 倍行高，14pt 字体
- 代码块灰色背景
- 图片最大宽度 100%，居中显示
- 页眉显示公众号名，页脚显示页码

---

## 已解决的坑

### 1. 文章被删除的检测

最初尝试通过 HTTP 请求预检测，但 ghost page 检测不可靠。最终采用**先下载，后清理**策略：

1. 下载所有文章（包含已删除的占位符）
2. 清理空文件夹（小于 1KB 的目录）
3. 将失败记录写入 JSON 和 Excel 第二个 sheet

### 2. PDF 与 Markdown 数量不匹配

原因：同一文章在不同日期重新发布（重复标题）。

解决方案：用标题匹配而非文件夹数量对比。匹配结果显示 Helen 育学园、安工聊港卡炒港股的 PDF 和有内容的 Markdown 数量完全一致。

### 3. m2w macOS 安全拦截

未签名的 `m2w` 二进制文件被 macOS Gatekeeper 拦截：
```
zsh: killed    ./m2w ...
```

解决：`xattr -cr ./m2w` 移除 `com.apple.quarantine` 属性。

### 4. Python 虚拟环境路径

`.venv/bin/python3` 是指向 python3.14 的 symlink，依赖包在 `.venv/lib/python3.14/site-packages/` 中。直接调用 `.venv/bin/python3` 可正常使用所有依赖。

---

## Git 管理

以下目录和文件已加入 `.gitignore`，不会推送到 GitHub：

```
WeChatArticles/
WeChatPDFs/
old/
.venv/
venv/
.DS_Store
wechat_session.json
```

每完成一个功能模块后及时 commit，保持提交粒度清晰。

---

## 待优化方向

1. **webfetch 通用化**：当前依赖 AutoGLM 扩展，可考虑 Puppeteer/Playwright 作为更通用的第三层
2. **增量下载**：记录已下载状态，避免重复下载
3. **并发下载**：多线程/异步下载加速批量处理
4. **阅读量获取**：当前因 token 限制无法获取阅读量数据
5. **图片 CDN 镜像**：微信图片超时问题，可考虑上传到图床
