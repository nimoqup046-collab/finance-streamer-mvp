"""
财经主播助手 MVP 版本
启动入口 - 放在项目根目录，方便部署
"""
import sys
import os
from pathlib import Path

# 确保能找到backend模块
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn

    def _resolve_port() -> int:
        # Railway 某些服务会把 "$PORT" 作为字面参数传入，这里做兼容兜底。
        raw = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PORT", "8000")
        value = str(raw).strip()
        if value.startswith("$"):
            value = os.getenv(value[1:], os.getenv("PORT", "8000")).strip()
        try:
            port = int(value)
            return port if 1 <= port <= 65535 else 8000
        except (TypeError, ValueError):
            return 8000

    uvicorn.run("backend.main:app", host="0.0.0.0", port=_resolve_port())
