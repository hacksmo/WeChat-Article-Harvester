# 微信文章批量采集工具

一款基于微信公众号后台 API 的文章批量采集工具，支持扫码登录、文章采集、本地下载、标签提取、Excel 导出和 PDF 转换。

## 功能特性

- **微信扫码登录** - 无需手动配置凭证，安全便捷
- **批量采集** - 获取公众号所有历史文章列表
- **阅读量获取** - 自动采集文章阅读量数据
- **本地下载** - Markdown + 本地图片保存
- **智能标签** - 基于关键词提取自动打标签
- **Excel 导出** - 数据导出为 Excel 方便分析
- **PDF 转换** - 将 Markdown 文章批量转换为 PDF 文件

## 环境要求

- Python >= 3.10
- macOS / Linux / Windows

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/hacksmo/WeChat-Article-Harvester.git
cd WeChat-Article-Harvester
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 3. 下载 m2w 工具（用于文章下载）

从 [wechatmp2markdown releases](https://github.com/fengxxc/wechatmp2markdown/releases) 下载对应平台的可执行文件，将文件名改为 `m2w` 后放入项目根目录。

macOS 用户需要移除安全限制：

```bash
xattr -cr ./m2w
```

### 4. 运行程序

```bash
python main.py
```

## 菜单说明

```
1. 微信扫码登录
2. 采集公众号文章列表
3. 批量下载文章
4. 提取文章标签
5. 导出 Excel
6. 查看采集数据
7. 查看下载失败记录
8. 清理空文件夹
9. 导出 PDF
0. 退出
```

## 下载机制

文章下载采用三层兜底策略，优先使用本地工具，失败后自动切换：

1. **m2w** - 本地 Chrome 浏览器渲染后抓取（需要 m2w 工具）
2. **HTTP** - 直接请求文章接口（需要 Cookie）
3. **webfetch** - 通过 AutoGLM API 渲染获取（需要 AutoGLM 扩展）

下载前会验证内容完整性（Markdown ≥500 字节），内容过少时自动尝试下一层。

## 目录结构

```
WeChat-Article-Harvester/
├── main.py              # 主程序入口
├── requirements.txt      # Python 依赖
├── m2w                  # 文章下载工具（需手动下载放入）
├── modules/             # 功能模块
│   ├── login.py         # 微信登录
│   ├── fetcher.py       # 文章采集
│   ├── downloader.py    # 文章下载
│   ├── tagger.py        # 标签提取
│   ├── exporter.py      # Excel导出
│   ├── pdf_converter.py # PDF转换
│   └── pdf_config.py    # PDF配置
└── static/              # 静态资源
    └── pdf_styles.css   # PDF样式
```

> 注意：`WeChatArticles/`（文章数据）、`WeChatPDFs/`（PDF输出）、`.venv/`（虚拟环境）、`old/`（历史文件）已加入 .gitignore，不会被提交到 GitHub。

## 常见问题

**Q: 运行时报错 "No module named 'xxx'"**
> 确保已激活虚拟环境（`source .venv/bin/activate`），然后重新运行 `pip install -r requirements.txt`

**Q: PDF 转换失败**
> 确保已运行 `playwright install chromium`

**Q: 文章下载失败**
> 确保已将 m2w 工具放入项目根目录，并赋予执行权限：
> ```bash
> chmod +x m2w
> ```

## 注意事项

- 需要拥有微信公众号后台账号（订阅号或服务号均可）
- 登录凭证有效期约 2 小时，过期需重新扫码
- 下载时会有 3-5 秒冷却机制，防止被封
- 请勿过于频繁地采集数据

## License

MIT License
