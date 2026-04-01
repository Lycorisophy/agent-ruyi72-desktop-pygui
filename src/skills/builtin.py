"""
内置技能

使用 Python 直接实现的技能
"""

from pathlib import Path
from typing import Any

from src.skills.base import Skill, SkillResult, SkillParameter


class ReadSkill(Skill):
    """读取文件技能"""
    
    name = "Read"
    description = "读取指定路径的文件内容"
    category = "filesystem"
    parameters = [
        SkillParameter(name="path", description="文件路径", type="string", required=True),
        SkillParameter(name="limit", description="限制读取行数，0表示不限制", type="integer", required=False, default=0),
        SkillParameter(name="offset", description="从第几行开始（0-based）", type="integer", required=False, default=0),
    ]
    triggers = ["读取文件", "查看文件", "cat", "type"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            path = kwargs.get("path")
            limit = kwargs.get("limit", 0)
            offset = kwargs.get("offset", 0)
            
            file_path = Path(path)
            
            if not file_path.exists():
                return SkillResult(success=False, error=f"文件不存在: {path}")
            
            if not file_path.is_file():
                return SkillResult(success=False, error=f"不是文件: {path}")
            
            # 检查文件大小
            if file_path.stat().st_size > 5 * 1024 * 1024:
                return SkillResult(success=False, error="文件过大（超过5MB）")
            
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            if offset > 0:
                lines = lines[offset:]
            if limit > 0:
                lines = lines[:limit]
            
            return SkillResult(
                success=True,
                output="\n".join(lines),
                metadata={"lines": len(lines), "path": str(file_path)},
            )
            
        except UnicodeDecodeError:
            return SkillResult(success=False, error="文件编码不支持（仅支持UTF-8）")
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class WriteSkill(Skill):
    """写入文件技能"""
    
    name = "Write"
    description = "写入内容到文件"
    category = "filesystem"
    parameters = [
        SkillParameter(name="path", description="文件路径", type="string", required=True),
        SkillParameter(name="content", description="写入内容", type="string", required=True),
        SkillParameter(name="append", description="是否追加模式", type="boolean", required=False, default=False),
    ]
    triggers = ["写入文件", "创建文件", "写文件"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            path = kwargs.get("path")
            content = kwargs.get("content", "")
            append = kwargs.get("append", False)
            
            file_path = Path(path)
            
            # 创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)
            
            return SkillResult(
                success=True,
                output=f"文件已{'追加' if append else '写入'}: {path}",
                metadata={"path": str(file_path), "bytes": len(content)},
            )
            
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class GlobSkill(Skill):
    """文件搜索技能"""
    
    name = "Glob"
    description = "搜索匹配模式的文件"
    category = "filesystem"
    parameters = [
        SkillParameter(name="pattern", description="搜索模式，如 *.py", type="string", required=True),
        SkillParameter(name="path", description="搜索目录", type="string", required=False, default="."),
    ]
    triggers = ["搜索文件", "查找文件", "glob"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            pattern = kwargs.get("pattern")
            path = kwargs.get("path", ".")
            
            search_path = Path(path)
            if not search_path.exists():
                return SkillResult(success=False, error=f"目录不存在: {path}")
            
            files = list(search_path.glob(pattern))
            
            return SkillResult(
                success=True,
                output="\n".join([str(f) for f in files]),
                metadata={"count": len(files)},
            )
            
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class GrepSkill(Skill):
    """文本搜索技能"""
    
    name = "Grep"
    description = "在文件中搜索匹配的文本"
    category = "filesystem"
    parameters = [
        SkillParameter(name="pattern", description="搜索模式（正则表达式）", type="string", required=True),
        SkillParameter(name="path", description="搜索目录或文件", type="string", required=False, default="."),
        SkillParameter(name="recursive", description="是否递归搜索", type="boolean", required=False, default=True),
    ]
    triggers = ["搜索文本", "grep", "查找内容"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            import re
            
            pattern = kwargs.get("pattern")
            path = kwargs.get("path", ".")
            recursive = kwargs.get("recursive", True)
            
            search_path = Path(path)
            results = []
            
            try:
                regex = re.compile(pattern)
            except re.error:
                return SkillResult(success=False, error=f"无效的正则表达式: {pattern}")
            
            def search_in_file(file_path: Path):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{i}:{line.rstrip()}")
                except:
                    pass
            
            if search_path.is_file():
                search_in_file(search_path)
            elif search_path.is_dir():
                pattern_str = "**/*" if recursive else "*"
                for file_path in search_path.glob(pattern_str):
                    if file_path.is_file():
                        search_in_file(file_path)
            
            return SkillResult(
                success=True,
                output="\n".join(results) if results else "未找到匹配",
                metadata={"matches": len(results)},
            )
            
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class BashSkill(Skill):
    """执行 Bash 命令技能"""
    
    name = "Bash"
    description = "执行 Shell/Bash 命令"
    category = "execution"
    parameters = [
        SkillParameter(name="command", description="要执行的命令", type="string", required=True),
        SkillParameter(name="cwd", description="工作目录", type="string", required=False, default="."),
        SkillParameter(name="timeout", description="超时时间（秒）", type="integer", required=False, default=30),
    ]
    triggers = ["执行命令", "运行命令", "bash"]
    
    async def execute(self, **kwargs) -> SkillResult:
        import asyncio
        import time
        
        command = kwargs.get("command")
        cwd = kwargs.get("cwd", ".")
        timeout = kwargs.get("timeout", 30)
        
        start_time = time.time()
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            execution_time = time.time() - start_time
            
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else None
            
            return SkillResult(
                success=proc.returncode == 0,
                output=output,
                error=error if proc.returncode != 0 else None,
                metadata={
                    "returncode": proc.returncode,
                    "execution_time": execution_time,
                },
            )
            
        except asyncio.TimeoutError:
            return SkillResult(
                success=False,
                error=f"命令超时 ({timeout}秒)",
                metadata={"execution_time": time.time() - start_time},
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class PythonSkill(Skill):
    """执行 Python 代码技能"""
    
    name = "Python"
    description = "执行 Python 代码"
    category = "execution"
    parameters = [
        SkillParameter(name="code", description="Python 代码", type="string", required=True),
        SkillParameter(name="timeout", description="超时时间（秒）", type="integer", required=False, default=60),
    ]
    triggers = ["执行代码", "运行代码", "python"]
    
    async def execute(self, **kwargs) -> SkillResult:
        import asyncio
        import tempfile
        import time
        
        code = kwargs.get("code")
        timeout = kwargs.get("timeout", 60)
        
        start_time = time.time()
        
        try:
            # 写入临时文件
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python",
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                
                execution_time = time.time() - start_time
                
                return SkillResult(
                    success=proc.returncode == 0,
                    output=stdout.decode() if stdout else "",
                    error=stderr.decode() if stderr else None,
                    metadata={
                        "returncode": proc.returncode,
                        "execution_time": execution_time,
                    },
                )
                
            finally:
                Path(temp_file).unlink()
                
        except asyncio.TimeoutError:
            return SkillResult(
                success=False,
                error=f"代码执行超时 ({timeout}秒)",
                metadata={"execution_time": time.time() - start_time},
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class WebSearchSkill(Skill):
    """网页搜索技能"""
    
    name = "WebSearch"
    description = "搜索网页信息"
    category = "web"
    parameters = [
        SkillParameter(name="query", description="搜索关键词", type="string", required=True),
        SkillParameter(name="limit", description="返回结果数量", type="integer", required=False, default=5),
    ]
    triggers = ["搜索", "网上搜索", "search"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            import httpx
            
            query = kwargs.get("query")
            limit = kwargs.get("limit", 5)
            
            # 简单的 DuckDuckGo 搜索
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json"},
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    # 提取相关主题
                    for topic in data.get("RelatedTopics", [])[:limit]:
                        if "Text" in topic:
                            results.append(topic["Text"])
                    
                    return SkillResult(
                        success=True,
                        output="\n".join(results) if results else "未找到结果",
                        metadata={"query": query, "count": len(results)},
                    )
                else:
                    return SkillResult(
                        success=False,
                        error=f"搜索请求失败: {response.status_code}",
                    )
                    
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class WebFetchSkill(Skill):
    """获取网页内容技能"""
    
    name = "WebFetch"
    description = "获取网页内容"
    category = "web"
    parameters = [
        SkillParameter(name="url", description="网页 URL", type="string", required=True),
        SkillParameter(name="limit", description="内容长度限制", type="integer", required=False, default=5000),
    ]
    triggers = ["获取网页", "抓取网页", "fetch"]
    
    async def execute(self, **kwargs) -> SkillResult:
        try:
            import httpx
            
            url = kwargs.get("url")
            limit = kwargs.get("limit", 5000)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                
                if response.status_code == 200:
                    content = response.text[:limit]
                    return SkillResult(
                        success=True,
                        output=content,
                        metadata={"url": url, "size": len(content)},
                    )
                else:
                    return SkillResult(
                        success=False,
                        error=f"获取失败: HTTP {response.status_code}",
                    )
                    
        except Exception as e:
            return SkillResult(success=False, error=str(e))


# 内置技能列表
BUILTIN_SKILLS = [
    ReadSkill(),
    WriteSkill(),
    GlobSkill(),
    GrepSkill(),
    BashSkill(),
    PythonSkill(),
    WebSearchSkill(),
    WebFetchSkill(),
]
