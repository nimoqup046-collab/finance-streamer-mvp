"""
财经主播助手 MVP 版本
FastAPI 主入口
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Depends, Header, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.config import (
    CORS_ORIGINS,
    PORT,
    API_KEY,
    NEWS_CACHE_MINUTES,
    USE_MOCK_NEWS,
)
from backend.fetcher import fetcher
from backend.generator import generator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 创建FastAPI应用
app = FastAPI(
    title="财经主播助手 MVP",
    description="财经新闻自动采集与内容生成工具",
    version="1.0.0"
)

# 配置CORS
# 当 origins 为通配符时，浏览器规范不允许同时开启 allow_credentials
_allow_credentials = "*" not in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# API Key 认证依赖（未设置 API_KEY 环境变量时跳过校验）
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="无效的API密钥")

# 请求模型
class GenerateRequest(BaseModel):
    news_ids: List[str]
    content_type: str  # stream_script, article, deep_dive, ppt, flash_report
    duration: Optional[int] = 30
    style: Optional[str] = "专业"
    title: Optional[str] = ""
    focus_topic: Optional[str] = ""

class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    time: str
    category: str

# 内存存储（MVP版本够用）
news_cache: List[dict] = []
cache_time: datetime = None
fallback_used_last_fetch: bool = False
_cache_lock: asyncio.Lock = None


def _get_cache_lock() -> asyncio.Lock:
    """延迟初始化 asyncio.Lock（需在事件循环启动后创建）"""
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


async def refresh_news_cache(force: bool = False) -> List[dict]:
    """在生成前兜底刷新缓存，避免多实例下缓存丢失（加锁防并发重复抓取）"""
    global news_cache, cache_time, fallback_used_last_fetch

    if not force and news_cache and cache_time:
        cache_age = (datetime.now() - cache_time).total_seconds()
        if cache_age < NEWS_CACHE_MINUTES * 60:
            return news_cache

    async with _get_cache_lock():
        # 再次检查，防止并发情况下重复抓取
        if not force and news_cache and cache_time:
            cache_age = (datetime.now() - cache_time).total_seconds()
            if cache_age < NEWS_CACHE_MINUTES * 60:
                return news_cache

        fallback_used = False
        if USE_MOCK_NEWS:
            news_list = await fetcher.fetch_mock_news()
            fallback_used = True
        else:
            try:
                news_list = await fetcher.fetch_all_news()
                if not news_list:
                    raise RuntimeError("未获取到新闻")
            except Exception:
                news_list = await fetcher.fetch_mock_news()
                fallback_used = True

        news_cache = news_list
        cache_time = datetime.now()
        fallback_used_last_fetch = fallback_used
    return news_cache

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# 获取新闻列表
@app.get("/api/news")
async def get_news(refresh: bool = False):
    """获取今日财经新闻"""
    global news_cache, cache_time, fallback_used_last_fetch

    # 检查缓存
    if not refresh and news_cache and cache_time:
        cache_age = (datetime.now() - cache_time).total_seconds()
        if cache_age < NEWS_CACHE_MINUTES * 60:
            return {
                "data": news_cache,
                "count": len(news_cache),
                "cached": True,
                "update_time": cache_time.isoformat()
            }

    # 获取新新闻
    try:
        await refresh_news_cache(force=True)
        fallback_used = fallback_used_last_fetch

        return {
            "data": news_cache,
            "count": len(news_cache),
            "cached": False,
            "fallback": fallback_used,
            "update_time": cache_time.isoformat()
        }
    except Exception as e:
        logger.error("获取新闻失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="获取新闻失败，请稍后重试")

# 获取新闻分类
@app.get("/api/news/categories")
async def get_categories():
    """获取新闻分类"""
    return {
        "categories": ["宏观", "A股", "美股", "行业", "个股", "财经"],
        "sources": ["东方财富网", "新浪财经", "财联社"]
    }


# 搜索新闻
@app.get("/api/news/search")
async def search_news(q: str = Query(..., min_length=1, description="搜索关键词")):
    """按关键词搜索当前缓存的新闻"""
    if not news_cache:
        await refresh_news_cache()

    keyword = q.strip().lower()
    matched = [
        n for n in news_cache
        if keyword in n.get("title", "").lower()
        or keyword in n.get("category", "").lower()
        or keyword in n.get("source", "").lower()
    ]
    return {"data": matched, "count": len(matched), "keyword": q}

# 新闻影响力评分（Reportify信号提取思路）
@app.post("/api/news/score", dependencies=[Depends(verify_api_key)])
async def score_news(news_ids: List[str] = Body(...)):
    """对选中新闻进行投资信号提取与影响力评分
    返回：结构化信号（受益方/风险方/紧迫度）+ 新闻影响力排序
    """
    global news_cache
    if not news_cache:
        await refresh_news_cache()

    selected_news = [n for n in news_cache if n["id"] in news_ids]
    if not selected_news:
        raise HTTPException(status_code=400, detail="未找到选中的新闻")

    try:
        signals = await generator._extract_news_signals(selected_news)
        return {
            "signals": signals,
            "news_count": len(selected_news),
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("信号提取失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="信号提取失败，请稍后重试")


# 生成内容
@app.post("/api/generate", dependencies=[Depends(verify_api_key)])
async def generate_content(request: GenerateRequest):
    """生成指定类型的内容"""
    global news_cache

    if not news_cache:
        await refresh_news_cache()

    # 根据ID筛选新闻
    selected_news = [n for n in news_cache if n["id"] in request.news_ids]

    if not selected_news:
        await refresh_news_cache(force=True)
        selected_news = [n for n in news_cache if n["id"] in request.news_ids]

    if not selected_news:
        raise HTTPException(status_code=400, detail="未找到选中的新闻")

    try:
        if request.content_type == "stream_script":
            content = await generator.generate_stream_script(
                selected_news,
                duration=request.duration or 30,
                style=request.style or "专业"
            )
            return {
                "type": "stream_script",
                "content": content,
                "word_count": len(content),
                "generated_at": datetime.now().isoformat()
            }

        elif request.content_type == "article":
            result = await generator.generate_article(
                selected_news,
                title=request.title or ""
            )
            return {
                "type": "article",
                **result,
                "generated_at": datetime.now().isoformat()
            }

        elif request.content_type == "deep_dive":
            content = await generator.generate_deep_dive(
                selected_news,
                focus_topic=request.focus_topic or ""
            )
            return {
                "type": "deep_dive",
                "content": content,
                "word_count": len(content),
                "generated_at": datetime.now().isoformat()
            }

        elif request.content_type == "ppt":
            content = await generator.generate_ppt(
                selected_news,
                focus_topic=request.focus_topic or ""
            )
            return {
                "type": "ppt",
                "content": content,
                "word_count": len(content),
                "generated_at": datetime.now().isoformat()
            }

        elif request.content_type == "flash_report":
            content = await generator.generate_flash_report(selected_news)
            return {
                "type": "flash_report",
                "content": content,
                "word_count": len(content),
                "generated_at": datetime.now().isoformat()
            }

        else:
            raise HTTPException(status_code=400, detail="不支持的内容类型")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("内容生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="内容生成失败，请稍后重试")

# 批量生成（一键生成全部）
@app.post("/api/generate/all", dependencies=[Depends(verify_api_key)])
async def generate_all(news_ids: List[str] = Body(...)):
    """一键生成所有类型的内容"""
    global news_cache

    if not news_cache:
        await refresh_news_cache()

    selected_news = [n for n in news_cache if n["id"] in news_ids]

    if not selected_news:
        await refresh_news_cache(force=True)
        selected_news = [n for n in news_cache if n["id"] in news_ids]

    if not selected_news:
        raise HTTPException(status_code=400, detail="未找到选中的新闻")

    try:
        stream_script, article, deep_dive, ppt = await asyncio.gather(
            generator.generate_stream_script(selected_news),
            generator.generate_article(selected_news),
            generator.generate_deep_dive(selected_news),
            generator.generate_ppt(selected_news),
        )
        results = {
            "stream_script": stream_script,
            "article": article,
            "deep_dive": deep_dive,
            "ppt": ppt,
            "generated_at": datetime.now().isoformat()
        }
        return results
    except Exception as e:
        logger.error("批量生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="内容生成失败，请稍后重试")

# 获取系统状态
@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return {
        "status": "running",
        "news_count": len(news_cache),
        "last_update": cache_time.isoformat() if cache_time else None,
        "features": {
            "stream_script": True,
            "article": True,
            "deep_dive": True,
            "ppt": True,
            "flash_report": True,
            "news_score": True,
            "infographic": False
        }
    }

# 挂载前端静态文件
frontend_path = Path(__file__).parent.parent / "frontend"
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# 启动说明
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "财经主播助手 MVP 版本",
        "version": "1.0.0",
        "endpoints": {
            "news": "/api/news",
            "generate": "/api/generate",
            "status": "/api/status",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
