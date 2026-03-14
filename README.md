# 财经主播助手 MVP

> 📊 财经新闻自动采集 + AI内容生成工具

专为财经主播设计，一键生成直播稿、公众号文章、深度长文。

---

## 🎯 功能特点

| 功能 | 说明 |
|------|------|
| **📰 新闻采集** | 并发从东方财富、新浪财经、财联社、第一财经获取最新新闻 |
| **🔍 关键词搜索** | 实时在新闻列表中按标题/分类/来源搜索 |
| **📝 直播稿生成** | 基于“编辑部 brief + 主线判断”生成更适合口播的直播稿 |
| **📱 公众号文章** | 输出更强调洞察、结构与可读性的财经公众号长文 |
| **📄 深度长文** | 输出带框架、机会与风险并重的深度研判文章 |
| **🚀 一键全部生成** | 三种格式**并行**生成，比逐个生成快 3 倍 |
| **📑 多结果标签页** | 一键全部生成后，通过标签页切换查看三种结果 |
| **⚙️ 设置面板** | 调节直播时长、写作风格、API Key，配置自动持久化 |
| **📊 PPT 导出** | 根据选中新闻直接下载结构化汇报版 PPT |
| **🌊 流式生成** | 直播稿和全部生成支持渐进式输出，等待过程可见 |

---

## 🚀 快速开始

### 本地运行

```bash
# 1. 配置环境变量
cat > .env << 'EOF'
AI_PROVIDER=zhipu
ZHIPU_API_KEY=your-api-key-here
ZHIPU_API_BASE=https://open.bigmodel.cn/api/paas/v4
ZHIPU_MODEL=glm-4.7
EOF

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动后端
python -m uvicorn backend.main:app --reload

# 4. 启动前端静态页（新终端）
cd frontend
python3 -m http.server 4173
```

后端访问：http://localhost:8000

前端访问：http://localhost:4173

本地体验默认直连已部署的 Railway 后端，配置位于 `frontend/config.js`。

---

## 🌐 云端部署

### 方式一：Railway.app（推荐）

1. 将代码推送到 GitHub
2. 登录 [Railway.app](https://railway.app)
3. 新建项目 → 选择 GitHub 仓库
4. 使用仓库内的 `Dockerfile` 作为唯一部署入口
5. 在环境变量中设置 `AI_PROVIDER` 和对应的 API Key（推荐智谱：`ZHIPU_API_KEY`）
6. 部署完成后，可得到类似 `https://finance-streamer-mvp-production.up.railway.app` 的网址

### 方式二：阿里云轻量服务器

```bash
# 1. 购买服务器后，执行一键部署脚本
wget https://your-domain/deploy.sh
chmod +x deploy.sh
./deploy.sh

# 2. 配置环境变量
export AI_PROVIDER="zhipu"
export ZHIPU_API_KEY="your-key-here"

# 3. 重启服务
systemctl restart finance-assistant
```

### 前端本地体验

1. 保持 Railway 后端在线
2. 编辑 `frontend/config.js` 中的 `window.API_BASE`
3. 在 `frontend/` 目录执行 `python3 -m http.server 4173`

---

## 📁 项目结构

```
finance-streamer-mvp/
├── backend/
│   ├── main.py          # FastAPI 主入口（含 search / stream / ppt 接口）
│   ├── config.py        # 配置文件
│   ├── fetcher.py       # 新闻并发爬取 + 智能去重
│   └── generator.py     # AI 异步内容生成 + PPT 导出
├── Dockerfile           # Railway Docker 部署入口
├── frontend/
│   ├── index.html       # 主页面（含搜索、设置面板、多结果标签页）
│   ├── style.css        # 样式
│   ├── config.js        # 前端 API 地址配置
│   └── app.js           # 前端逻辑（含本地持久化设置）
├── requirements.txt
├── railway.toml         # Railway 部署配置
└── README.md
```

---

## 🔧 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `AI_PROVIDER` | AI 提供商 | `zhipu` |
| `ZHIPU_API_KEY` | 智谱 API Key | `xxx` |
| `ZHIPU_API_BASE` | 智谱 API Base | `https://open.bigmodel.cn/api/paas/v4` |
| `ZHIPU_MODEL` | 智谱模型（推荐中文写作） | `glm-4.7` |
| `DOUBAO_API_KEY` | 豆包 API Key | `xxx` |
| `DOUBAO_API_BASE` | 豆包 API Base | `https://ark.cn-beijing.volces.com/api/v3` |
| `DOUBAO_ENDPOINT_ID` | 方舟推理接入点 ID，优先于模型名 | `ep-202503...` |
| `DOUBAO_MODEL` | 豆包模型 | `doubao-1-5-pro-32k-250115` |
| `ANTHROPIC_API_KEY` | Anthropic API Key | `sk-ant-xxx` |
| `ANTHROPIC_MODEL` | Anthropic 模型 | `claude-sonnet-4-20250514` |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-xxx` |
| `OPENAI_API_BASE` | OpenAI API Base | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI 模型 | `gpt-4o-mini` |
| `PORT` | 服务端口 | `8000` |
| `CORS_ORIGINS` | 允许跨域来源 | `*` |
| `NEWS_CACHE_MINUTES` | 新闻缓存分钟数 | `30` |
| `USE_MOCK_NEWS` | 是否强制使用模拟新闻 | `false` |
| `API_KEY` | 接口鉴权密钥（生产环境建议设置）| `your-secret` |

---

## 📝 使用流程

1. 打开网站，系统自动加载今日新闻（默认热点优先，最多 100 条）
2. 使用“热点优先 / 最新优先”、搜索框或分类标签筛选感兴趣的新闻
3. 勾选需要播报的新闻
4. 在右侧调整直播时长和写作风格
5. 点击生成按钮（直播稿/公众号/深度长文/全部生成）
6. 等待 AI 生成完成
7. 通过标签页切换不同格式，复制、下载或导出 PPT

---

## 🔄 API 接口

### 获取新闻
```
GET /api/news?refresh=true
```

### 搜索新闻
```
GET /api/news/search?q=关键词
```

### 生成内容
```
POST /api/generate
{
  "news_ids": ["id1", "id2"],
  "content_type": "stream_script",  // stream_script | article | deep_dive
  "duration": 30,
  "style": "专业"
}
```

### 一键全部生成（并行）
```
POST /api/generate/all
["id1", "id2"]
```

### 流式生成（SSE）
```
POST /api/generate/stream
{
  "news_ids": ["id1", "id2"],
  "content_type": "stream_script",  // stream_script | article | deep_dive | all
  "duration": 30,
  "style": "专业"
}
```

### 生成 PPT
```
POST /api/generate/ppt
["id1", "id2"]
```

### 健康检查
```
GET /health
```

---

## 🎨 待开发功能

- [ ] 信息图生成
- [ ] 用户系统
- [ ] 历史记录持久化升级（IndexedDB / 服务端同步）
- [ ] 更多新闻源（证券时报、界面新闻等扩展源）
- [ ] 更精细的流式输出（逐 token / 可中断恢复）

---

## 📄 License

MIT
