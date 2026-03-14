"""
配置文件
所有敏感信息通过环境变量设置
"""
import os
from dotenv import load_dotenv

load_dotenv()

# AI 提供商配置
AI_PROVIDER = os.getenv("AI_PROVIDER", "doubao")  # doubao / anthropic / openai

# 豆包配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_API_BASE = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seedream-4-5-251128")

# Anthropic Claude 配置 (Sonnet 4.6)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")  # Sonnet 4.6

# OpenAI 配置 (备用)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 根据提供商选择配置
if AI_PROVIDER == "anthropic":
    AI_API_KEY = ANTHROPIC_API_KEY
    AI_API_BASE = "https://api.anthropic.com"
    AI_MODEL = ANTHROPIC_MODEL
elif AI_PROVIDER == "openai":
    AI_API_KEY = OPENAI_API_KEY
    AI_API_BASE = OPENAI_API_BASE
    AI_MODEL = OPENAI_MODEL
else:  # 默认豆包
    AI_API_KEY = DOUBAO_API_KEY
    AI_API_BASE = DOUBAO_API_BASE
    AI_MODEL = DOUBAO_MODEL

# 服务配置
PORT = int(os.getenv("PORT", 8000))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# API 认证密钥（设置后所有生成接口需携带 X-API-Key 请求头）
API_KEY = os.getenv("API_KEY", "")

# 新闻缓存时间（分钟）
NEWS_CACHE_MINUTES = int(os.getenv("NEWS_CACHE_MINUTES", "30"))
