#!/usr/bin/env python3
"""剪贴板管理器"""
import argparse
import json
import os
import sys
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/clipboard-manager")
HISTORY_FILE = os.path.join(STORAGE_DIR, "history.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_history():
    ensure_dir()
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_history(history):
    ensure_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def read_clipboard():
    import subprocess
    ps_script = "Get-Clipboard -Raw"
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return None


def write_clipboard(text):
    import subprocess
    ps_script = f'Set-Clipboard -Value "{text}"'
    try:
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=5)
        return True
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description="剪贴板管理器")
    parser.add_argument("--read", action="store_true", help="读取剪贴板")
    parser.add_argument("--write", help="写入剪贴板")
    parser.add_argument("--history", action="store_true", help="查看历史")
    parser.add_argument("--clear", action="store_true", help="清除历史")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.clear:
        ensure_dir()
        save_history([])
        print("✓ 已清除剪贴板历史")
        return 0

    if args.read:
        content = read_clipboard()
        if content:
            # 保存到历史
            history = load_history()
            history.insert(0, {"content": content, "time": datetime.now().isoformat()})
            history = history[:20]  # 保留20条
            save_history(history)
            
            if args.json:
                print(json.dumps({"content": content}, indent=2))
            else:
                print(f"剪贴板内容:\n{content}")
        else:
            print("剪贴板为空")
        return 0

    if args.write:
        if write_clipboard(args.write):
            # 保存到历史
            history = load_history()
            history.insert(0, {"content": args.write, "time": datetime.now().isoformat()})
            history = history[:20]
            save_history(history)
            
            if args.json:
                print(json.dumps({"success": True, "content": args.write}))
            else:
                print(f"✓ 已复制到剪贴板:\n{args.write}")
        else:
            print("✗ 复制失败")
        return 0

    if args.history:
        history = load_history()
        if args.json:
            print(json.dumps({"history": history}, indent=2, ensure_ascii=False))
        else:
            print("===== 剪贴板历史 =====")
            for i, item in enumerate(history[:10]):
                print(f"{i+1}. {item['content'][:50]}{'...' if len(item['content']) > 50 else ''}")
                print(f"   {item['time']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
