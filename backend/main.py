"""
财经主播助手 MVP 版本
FastAPI 主入口
"""
import asyncio
import json
import sys
import os
import logging
import time
from pathlib import Path
from urllib.parse import quote
from collections import defaultdict, deque

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Depends, Header, Body, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    content_type: str  # stream_script, article, deep_dive
    duration: Optional[int] = 30
    style: Optional[str] = "专业"
    title: Optional[str] = ""

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
_rate_limit_lock: asyncio.Lock = None
_generate_requests = defaultdict(deque)
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 6


def _get_cache_lock() -> asyncio.Lock:
    """延迟初始化 asyncio.Lock（需在事件循环启动后创建）"""
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def _get_rate_limit_lock() -> asyncio.Lock:
    global _rate_limit_lock
    if _rate_limit_lock is None:
        _rate_limit_lock = asyncio.Lock()
    return _rate_limit_lock


def _get_client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_generate_rate_limit(request: Request):
    client_key = _get_client_key(request)
    now = time.monotonic()
    async with _get_rate_limit_lock():
        bucket = _generate_requests[client_key]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning("Rate limit exceeded for client=%s", client_key)
            raise HTTPException(status_code=429, detail="生成请求过于频繁，请稍后再试")
        bucket.append(now)


async def _resolve_selected_news(news_ids: List[str]) -> List[dict]:
    global news_cache

    if not news_cache:
        await refresh_news_cache()

    selected_news = [n for n in news_cache if n["id"] in news_ids]
    if not selected_news:
        await refresh_news_cache(force=True)
        selected_news = [n for n in news_cache if n["id"] in news_ids]
    if not selected_news:
        raise HTTPException(status_code=400, detail="未找到选中的新闻")
    return selected_news


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
                started = time.monotonic()
                news_list = await fetcher.fetch_all_news()
                logger.info("fetch_all_news completed in %.2fs", time.monotonic() - started)
                if not news_list:
                    raise RuntimeError("未获取到新闻")
            except Exception:
                news_list = await fetcher.fetch_mock_news()
                fallback_used = True
                logger.warning("真实新闻抓取失败，回退 mock 数据")

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
        "sources": ["东方财富网", "新浪财经", "财联社", "第一财经"]
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

# 生成内容
@app.post("/api/generate", dependencies=[Depends(verify_api_key), Depends(enforce_generate_rate_limit)])
async def generate_content(request: GenerateRequest):
    """生成指定类型的内容"""
    selected_news = await _resolve_selected_news(request.news_ids)

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
            content = await generator.generate_deep_dive(selected_news)
            return {
                "type": "deep_dive",
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
@app.post("/api/generate/all", dependencies=[Depends(verify_api_key), Depends(enforce_generate_rate_limit)])
async def generate_all(news_ids: List[str] = Body(...)):
    """一键生成所有类型的内容"""
    selected_news = await _resolve_selected_news(news_ids)

    try:
        stream_script, article, deep_dive = await asyncio.gather(
            generator.generate_stream_script(selected_news),
            generator.generate_article(selected_news),
            generator.generate_deep_dive(selected_news),
        )
        results = {
            "stream_script": stream_script,
            "article": article,
            "deep_dive": deep_dive,
            "generated_at": datetime.now().isoformat()
        }
        return results
    except Exception as e:
        logger.error("批量生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="内容生成失败，请稍后重试")


@app.post("/api/generate/ppt", dependencies=[Depends(verify_api_key), Depends(enforce_generate_rate_limit)])
async def generate_ppt(news_ids: List[str] = Body(...)):
    """根据选中新闻生成 PPT 并返回下载流。"""
    selected_news = await _resolve_selected_news(news_ids)
    started = time.monotonic()
    try:
        pptx_bytes = await generator.generate_ppt(selected_news)
        logger.info("PPT generated in %.2fs for %s news", time.monotonic() - started, len(selected_news))
        filename = f"财经日报_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
        quoted = quote(filename)
        return StreamingResponse(
            iter([pptx_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PPT 生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="PPT 生成失败，请稍后重试")


@app.post("/api/generate/stream", dependencies=[Depends(verify_api_key), Depends(enforce_generate_rate_limit)])
async def generate_stream(request: Request, payload: GenerateRequest):
    """通过 SSE 流式返回生成进度和内容。"""
    selected_news = await _resolve_selected_news(payload.news_ids)

    async def event_stream():
        started = time.monotonic()
        logger.info("SSE generation started type=%s news_count=%s", payload.content_type, len(selected_news))
        try:
            yield _sse("status", {"step": 0, "text": "准备生成", "tip": "正在校验新闻与参数"})

            if payload.content_type == "all":
                yield _sse("status", {"step": 1, "text": "并行生成中", "tip": "直播稿流式输出，其他内容后台并行生成"})
                article_task = asyncio.create_task(generator.generate_article(selected_news, title=payload.title or ""))
                deep_task = asyncio.create_task(generator.generate_deep_dive(selected_news))

                raw_script = []
                async for chunk in generator.stream_stream_script(
                    selected_news,
                    duration=payload.duration or 30,
                    style=payload.style or "专业",
                ):
                    if await request.is_disconnected():
                        logger.info("SSE client disconnected during all-generation stream")
                        return
                    raw_script.append(chunk)
                    yield _sse("chunk", {"result_type": "stream_script", "delta": chunk})

                stream_script = generator._format_stream_script("".join(raw_script), selected_news)
                yield _sse("result", {"result_type": "stream_script", "result": stream_script})

                article = await article_task
                yield _sse("result", {"result_type": "article", "result": article})

                deep_dive = await deep_task
                yield _sse("result", {"result_type": "deep_dive", "result": deep_dive})

                results = {
                    "stream_script": stream_script,
                    "article": article,
                    "deep_dive": deep_dive,
                    "generated_at": datetime.now().isoformat(),
                }
                yield _sse("complete", {"type": "all", "results": results})
            else:
                yield _sse("status", {"step": 1, "text": "开始生成", "tip": "正在向模型请求内容"})

                if payload.content_type == "stream_script":
                    raw_script = []
                    async for chunk in generator.stream_stream_script(
                        selected_news,
                        duration=payload.duration or 30,
                        style=payload.style or "专业",
                    ):
                        if await request.is_disconnected():
                            logger.info("SSE client disconnected during stream_script")
                            return
                        raw_script.append(chunk)
                        yield _sse("chunk", {"result_type": "stream_script", "delta": chunk})

                    result = generator._format_stream_script("".join(raw_script), selected_news)
                elif payload.content_type == "article":
                    result = await generator.generate_article(selected_news, title=payload.title or "")
                elif payload.content_type == "deep_dive":
                    result = await generator.generate_deep_dive(selected_news)
                else:
                    raise HTTPException(status_code=400, detail="不支持的流式内容类型")

                yield _sse("complete", {"type": payload.content_type, "result": result})

            logger.info("SSE generation finished type=%s in %.2fs", payload.content_type, time.monotonic() - started)
        except HTTPException as e:
            yield _sse("error", {"message": e.detail})
        except Exception as e:
            logger.error("SSE generation failed: %s", e, exc_info=True)
            yield _sse("error", {"message": "流式生成失败，前端将回退普通生成"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

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
            "infographic": False  # 待开发
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
