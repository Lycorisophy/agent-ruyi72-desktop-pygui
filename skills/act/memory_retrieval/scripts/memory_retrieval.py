"""
记忆检索脚本 - ChromaDB向量版本
通过RAG检索相关记忆

用法:
    python memory_retrieval.py "用户问题"
    python memory_retrieval.py --query "用户问题" --days 30
"""

import json
import sys
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

# 尝试导入ChromaDB，如果失败则使用关键词匹配
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[警告] ChromaDB未安装，使用关键词匹配模式")

# 配置路径
WORKSPACE = Path.home() / ".openclaw" / "workspace"
SHORT_TERM_DIR = WORKSPACE / "memory" / "SHORT_TERM"
LONG_TERM_DIR = WORKSPACE / "memory" / "LONG_TERM"
EPISODIC_DIR = LONG_TERM_DIR / "episodic"
VECTOR_DB_DIR = WORKSPACE / "memory" / "vector_db" / "chroma"

# Ollama配置（用于生成query的embedding）
OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_EMBEDDING_MODEL = "qwen3-embedding:8b"

def get_query_embedding(text: str) -> list:
    """使用本地Ollama获取query的embedding"""
    import requests
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_EMBEDDING_MODEL, "prompt": text},
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get("embedding", [])
        else:
            print(f"[错误] Ollama返回错误: {response.status_code}")
            return None
    except Exception as e:
        print(f"[错误] 获取Embedding失败: {e}")
        return None

def init_vector_db():
    """初始化ChromaDB"""
    if not CHROMADB_AVAILABLE:
        return None
    
    try:
        VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
            collection = client.get_or_create_collection("memories")
            print("[ChromaDB] 向量数据库已就绪")
            return collection
        except Exception as e:
            print(f"[提示] ChromaDB初始化: {str(e)[:80]}")
            return None
    except Exception as e:
        print(f"[提示] ChromaDB不可用: {str(e)[:80]}")
        return None

def search_vectors(collection, query: str, n_results: int = 5) -> list:
    """向量检索（使用本地Ollama embedding）"""
    if collection is None:
        return []
    
    try:
        print(f"[向量检索] 生成query embedding...")
        query_embedding = get_query_embedding(query)
        
        if query_embedding is None:
            print("[提示] 无法获取embedding，回退到关键词搜索")
            return []
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        memories = []
        if results and results.get('documents'):
            for i, doc in enumerate(results['documents'][0]):
                memories.append({
                    'content': doc,
                    'distance': results['distances'][0][i] if 'distances' in results else 0,
                    'id': results['ids'][0][i] if 'ids' in results else f'vec_{i}'
                })
        
        return memories
    except Exception as e:
        print(f"[错误] 向量检索失败: {e}")
        return []

def search_keywords(query: str, days: int = 30) -> list:
    """关键词匹配搜索（ChromaDB不可用时使用）"""
    results = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 搜索短期记忆
    buffer_file = SHORT_TERM_DIR / "buffer.md"
    if buffer_file.exists():
        results.extend(search_in_file(buffer_file, query))
    
    # 搜索情景记忆
    if EPISODIC_DIR.exists():
        for md_file in EPISODIC_DIR.rglob("*.md"):
            results.extend(search_in_file(md_file, query))
    
    # 搜索事实库
    facts_dir = LONG_TERM_DIR / "facts"
    if facts_dir.exists():
        for md_file in facts_dir.rglob("*.md"):
            results.extend(search_in_file(md_file, query))
    
    # 按相关性排序
    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    
    return results[:10]

def search_in_file(file_path: Path, query: str) -> list:
    """在单个文件中搜索"""
    results = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
        
        query_words = query.lower().split()
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            matches = sum(1 for word in query_words if word in line_lower)
            if matches > 0:
                relevance = matches / len(query_words)
                
                context = ""
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    context += lines[j] + "\n"
                
                results.append({
                    "content": line.strip(),
                    "context": context,
                    "source": str(file_path),
                    "relevance": relevance,
                    "type": detect_type(line),
                    "distance": 1 - relevance  # 模拟距离
                })
    except Exception as e:
        print(f"搜索文件 {file_path} 时出错: {e}")
    
    return results

def detect_type(line: str) -> str:
    """检测记忆类型"""
    if "[fact]" in line.lower():
        return "fact"
    elif "[event]" in line.lower():
        return "event"
    elif "[emotion]" in line.lower():
        return "emotion"
    elif "[preference]" in line.lower():
        return "preference"
    return "general"

def format_results(results: list, query: str) -> str:
    """格式化搜索结果"""
    if not results:
        return "## 检索结果\n\n没有找到相关记忆。\n"
    
    output = "## 检索结果\n\n"
    output += f"找到 {len(results)} 条相关记忆：\n\n"
    
    for i, r in enumerate(results, 1):
        confidence = "高" if r.get("distance", 1) < 0.3 else "中" if r.get("distance", 1) < 0.6 else "低"
        output += f"### [{confidence}置信度] {r.get('type', 'general').upper()}\n"
        output += f"- 内容: {r.get('content', r.get('context', ''))}\n"
        output += f"- 来源: {r.get('source', '未知')}\n\n"
    
    output += "## AI回复建议\n"
    output += "根据以上记忆，自然地回答用户问题。如果没有找到相关信息，"
    output += "请坦诚告知用户你目前没有相关记忆。\n"
    
    return output

def main():
    query = ""
    days = 30
    
    for i, arg in enumerate(sys.argv):
        if arg == "--query" and i + 1 < len(sys.argv):
            query = sys.argv[i + 1]
        elif arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])
        elif not arg.startswith("--"):
            query = arg
    
    if not query:
        print("用法: python memory_retrieval.py <问题>")
        print("   或: python memory_retrieval.py --query <问题> --days <天数>")
        sys.exit(1)
    
    print(f"[记忆检索] 搜索: {query}")
    
    if CHROMADB_AVAILABLE:
        collection = init_vector_db()
        if collection:
            results = search_vectors(collection, query, n_results=10)
            if results:
                formatted = format_results(results, query)
                print("\n" + formatted)
                return
            else:
                print("[提示] 向量库为空，使用关键词搜索")
    
    # 回退到关键词搜索
    results = search_keywords(query, days)
    formatted = format_results(results, query)
    print("\n" + formatted)
    
    return formatted

if __name__ == "__main__":
    main()
