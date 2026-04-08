#!/usr/bin/env python3
"""快捷笔记"""
import argparse
import json
import os
import sys
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/quick-notes")
NOTES_FILE = os.path.join(STORAGE_DIR, "notes.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_notes():
    ensure_dir()
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_notes(notes):
    ensure_dir()
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="快捷笔记")
    parser.add_argument("--add", help="添加笔记")
    parser.add_argument("--list", action="store_true", help="列出笔记")
    parser.add_argument("--search", help="搜索笔记")
    parser.add_argument("--delete", type=int, help="删除笔记(ID)")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    notes = load_notes()

    if args.add:
        note = {"id": len(notes) + 1, "content": args.add, "time": datetime.now().isoformat()}
        notes.insert(0, note)
        save_notes(notes)
        print(f"✓ 已保存笔记 (ID: {note['id']})")
        return 0

    if args.delete:
        notes = [n for n in notes if n["id"] != args.delete]
        save_notes(notes)
        print(f"✓ 已删除笔记 ID: {args.delete}")
        return 0

    if args.search:
        results = [n for n in notes if args.search.lower() in n["content"].lower()]
        if args.json:
            print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
        else:
            print(f"===== 搜索结果 ({len(results)}条) =====")
            for n in results:
                print(f"{n['id']}. {n['content'][:60]}{'...' if len(n['content']) > 60 else ''}")
        return 0

    if args.list:
        if args.json:
            print(json.dumps({"notes": notes}, indent=2, ensure_ascii=False))
        else:
            print(f"===== 笔记列表 ({len(notes)}条) =====")
            for n in notes:
                print(f"{n['id']}. {n['content'][:60]}{'...' if len(n['content']) > 60 else ''}")
                print(f"   {n['time'][:16]}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
