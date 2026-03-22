"""
配置文件
所有敏感信息通过环境变量设置
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 基础工具
def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _parse_csv(value: str, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or list(default)


def _parse_float(value: str, default: float = 0.0) -> float:
    if value is None or not str(value).strip():
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

# AI 提供商配置
AI_PROVIDER = os.getenv("AI_PROVIDER", "zhipu").lower()  # doubao / zhipu / anthropic / openai / openrouter

# 豆包配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_API_BASE = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_ENDPOINT_ID = os.getenv("DOUBAO_ENDPOINT_ID", "")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-1-5-pro-32k-250115")

# 智谱配置（推荐用于中文财经写作）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_API_BASE = os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL", "glm-5")

# Anthropic Claude 配置 (Sonnet 4.6)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")  # Sonnet 4.6

# OpenAI 配置 (备用)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# OpenRouter 配置（高质量内容路由）
DEFAULT_OPENROUTER_STREAM_MODELS = [
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5.1",
]
DEFAULT_OPENROUTER_ARTICLE_MODELS = [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.1",
    "google/gemini-3.1-pro-preview",
]
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "finance-streamer-mvp")
OPENROUTER_ENABLE_QUALITY_ROUTING = _parse_bool(os.getenv("OPENROUTER_ENABLE_QUALITY_ROUTING"), False)
OPENROUTER_PLATFORM_PACK_ROUTING = _parse_bool(os.getenv("OPENROUTER_PLATFORM_PACK_ROUTING"), False)
OPENROUTER_STREAM_MODELS = _parse_csv(
    os.getenv("OPENROUTER_STREAM_MODELS"),
    DEFAULT_OPENROUTER_STREAM_MODELS,
)
OPENROUTER_ARTICLE_MODELS = _parse_csv(
    os.getenv("OPENROUTER_ARTICLE_MODELS"),
    DEFAULT_OPENROUTER_ARTICLE_MODELS,
)
QUALITY_ROUTING_AUTO_FALLBACK = _parse_bool(os.getenv("QUALITY_ROUTING_AUTO_FALLBACK"), True)
QUALITY_ROUTING_HOURLY_BUDGET_USD = _parse_float(os.getenv("QUALITY_ROUTING_HOURLY_BUDGET_USD"), 0.0)
QUALITY_ROUTING_DAILY_BUDGET_USD = _parse_float(os.getenv("QUALITY_ROUTING_DAILY_BUDGET_USD"), 0.0)

# 根据提供商选择配置
if AI_PROVIDER == "anthropic":
    AI_API_KEY = ANTHROPIC_API_KEY
    AI_API_BASE = "https://api.anthropic.com"
    AI_MODEL = ANTHROPIC_MODEL
elif AI_PROVIDER == "zhipu":
    AI_API_KEY = ZHIPU_API_KEY
    AI_API_BASE = ZHIPU_API_BASE
    AI_MODEL = ZHIPU_MODEL
elif AI_PROVIDER == "openai":
    AI_API_KEY = OPENAI_API_KEY
    AI_API_BASE = OPENAI_API_BASE
    AI_MODEL = OPENAI_MODEL
elif AI_PROVIDER == "openrouter":
    AI_API_KEY = OPENROUTER_API_KEY
    AI_API_BASE = OPENROUTER_API_BASE
    AI_MODEL = OPENROUTER_STREAM_MODELS[0]
else:  # 默认豆包
    AI_API_KEY = DOUBAO_API_KEY
    AI_API_BASE = DOUBAO_API_BASE
    # 方舟控制台里的 Endpoint ID 优先，其次才是基础模型名
    AI_MODEL = DOUBAO_ENDPOINT_ID or DOUBAO_MODEL

# 服务配置
PORT = int(os.getenv("PORT", 8000))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# API 认证密钥（设置后所有生成接口需携带 X-API-Key 请求头）
API_KEY = os.getenv("API_KEY", "")

# 新闻缓存时间（分钟）
NEWS_CACHE_MINUTES = int(os.getenv("NEWS_CACHE_MINUTES", "30"))
USE_MOCK_NEWS = _parse_bool(os.getenv("USE_MOCK_NEWS"), False)
