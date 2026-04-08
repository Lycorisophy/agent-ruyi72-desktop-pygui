#!/usr/bin/env python3
"""增强版剪贴板"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/clipboard-enhance")
HISTORY_FILE = os.path.join(STORAGE_DIR, "history.json")
FAVORITES_FILE = os.path.join(STORAGE_DIR, "favorites.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_json(file_path, default):
    ensure_dir()
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json(file_path, data):
    ensure_dir()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_content_type(text):
    """检测内容类型"""
    # URL
    if re.match(r'^https?://', text.strip()):
        return "url"
    # 邮箱
    if re.match(r'^[\w\.-]+@[\w\.-]+', text.strip()):
        return "email"
    # 代码片段（简单判断）
    if any(x in text for x in ['def ', 'function ', 'class ', 'import ', '{', '}', '=>', '->']):
        return "code"
    # 文件路径
    if re.match(r'^[A-Za-z]:\\|/[\w/]', text.strip()):
        return "path"
    return "text"


def read_clipboard():
    import subprocess
    ps_script = "Get-Clipboard -Raw"
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return None


def main():
    parser = argparse.ArgumentParser(description="增强版剪贴板")
    parser.add_argument("--read", action="store_true", help="读取剪贴板")
    parser.add_argument("--history", action="store_true", help="查看历史")
    parser.add_argument("--fav", help="收藏内容")
    parser.add_argument("--favorites", action="store_true", help="查看收藏")
    parser.add_argument("--delete", type=int, help="删除收藏")
    parser.add_argument("--clear", action="store_true", help="清除历史")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.clear:
        save_json(HISTORY_FILE, [])
        print("✓ 已清除历史")
        return 0

    if args.favorites:
        favs = load_json(FAVORITES_FILE, [])
        if args.json:
            print(json.dumps({"favorites": favs}, indent=2, ensure_ascii=False))
        else:
            print("===== 收藏列表 =====")
            for f in favs:
                print(f"{f['id']}. {f['content'][:50]}{'...' if len(f['content']) > 50 else ''}")
                print(f"   类型: {f['type']} | 时间: {f['time'][:16]}")
        return 0

    if args.fav:
        favs = load_json(FAVORITES_FILE, [])
        content_type = detect_content_type(args.fav)
        item = {"id": len(favs) + 1, "content": args.fav, "type": content_type, "time": datetime.now().isoformat()}
        favs.insert(0, item)
        save_json(FAVORITES_FILE, favs)
        print(f"✓ 已收藏: {args.fav[:30]}... ({content_type})")
        return 0

    if args.delete:
        favs = load_json(FAVORITES_FILE, [])
        favs = [f for f in favs if f['id'] != args.delete]
        save_json(FAVORITES_FILE, favs)
        print(f"✓ 已删除收藏 ID: {args.delete}")
        return 0

    if args.read:
        content = read_clipboard()
        if content:
            content_type = detect_content_type(content)
            # 保存到历史
            history = load_json(HISTORY_FILE, [])
            history.insert(0, {"content": content, "type": content_type, "time": datetime.now().isoformat()})
            history = history[:50]
            save_json(HISTORY_FILE, history)
            
            if args.json:
                print(json.dumps({"content": content, "type": content_type}, indent=2))
            else:
                print(f"类型: {content_type}")
                print(f"内容:\n{content[:200]}{'...' if len(content) > 200 else ''}")
        else:
            print("剪贴板为空")
        return 0

    if args.history:
        history = load_json(HISTORY_FILE, [])
        if args.json:
            print(json.dumps({"history": history[:20]}, indent=2, ensure_ascii=False))
        else:
            print("===== 剪贴板历史 =====")
            for i, h in enumerate(history[:20]):
                print(f"{i+1}. [{h['type']}] {h['content'][:40]}{'...' if len(h['content']) > 40 else ''}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
