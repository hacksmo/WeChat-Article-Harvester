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
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
# python -m venv venv
# venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 PDF 转换所需的 Chromium 浏览器
playwright install chromium
```

### 3. 下载 m2w 工具（用于文章下载）

从 [wechatmp2markdown releases](https://github.com/fengxxc/wechatmp2markdown/releases) 下载对应平台的可执行文件，将文件名改为 `m2w` 后放入项目根目录。

### 4. 运行程序

```bash
python main.py
```

## 使用流程

1. **微信登录** - 选择菜单 1，扫码登录微信公众号后台
2. **采集文章** - 输入公众号名称，选择下载范围
3. **下载文章** - 自动调用 m2w 下载 Markdown 和图片
4. **提取标签** - 自动分析文章内容生成标签
5. **导出 Excel** - 将数据导出为 Excel 文件
6. **导出 PDF** - 将 Markdown 文章批量转换为 PDF 文件

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

> 注意：`WeChatArticles/`（文章数据）、`WeChatPDFs/`（PDF输出）、`venv/`（虚拟环境）已加入 .gitignore，不会被提交到 GitHub。

## 常见问题

**Q: 运行时报错 "No module named 'xxx'"**
> 确保已激活虚拟环境（`source venv/bin/activate`），然后重新运行 `pip install -r requirements.txt`

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
