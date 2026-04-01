"""
如意 Agent 后端服务

FastAPI + 技能系统 + Ollama
"""

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入核心模块
from src.config import settings
from src.logger import logger
from src.llm import OllamaProvider
from src.agent import AgentRunner
from src.agent.base import GeneralAgent, AgentMode
from src.skills import SkillManager
from src.memory import SessionMemory


# ==========================================================
# 全局状态
# ==========================================================

class AppState:
    """应用状态"""
    llm: Optional[OllamaProvider] = None
    skill_manager: Optional[SkillManager] = None
    agent_runner: Optional[AgentRunner] = None
    memory_store: dict = {}  # session_id -> SessionMemory


app_state = AppState()


def init_backend():
    """初始化后端组件"""
    try:
        logger.info("Initializing backend components...")
        
        # 初始化 LLM
        app_state.llm = OllamaProvider(
            base_url=settings.ollama.base_url,
            model=settings.ollama.model,
            timeout=settings.ollama.timeout,
            temperature=settings.ollama.temperature,
        )
        logger.info(f"Ollama connected: {settings.ollama.model}")
        
        # 初始化技能管理器
        skills_dir = project_root / "skills"
        app_state.skill_manager = SkillManager(
            skills_dir=str(skills_dir),
            max_execution_time=30,
        )
        logger.info(f"Loaded {len(app_state.skill_manager.list_skills())} skills")
        
        # 初始化 Agent 运行器
        app_state.agent_runner = AgentRunner(
            llm=app_state.llm,
            skill_manager=app_state.skill_manager,
            max_iterations=settings.agent.max_iterations,
        )
        
        # 注册默认 Agent
        general_agent = GeneralAgent(
            llm=app_state.llm,
            skill_manager=app_state.skill_manager,
        )
        app_state.agent_runner.register_agent("general", general_agent)
        
        logger.info("Backend initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize backend: {e}")
        raise


# ==========================================================
# FastAPI 应用
# ==========================================================

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="如意 Agent API",
        description="如意智能 Agent 系统后端 API",
        version="1.0.0",
    )
    
    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 初始化后端
    init_backend()
    
    # 注册路由
    _register_routes(app)
    
    return app


def _register_routes(app: FastAPI):
    """注册路由"""
    
    # ----------------------------------------
    # 请求模型
    # ----------------------------------------
    
    class ChatRequest(BaseModel):
        message: str
        agent_mode: str = "general"
        session_id: str = "default"
        stream: bool = True
    
    class SkillExecuteRequest(BaseModel):
        skill_name: str
        params: dict = {}
    
    # ----------------------------------------
    # 对话接口
    # ----------------------------------------
    
    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """对话接口（非流式）"""
        try:
            # 获取或创建会话记忆
            if request.session_id not in app_state.memory_store:
                app_state.memory_store[request.session_id] = SessionMemory(request.session_id)
            memory = app_state.memory_store[request.session_id]
            
            # 添加用户消息
            memory.add_user_message(request.message)
            
            # 执行 Agent
            result = await app_state.agent_runner.run(
                message=request.message,
                mode=request.agent_mode,
                session_id=request.session_id,
            )
            
            # 添加助手回复
            memory.add_assistant_message(result.message)
            
            return {
                "success": result.success,
                "message": result.message,
                "mode": result.mode,
                "session_id": request.session_id,
            }
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/chat/stream")
    async def chat_stream(request: ChatRequest):
        """流式对话接口"""
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate():
            try:
                # 获取或创建会话记忆
                if request.session_id not in app_state.memory_store:
                    app_state.memory_store[request.session_id] = SessionMemory(request.session_id)
                memory = app_state.memory_store[request.session_id]
                
                # 添加用户消息
                memory.add_user_message(request.message)
                
                # 流式执行
                full_response = ""
                async for chunk in app_state.agent_runner.run_stream(
                    message=request.message,
                    mode=request.agent_mode,
                    session_id=request.session_id,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                
                # 添加助手回复
                memory.add_assistant_message(full_response)
                
                # 发送完成信号
                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    
    # ----------------------------------------
    # 技能接口
    # ----------------------------------------
    
    @app.get("/api/skills")
    async def list_skills():
        """列出所有技能"""
        return {
            "skills": app_state.skill_manager.list_skills(),
            "count": len(app_state.skill_manager.list_skills()),
        }
    
    @app.post("/api/skills/execute")
    async def execute_skill(request: SkillExecuteRequest):
        """执行技能"""
        try:
            result = await app_state.skill_manager.execute(
                skill_name=request.skill_name,
                **request.params,
            )
            return result.to_dict()
        except Exception as e:
            logger.error(f"Skill execution error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ----------------------------------------
    # 会话接口
    # ----------------------------------------
    
    @app.get("/api/session/{session_id}/history")
    async def get_session_history(session_id: str):
        """获取会话历史"""
        if session_id in app_state.memory_store:
            memory = app_state.memory_store[session_id]
            return {
                "session_id": session_id,
                "history": memory.get_history(),
            }
        return {"session_id": session_id, "history": []}
    
    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        """清空会话"""
        if session_id in app_state.memory_store:
            app_state.memory_store[session_id].clear()
        return {"success": True, "message": f"Session {session_id} cleared"}
    
    # ----------------------------------------
    # 系统接口
    # ----------------------------------------
    
    @app.get("/api/system/info")
    async def get_system_info():
        """获取系统信息"""
        skills = app_state.skill_manager.list_skills()
        return {
            "app_name": settings.app.name,
            "version": settings.app.version,
            "ollama": {
                "base_url": settings.ollama.base_url,
                "model": settings.ollama.model,
            },
            "skills_count": len(skills),
            "sessions_count": len(app_state.memory_store),
        }
    
    @app.get("/api/system/health")
    async def health_check():
        """健康检查"""
        ollama_ok = False
        try:
            ollama_ok = await app_state.llm.health_check()
        except:
            pass
        
        return {
            "status": "healthy" if ollama_ok else "degraded",
            "ollama": "connected" if ollama_ok else "disconnected",
            "skills": len(app_state.skill_manager.list_skills()),
        }
    
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "name": "如意 Agent",
            "version": "1.0.0",
            "description": "如意智能 Agent 系统",
        }


# ==========================================================
# 直接运行
# ==========================================================

if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_level="info",
    )
