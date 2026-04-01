#!/usr/bin/env python3
"""
文件树技能脚本

显示目录的树形结构
"""
import json
import os
import sys
from pathlib import Path


def build_tree(path: Path, prefix: str = "", depth: int = 3, current_depth: int = 0, exclude: set = None):
    """递归构建目录树"""
    if exclude is None:
        exclude = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
    
    if current_depth >= depth:
        return []
    
    tree = []
    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    except PermissionError:
        return [f"{prefix}[权限拒绝]"]
    
    for i, item in enumerate(items):
        if item.name in exclude:
            continue
        
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        
        tree.append(f"{prefix}{connector}{item.name}")
        
        if item.is_dir():
            extension = "    " if is_last else "│   "
            tree.extend(build_tree(
                item,
                prefix + extension,
                depth,
                current_depth + 1,
                exclude
            ))
    
    return tree


def main():
    # 读取参数
    params = json.loads(sys.stdin.read())
    
    path = params.get("path", ".")
    depth = int(params.get("depth", 3))
    exclude_str = params.get("exclude", "")
    
    exclude = set(exclude_str.split(",")) if exclude_str else set()
    
    root = Path(path)
    
    if not root.exists():
        result = {
            "success": False,
            "output": None,
            "error": f"路径不存在: {path}"
        }
        print(json.dumps(result))
        return
    
    if not root.is_dir():
        result = {
            "success": False,
            "output": None,
            "error": f"不是目录: {path}"
        }
        print(json.dumps(result))
        return
    
    tree = [str(root.absolute())]
    tree.extend(build_tree(root, "", depth, 0, exclude))
    
    result = {
        "success": True,
        "output": "\n".join(tree),
        "metadata": {"path": str(root.absolute())}
    }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
