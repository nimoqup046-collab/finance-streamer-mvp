# 财经主播助手 MVP

> 📊 财经新闻自动采集 + AI内容生成工具

专为财经主播设计，一键生成直播稿、公众号文章、深度长文。

---

## 🎯 功能特点

| 功能 | 说明 |
|------|------|
| **📰 新闻采集** | 并发从东方财富、新浪财经、财联社、第一财经获取最新新闻 |
| **🔍 关键词搜索** | 实时在新闻列表中按标题/分类/来源搜索 |
| **📝 直播稿生成** | 基于“编辑部 brief + 主线判断”生成更适合口播的直播稿，可选 OpenRouter 多模型质量路由 |
| **📱 公众号文章** | 输出更强调洞察、结构与可读性的财经公众号长文，可选 OpenRouter 多模型质量路由 |
| **📄 深度长文** | 输出带框架、机会与风险并重的深度研判文章 |
| **⚡ 快报速评** | 30秒读完的短内容速评，适合社媒直发和群内快读 |
| **🚀 一键全部生成** | 六种格式**并行**生成（直播稿/公众号/深度长文/PPT脚本/快报速评/平台格式包） |
| **📑 多结果标签页** | 一键全部生成后，通过标签页切换查看多种结果 |
| **⚙️ 设置面板** | 调节直播时长、写作风格、API Key，配置自动持久化 |
| **📊 PPT 导出** | 根据选中新闻直接下载结构化汇报版 PPT |
| **🌊 流式生成** | 直播稿和全部生成支持渐进式输出，等待过程可见 |
| **🎛️ 请求级档位切换** | 前端可一键切换“跟随后端 / 省钱 / 高质量”，仅作用于直播稿与公众号 |
| **🔍 投资信号提取** | 对选中新闻生成结构化“投资信号速览”（主线/风险/验证清单） |
| **📦 平台格式包** | 一键输出抖音口播、小红书图文、微博热评、朋友圈文案 |

---

## 🚀 快速开始

### 本地运行

```bash
# 1. 配置环境变量
cat > .env << 'EOF'
AI_PROVIDER=zhipu
ZHIPU_API_KEY=your-api-key-here
ZHIPU_API_BASE=https://open.bigmodel.cn/api/paas/v4
ZHIPU_MODEL=glm-5

# 可选：只把直播稿 / 公众号切到 OpenRouter 质量路由
OPENROUTER_ENABLE_QUALITY_ROUTING=false
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_HTTP_REFERER=
OPENROUTER_APP_TITLE=finance-streamer-mvp
OPENROUTER_STREAM_MODELS=anthropic/claude-sonnet-4.6,google/gemini-3.1-pro-preview,openai/gpt-5.1
OPENROUTER_ARTICLE_MODELS=anthropic/claude-sonnet-4.6,openai/gpt-5.1,google/gemini-3.1-pro-preview
# 是否让 platform_pack 也走 OpenRouter（默认 false，省钱）
OPENROUTER_PLATFORM_PACK_ROUTING=false
QUALITY_ROUTING_AUTO_FALLBACK=true
QUALITY_ROUTING_HOURLY_BUDGET_USD=0.20
QUALITY_ROUTING_DAILY_BUDGET_USD=1.00
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
5. 在环境变量中设置 `AI_PROVIDER` 和对应的 API Key（推荐智谱：`ZHIPU_API_KEY`；默认模型建议 `glm-5`，若账号权限不足可临时切到 `glm-4.7`）
6. 如果希望只把“直播稿 / 公众号”切到更强模型，可额外配置 `OPENROUTER_*` 变量并开启 `OPENROUTER_ENABLE_QUALITY_ROUTING=true`
7. 部署完成后，可得到类似 `https://finance-streamer-mvp-production.up.railway.app` 的网址

### 方式二：阿里云轻量服务器

```bash
# 1. 购买服务器后，执行一键部署脚本
wget https://your-domain/deploy.sh
chmod +x deploy.sh
./deploy.sh

# 2. 配置环境变量
export AI_PROVIDER="zhipu"
export ZHIPU_API_KEY="your-key-here"
# export OPENROUTER_ENABLE_QUALITY_ROUTING="true"
# export OPENROUTER_API_KEY="your-openrouter-key"

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
| `ZHIPU_MODEL` | 智谱模型（默认推荐） | `glm-5` |
| `OPENROUTER_ENABLE_QUALITY_ROUTING` | 是否开启高质量内容路由（仅直播稿/公众号） | `false` |
| `OPENROUTER_API_KEY` | OpenRouter API Key | `sk-or-xxx` |
| `OPENROUTER_API_BASE` | OpenRouter API Base | `https://openrouter.ai/api/v1` |
| `OPENROUTER_HTTP_REFERER` | OpenRouter 可选来源标识 | `` |
| `OPENROUTER_APP_TITLE` | OpenRouter 应用标题 | `finance-streamer-mvp` |
| `OPENROUTER_STREAM_MODELS` | 直播稿候选模型列表 | `anthropic/claude-sonnet-4.6,google/gemini-3.1-pro-preview,openai/gpt-5.1` |
| `OPENROUTER_ARTICLE_MODELS` | 公众号候选模型列表 | `anthropic/claude-sonnet-4.6,openai/gpt-5.1,google/gemini-3.1-pro-preview` |
| `OPENROUTER_PLATFORM_PACK_ROUTING` | 平台格式包是否走 OpenRouter（默认关闭省成本） | `false` |
| `QUALITY_ROUTING_AUTO_FALLBACK` | 超预算是否自动降级到基础 provider | `true` |
| `QUALITY_ROUTING_HOURLY_BUDGET_USD` | 质量路由每小时预算上限（0 关闭） | `0.20` |
| `QUALITY_ROUTING_DAILY_BUDGET_USD` | 质量路由每日预算上限（0 关闭） | `1.00` |
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
5. 在顶部“请求档位”选择：`跟随后端 / 省钱 / 高质量`（会自动记忆本机选择）
6. 点击生成按钮（直播稿/公众号/深度长文/全部生成）
7. 等待 AI 生成完成
8. 通过标签页切换不同格式，复制、下载或导出 PPT
9. 可在新闻区点击“提取投资信号”先看结构化判断，再决定要生成哪类内容

### OpenRouter 质量路由

- 开启 `OPENROUTER_ENABLE_QUALITY_ROUTING=true` 后：
  - `stream_script` 和 `article` 会优先走 OpenRouter 多模型 fallback
  - `deep_dive`、`ppt_script`、`flash_report`、`platform_pack` 默认继续走基础 provider（可通过 `OPENROUTER_PLATFORM_PACK_ROUTING=true` 打开）
- 如果配置了预算阈值（`QUALITY_ROUTING_*_BUDGET_USD`），超预算时会自动降级到基础 provider（默认 `AI_PROVIDER`）。
- 推荐 Railway 组合：
  - `AI_PROVIDER=zhipu`
  - `OPENROUTER_ENABLE_QUALITY_ROUTING=true`
  - `OPENROUTER_API_KEY=...`
  - `OPENROUTER_STREAM_MODELS=anthropic/claude-sonnet-4.6,google/gemini-3.1-pro-preview,openai/gpt-5.1`
  - `OPENROUTER_ARTICLE_MODELS=anthropic/claude-sonnet-4.6,openai/gpt-5.1,google/gemini-3.1-pro-preview`

### OpenRouter 档位一键切换（省钱/高质量）

- 脚本：`scripts/switch_openrouter_profile.sh`
- 默认作用于 `production` 环境和 `finance-streamer-mvp` 服务。

```bash
# 省钱档（Gemini 优先）
./scripts/switch_openrouter_profile.sh cheap

# 高质量档（Claude 优先）
./scripts/switch_openrouter_profile.sh quality

# 只改变量，不立即部署
./scripts/switch_openrouter_profile.sh cheap --no-deploy
```

### 请求级档位切换（前端一键）

- 页面顶部提供三档：`跟随后端`、`省钱`、`高质量`。
- 仅影响 `stream_script` 与 `article` 两类生成请求。
- `跟随后端`：不传 `quality_profile`，完全使用服务端默认路由。
- `省钱 / 高质量`：前端会在请求体中透传 `quality_profile=cheap|quality`。
- 优先级说明：预算护栏高于请求档位。即使用户选择“高质量”，若超预算也会自动降级到基础 provider，并在状态与日志可见。

### 内容质量开发验收

- 固定样例集：`benchmarks/content_quality_cases.json`
- 评分 rubric：`benchmarks/content_quality_rubric.json`
- 本地 benchmark 脚本：`scripts/benchmark_content_quality.py`

示例：

```bash
python3 scripts/benchmark_content_quality.py --dry-run
python3 scripts/benchmark_content_quality.py --output /tmp/content-quality-report.md
```

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

### 提取投资信号
```
POST /api/news/score
{
  "news_ids": ["id1", "id2"],
  "focus_topic": "可选，聚焦主题"
}
```

### 生成内容
```
POST /api/generate
{
  "news_ids": ["id1", "id2"],
  "content_type": "stream_script",  // stream_script | article | deep_dive | ppt_script | flash_report | platform_pack
  "duration": 30,
  "style": "专业",
  "quality_profile": "quality"      // 可选：cheap | quality；仅对 stream_script/article 生效
}
```

### 一键全部生成（并行，返回 6 类结果）
```
POST /api/generate/all
["id1", "id2"]

// 新增兼容对象体（推荐在前端显式档位时使用）
{
  "news_ids": ["id1", "id2"],
  "quality_profile": "cheap"        // 可选：cheap | quality
}

// 返回: stream_script / article / deep_dive / ppt_script / flash_report / platform_pack
```

### 流式生成（SSE）
```
POST /api/generate/stream
{
  "news_ids": ["id1", "id2"],
  "content_type": "stream_script",  // stream_script | article | deep_dive | ppt_script | flash_report | all
  "duration": 30,
  "style": "专业",
  "quality_profile": "quality"      // 可选：cheap | quality；仅对 stream_script/article 生效
}
```

### 生成 PPT 脚本（文本结果）
```
POST /api/generate
{
  "news_ids": ["id1", "id2"],
  "content_type": "ppt_script"
}
```

### 生成 PPT 文件（.pptx 下载）
```
POST /api/generate/ppt
["id1", "id2"]
```

### 健康检查
```
GET /health
```

### 质量路由状态
```
GET /api/status
```

返回中包含：
- `quality_routing`：后端是否启用质量路由
- `quality_router_provider`：质量路由提供商（如 `openrouter`）
- `quality_routed_types`：当前后端允许走质量路由的内容类型

### 成本状态（近窗口估算）
```
GET /api/status/cost
```

返回包含：
- `totals`：当前内存窗口汇总
- `recent_1h`：最近 1 小时汇总
- `recent_24h`：最近 24 小时汇总
- `budget_guard`：预算保护状态（是否超限、触发原因、实时窗口花费）

---

## 🧭 主线基底

- 内容与工程主线说明：`docs/claude-core-baseline.md`
- 后续内容质量优化默认以 `PR #7` 为内容基底、以 `PR #8` 为整合基底、以 `PR #6` 为交互基底

---

## 🎨 待开发功能

- [ ] 信息图生成
- [ ] 用户系统
- [ ] 历史记录持久化升级（IndexedDB / 服务端同步）
- [ ] 更多新闻源（界面新闻、华尔街见闻等扩展源）
- [ ] 更精细的流式输出（逐 token / 可中断恢复）

---

## 📄 License

MIT
