"""
上策（ShangCe）· 后端一键启动入口
================================

在 PyCharm 中直接 Run 本文件即可启动后端服务（http://127.0.0.1:8000），
等同于：cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000

配合前端开发模式使用（另开终端）：
    cd frontend && npm install && npm run dev
然后访问 http://localhost:5173（已配置 /api 代理到本服务）。

注意：数据（SQLite + LangGraph 检查点）固定存放在 backend/data/，
与启动时的工作目录无关。
"""
import sys
from pathlib import Path

# 把 backend 目录加入模块搜索路径，保证任意工作目录/任意启动方式下都能导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # 绑定所有网卡，局域网内其他设备可通过 http://<本机IP>:8000 访问
        port=8000,
        reload=False,  # PyCharm 自行管理重启，无需热重载
    )
