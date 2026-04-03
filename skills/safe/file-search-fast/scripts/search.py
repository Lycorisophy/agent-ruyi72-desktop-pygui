#!/usr/bin/env python3
"""快速文件搜索"""
import argparse
import json
import os
import subprocess
import sys


def search_with_everything(keyword, file_type="", limit=20):
    """使用Everything搜索"""
    # 检查es.exe是否存在
    es_path = r"C:\Program Files\Everything\es.exe"
    if not os.path.exists(es_path):
        es_path = "es"  # 尝试PATH中的es
    
    query = keyword
    if file_type:
        query = f"{keyword} ext:{file_type}"
    
    try:
        result = subprocess.run(
            [es_path, "-n", str(limit), query],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    files.append({"path": line.strip()})
            return files, "everything"
    except:
        pass
    return None, "everything"


def search_with_windows(keyword, file_type="", limit=20):
    """使用Windows搜索"""
    import winshell
    
    try:
        results = []
        # 使用Windows Search
        from win32com.client import Dispatch
        obj = Dispatch("Shell.Application")
        
        folder = winshell.folder(winshell.public('windows'))
        
        for item in folder.Search(winshell.SHELL_FOLDER_SCOPES):
            if keyword.lower() in item.name.lower():
                results.append({"path": item.path, "name": item.name})
                if len(results) >= limit:
                    break
        
        return results, "windows"
    except:
        pass
    
    # 备选：使用PowerShell
    ps_script = f'''
$results = Get-ChildItem -Path $env:UserProfile -Recurse -ErrorAction SilentlyContinue -Filter "*{keyword}*" | Select-Object -First {limit}
$results | ForEach-Object {{ $_.FullName }}
'''
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    files.append({"path": line.strip()})
            return files, "windows"
    except:
        pass
    
    return None, "windows"


def main():
    parser = argparse.ArgumentParser(description="快速文件搜索")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--type", help="文件类型，如 pdf, txt, jpg")
    parser.add_argument("--path", help="搜索路径")
    parser.add_argument("--limit", type=int, default=20, help="结果数量限制")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    # 尝试Everything
    files, method = search_with_everything(args.keyword, args.type, args.limit)
    
    if files is None:
        # 回退到Windows搜索
        files, method = search_with_windows(args.keyword, args.type, args.limit)
    
    if args.json:
        print(json.dumps({"keyword": args.keyword, "method": method, "files": files}, indent=2, ensure_ascii=False))
    else:
        if files:
            print(f"===== 搜索结果 ({method}) =====")
            print(f"关键词: {args.keyword}")
            if args.type:
                print(f"类型: {args.type}")
            print(f"找到 {len(files)} 个结果:\n")
            for i, f in enumerate(files[:10]):
                print(f"{i+1}. {f.get('path', f.get('name', ''))}")
        else:
            print("未找到文件")

    return 0


if __name__ == "__main__":
    sys.exit(main())
