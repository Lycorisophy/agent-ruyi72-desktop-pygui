"""
Ollama LLM 提供商

封装与 Ollama API 的交互
支持流式响应
"""

import json
from typing import Any, AsyncGenerator, Optional

import httpx

from src.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider:
    """
    Ollama LLM 提供商
    
    提供与本地 Ollama 服务器的交互接口
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3.5:35b-a3b-q8_0-nothink",
        timeout: int = 120,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.options = kwargs
        
        # HTTP 客户端
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        
        logger.info(f"Initialized OllamaProvider: {base_url}, model={model}")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def _post(self, endpoint: str, data: dict) -> dict:
        """POST 请求"""
        url = f"{self.base_url}{endpoint}"
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[list] = None,
        stream: bool = False,
        **options,
    ) -> dict:
        """
        生成文本
        
        Args:
            prompt: 用户提示
            system: 系统提示
            context: 上下文
            stream: 是否流式返回
            **options: 额外的模型参数
        
        Returns:
            dict: 生成结果
        """
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": options.get("temperature", self.temperature),
                "num_predict": options.get("max_tokens", self.max_tokens),
                **self.options,
                **options,
            },
        }
        
        if system:
            data["system"] = system
        if context:
            data["context"] = context
        
        logger.debug(f"Generating with prompt: {prompt[:100]}...")
        
        response = await self._post("/api/generate", data)
        
        return {
            "content": response.get("response", ""),
            "model": response.get("model", self.model),
            "done": response.get("done", True),
        }
    
    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[list] = None,
        **options,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 用户提示
            system: 系统提示
            context: 上下文
            **options: 额外的模型参数
        
        Yields:
            str: 生成的文本片段
        """
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": options.get("temperature", self.temperature),
                "num_predict": options.get("max_tokens", self.max_tokens),
                **self.options,
                **options,
            },
        }
        
        if system:
            data["system"] = system
        
        url = f"{self.base_url}/api/generate"
        
        async with self.client.stream("POST", url, json=data) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            yield chunk["response"]
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
    
    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        **options,
    ) -> dict:
        """
        聊天接口（使用 /api/chat）
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式返回
            **options: 额外的模型参数
        
        Returns:
            dict: 生成结果
        """
        data = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": options.get("temperature", self.temperature),
                "num_predict": options.get("max_tokens", self.max_tokens),
                **self.options,
                **options,
            },
        }
        
        logger.debug(f"Chat with {len(messages)} messages")
        
        response = await self._post("/api/chat", data)
        
        return {
            "content": response.get("message", {}).get("content", ""),
            "model": response.get("model", self.model),
            "done": response.get("done", True),
        }
    
    async def chat_stream(
        self,
        messages: list[dict],
        **options,
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天
        
        Args:
            messages: 消息列表
            **options: 额外的模型参数
        
        Yields:
            str: 生成的文本片段
        """
        data = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": options.get("temperature", self.temperature),
                "num_predict": options.get("max_tokens", self.max_tokens),
                **self.options,
                **options,
            },
        }
        
        url = f"{self.base_url}/api/chat"
        
        async with self.client.stream("POST", url, json=data) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


__all__ = ["OllamaProvider"]
