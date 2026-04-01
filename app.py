"""
如意 Agent - PyWebView 桌面应用

基于 PyWebView 的跨平台桌面应用
整合技能系统和流式对话
"""

import os
import sys
import json
import asyncio
import threading
from pathlib import Path
import webview


class Ruyi72App:
    """如意 Agent 应用主类"""
    
    def __init__(self):
        self.window = None
        self.backend_thread = None
        self.backend_ready = threading.Event()
        
        # 获取资源路径
        if getattr(sys, 'frozen', False):
            self.base_path = Path(sys._MEIPASS)
        else:
            self.base_path = Path(__file__).parent
        
        self.frontend_path = self.base_path / "frontend"
        self.api_base = "http://127.0.0.1:8765/api"
    
    def start_backend(self):
        """启动后端服务（独立线程）"""
        def run_backend():
            sys.path.insert(0, str(self.base_path))
            from backend.server import create_app
            
            app = create_app()
            
            import uvicorn
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=8765,
                log_level="info",
            )
            server = uvicorn.Server(config)
            
            self.backend_ready.set()
            server.run()
        
        self.backend_thread = threading.Thread(target=run_backend, daemon=True)
        self.backend_thread.start()
        self.backend_ready.wait(timeout=10)
        print("[Ruyi72] Backend started: http://127.0.0.1:8765")
    
    def create_window(self):
        """创建窗口"""
        html_path = self.frontend_path / "index.html"
        
        if not html_path.exists():
            self._create_default_html()
        
        self.window = webview.create_window(
            title="如意 Agent - ruyi72",
            html=str(html_path),
            width=1280,
            height=800,
            min_size=(900, 600),
            resizable=True,
            js_api=self,
        )
    
    def _create_default_html(self):
        """创建默认 HTML"""
        html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>如意 Agent</title>
    <style>
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }
    </style>
</head>
<body>
    <h1>如意 Agent 加载中...</h1>
</body>
</html>
"""
        self.frontend_path.mkdir(parents=True, exist_ok=True)
        (self.frontend_path / "index.html").write_text(html, encoding='utf-8')
    
    def run(self):
        """运行应用"""
        print("[Ruyi72] Starting backend...")
        self.start_backend()
        
        print("[Ruyi72] Creating window...")
        self.create_window()
        
        print("[Ruyi72] Starting GUI...")
        webview.start(debug=True)
        
        print("[Ruyi72] App closed")
    
    # ==========================================================
    # JavaScript API
    # ==========================================================
    
    def chat(self, message: str, agent_mode: str = "general", session_id: str = "default") -> dict:
        """发送消息并获取回复（非流式）"""
        try:
            import requests
            response = requests.post(
                f"{self.api_base}/chat",
                json={
                    "message": message,
                    "agent_mode": agent_mode,
                    "session_id": session_id,
                    "stream": False,
                },
                timeout=120,
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def chat_stream(self, message: str, agent_mode: str = "general", session_id: str = "default") -> str:
        """
        流式对话 - 返回 SSE URL
        前端应使用 fetch 访问此 URL
        """
        return f"{self.api_base}/chat/stream"
    
    def get_skills(self) -> dict:
        """获取技能列表"""
        try:
            import requests
            response = requests.get(f"{self.api_base}/skills", timeout=10)
            return response.json()
        except Exception as e:
            return {"skills": [], "error": str(e)}
    
    def execute_skill(self, skill_name: str, params: dict = None) -> dict:
        """执行技能"""
        try:
            import requests
            response = requests.post(
                f"{self.api_base}/skills/execute",
                json={
                    "skill_name": skill_name,
                    "params": params or {},
                },
                timeout=60,
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_history(self, session_id: str) -> dict:
        """获取会话历史"""
        try:
            import requests
            response = requests.get(
                f"{self.api_base}/session/{session_id}/history",
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"history": [], "error": str(e)}
    
    def clear_session(self, session_id: str) -> dict:
        """清空会话"""
        try:
            import requests
            response = requests.delete(
                f"{self.api_base}/session/{session_id}",
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_system_info(self) -> dict:
        """获取系统信息"""
        try:
            import requests
            response = requests.get(f"{self.api_base}/system/info", timeout=10)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def health_check(self) -> dict:
        """健康检查"""
        try:
            import requests
            response = requests.get(f"{self.api_base}/system/health", timeout=10)
            return response.json()
        except Exception as e:
            return {"status": "offline", "error": str(e)}
    
    def minimize(self):
        """最小化窗口"""
        if self.window:
            self.window.minimize()
    
    def maximize(self):
        """最大化窗口"""
        if self.window:
            self.window.toggle_maximize()
    
    def close(self):
        """关闭窗口"""
        if self.window:
            self.window.destroy()


def main():
    """入口函数"""
    app = Ruyi72App()
    app.run()


if __name__ == "__main__":
    main()
