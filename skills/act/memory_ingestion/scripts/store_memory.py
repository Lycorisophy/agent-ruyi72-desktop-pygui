"""
向量存储脚本
将记忆文本向量化后存入ChromaDB

依赖:
    pip install chromadb requests

用法:
    python store_memory.py "记忆内容" --type fact --tags 个人信息
    python store_memory.py --file memory.txt
"""

import json
import sys
import os
import requests
from datetime import datetime
from pathlib import Path

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[警告] ChromaDB未安装，请先安装: pip install chromadb")

# 配置路径
WORKSPACE = Path.home() / ".ruyi72" / "workspace"
VECTOR_DB_DIR = WORKSPACE / "memory" / "vector_db" / "chroma"

# Ollama配置
OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "qwen3-embedding:8b"  # 本地Ollama部署的embedding模型

def get_embedding(text: str) -> list:
    """使用Ollama获取文本Embedding"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": text},
            timeout=30
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
        client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
        collection = client.get_or_create_collection("memories")
        return collection
    except Exception as e:
        print(f"[错误] 初始化向量数据库失败: {e}")
        return None

def store_memory(content: str, memory_type: str = "general", tags: list = None):
    """存储单条记忆到向量数据库"""
    collection = init_vector_db()
    if collection is None:
        print("[错误] 无法初始化向量数据库")
        return False
    
    print(f"[存储] 获取Embedding...")
    embedding = get_embedding(content)
    
    if embedding is None:
        print("[错误] 无法获取Embedding，跳过向量存储")
        return False
    
    # 生成唯一ID
    memory_id = f"{memory_type}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    # 存储到ChromaDB
    try:
        collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[{
                "type": memory_type,
                "tags": ",".join(tags) if tags else "",
                "created_at": datetime.now().isoformat()
            }],
            ids=[memory_id]
        )
        print(f"[存储成功] ID: {memory_id}")
        return True
    except Exception as e:
        print(f"[错误] 存储失败: {e}")
        return False

def store_from_file(file_path: str, memory_type: str = "general"):
    """从文件批量存储记忆"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 按行分割，每行一条记忆
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("#")]
        
        success_count = 0
        for line in lines:
            if store_memory(line, memory_type):
                success_count += 1
        
        print(f"\n[完成] 成功存储 {success_count}/{len(lines)} 条记忆")
        return success_count
    except Exception as e:
        print(f"[错误] 读取文件失败: {e}")
        return 0

def main():
    if not CHROMADB_AVAILABLE:
        print("请先安装ChromaDB: pip install chromadb")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python store_memory.py <记忆内容>")
        print("  python store_memory.py --file <文件路径>")
        print("  python store_memory.py <记忆内容> --type fact --tags 个人信息,重要")
        sys.exit(1)
    
    memory_type = "general"
    tags = []
    
    # 解析参数
    for i, arg in enumerate(sys.argv):
        if arg == "--file" and i + 1 < len(sys.argv):
            store_from_file(sys.argv[i + 1], memory_type)
            return
        elif arg == "--type" and i + 1 < len(sys.argv):
            memory_type = sys.argv[i + 1]
        elif arg == "--tags" and i + 1 < len(sys.argv):
            tags = sys.argv[i + 1].split(",")
    
    # 单条记忆存储
    content = " ".join([a for a in sys.argv[1:] if not a.startswith("--")])
    if content:
        store_memory(content, memory_type, tags)

if __name__ == "__main__":
    main()
