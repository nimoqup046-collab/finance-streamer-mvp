# 财经主播助手 MVP

> 📊 财经新闻自动采集 + AI内容生成工具

专为财经主播设计，一键生成直播稿、公众号文章、深度长文。

---

## 🎯 功能特点

| 功能 | 说明 |
|------|------|
| **📰 新闻采集** | 自动从东方财富、新浪财经、财联社获取最新新闻 |
| **📝 直播稿生成** | 根据选中新闻生成专业直播脚本 |
| **📱 公众号文章** | 生成可直接粘贴到微信公众号的格式化文章 |
| **📄 深度长文** | 生成深度调研分析报告 |
| **🚀 一键生成** | 同时生成多种格式内容 |

---

## 🚀 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 AI API Key

# 3. 启动服务
python -m uvicorn backend.main:app --reload
```

访问：http://localhost:8000

---

## 🌐 云端部署

### 方式一：Railway.app（推荐）

1. 将代码推送到 GitHub
2. 登录 [Railway.app](https://railway.app)
3. 新建项目 → 选择 GitHub 仓库
4. 在环境变量中设置 `AI_API_KEY`
5. 部署完成，获得一个 `xxx.railway.app` 网址

### 方式二：阿里云轻量服务器

```bash
# 1. 购买服务器后，执行一键部署脚本
wget https://your-domain/deploy.sh
chmod +x deploy.sh
./deploy.sh

# 2. 配置环境变量
export AI_API_KEY="your-key-here"

# 3. 重启服务
systemctl restart finance-assistant
```

---

## 📁 项目结构

```
finance-streamer-mvp/
├── backend/
│   ├── main.py          # FastAPI 主入口
│   ├── config.py        # 配置文件
│   ├── fetcher.py       # 新闻爬取
│   └── generator.py     # AI 内容生成
├── frontend/
│   ├── index.html       # 主页面
│   ├── style.css        # 样式
│   └── app.js           # 前端逻辑
├── requirements.txt
├── railway.toml         # Railway 部署配置
└── README.md
```

---

## 🔧 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `AI_API_KEY` | AI 服务 API Key | `sk-xxx` |
| `AI_API_BASE` | API 接口地址 | `https://api.openai.com/v1` |
| `AI_MODEL` | 使用的模型 | `gpt-4o-mini` |
| `PORT` | 服务端口 | `8000` |

---

## 📝 使用流程

1. 打开网站，系统自动加载今日新闻
2. 勾选需要播报的新闻
3. 点击生成按钮（直播稿/公众号/深度长文）
4. 等待 2-3 分钟，AI 生成完成
5. 复制或下载生成的内容

---

## 🔄 API 接口

### 获取新闻
```
GET /api/news?refresh=true
```

### 生成内容
```
POST /api/generate
{
  "news_ids": ["id1", "id2"],
  "content_type": "stream_script",
  "duration": 30,
  "style": "专业"
}
```

### 健康检查
```
GET /health
```

---

## 🎨 待开发功能

- [ ] PPT 自动生成
- [ ] 信息图生成
- [ ] 新闻去重优化
- [ ] 更多新闻源
- [ ] 历史记录保存
- [ ] 用户系统

---

## 📄 License

MIT
