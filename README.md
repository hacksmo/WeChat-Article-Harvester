# 微信文章批量采集工具

一款基于微信公众号后台 API 的文章批量采集工具，支持扫码登录、文章采集、本地下载、标签提取和 Excel 导出。

## 功能特性

- 📱 **微信扫码登录** - 无需手动配置凭证，安全便捷
- 🔍 **批量采集** - 获取公众号所有历史文章列表
- 📊 **阅读量获取** - 自动采集文章阅读量数据
- 📥 **本地下载** - Markdown + 本地图片保存
- 🏷️ **智能标签** - 基于关键词提取自动打标签
- 📤 **Excel 导出** - 数据导出为 Excel 方便分析

## 目录结构

```
gpt_excel_tool/
├── modules/               # 功能模块
│   ├── login.py          # 微信登录
│   ├── fetcher.py        # 文章采集
│   ├── downloader.py     # 文章下载
│   ├── tagger.py         # 标签提取
│   └── exporter.py       # Excel导出
├── articles/             # 文章内容存储
├── articles_data/        # JSON数据存储
├── m2w                   # 文章转Markdown工具
├── main.py               # 主程序入口
└── requirements.txt      # Python依赖
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
```

### 2. 下载 m2w 工具

从 [wechatmp2markdown](https://github.com/fengxxc/wechatmp2markdown/releases) 下载对应平台的可执行文件，命名为 `m2w` 放入项目目录。

### 3. 运行程序

```bash
# 确保已激活虚拟环境
python main.py
```

## 使用流程

1. **微信登录** - 运行后选择菜单1，扫码登录微信公众号后台
2. **采集文章** - 输入公众号名称，选择下载范围
3. **下载文章** - 自动调用 m2w 下载 Markdown 和图片
4. **提取标签** - 自动分析文章内容生成标签
5. **导出Excel** - 将数据导出为 Excel 文件

## 注意事项

- 需要拥有微信公众号后台账号（订阅号或服务号均可）
- 登录凭证有效期约 2 小时，过期需重新扫码
- 下载时会有 3-5 秒冷却机制，防止被封
- 请勿过于频繁地采集数据

## License

MIT License
