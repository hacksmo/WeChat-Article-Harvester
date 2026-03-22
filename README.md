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

## 目录结构

```
gpt_excel_tool/
├── modules/               # 功能模块
│   ├── login.py          # 微信登录
│   ├── fetcher.py         # 文章采集
│   ├── downloader.py      # 文章下载
│   ├── tagger.py          # 标签提取
│   ├── exporter.py        # Excel导出
│   ├── pdf_converter.py   # PDF转换
│   └── pdf_config.py     # PDF配置
├── static/                # 静态资源
│   └── pdf_styles.css     # PDF样式
├── WeChatArticles/        # 文章数据（每个公众号一个文件夹）
├── WeChatPDFs/            # PDF输出（每个公众号一个子文件夹）
├── main.py                # 主程序入口
└── requirements.txt       # Python依赖
```

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (macOS/Linux)
source venv/bin/activate

# 激活虚拟环境 (Windows)
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（用于PDF转换）
playwright install chromium
```

### 2. 下载 m2w 工具（可选，用于文章下载）

从 [wechatmp2markdown](https://github.com/fengxxc/wechatmp2markdown/releases) 下载对应平台的可执行文件，命名为 `m2w` 放入项目目录。

### 3. 运行程序

```bash
# 确保已激活虚拟环境
python main.py
```

## 使用流程

1. **微信登录** - 运行后选择菜单 1，扫码登录微信公众号后台
2. **采集文章** - 输入公众号名称，选择下载范围
3. **下载文章** - 自动调用 m2w 或 Cookie 下载 Markdown 和图片
4. **提取标签** - 自动分析文章内容生成标签
5. **导出 Excel** - 将数据导出为 Excel 文件
6. **导出 PDF** - 将 Markdown 文章批量转换为 PDF 文件

## 注意事项

- 需要拥有微信公众号后台账号（订阅号或服务号均可）
- 登录凭证有效期约 2 小时，过期需重新扫码
- 下载时会有 3-5 秒冷却机制，防止被封
- 请勿过于频繁地采集数据

## License

MIT License
