"""
财经主播助手 MVP 版本
启动入口 - 放在项目根目录，方便部署
"""
import sys
from pathlib import Path

# 确保能找到backend模块
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
