#!/usr/bin/env python3
"""增强记忆系统"""
import argparse
import json
import os
import sys
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/enhanced-memory")
MEMORY_FILE = os.path.join(STORAGE_DIR, "memory.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_memory():
    ensure_dir()
    if not os.path.exists(MEMORY_FILE):
        return {"important": [], "preferences": [], "events": [], "notes": []}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"important": [], "preferences": [], "events": [], "notes": []}


def save_memory(memory):
    ensure_dir()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="增强记忆")
    parser.add_argument("--remember", help="记住重要信息")
    parser.add_argument("--preference", help="记录偏好")
    parser.add_argument("--event", help="记录事件")
    parser.add_argument("--note", help="添加笔记")
    parser.add_argument("--list", action="store_true", help="查看所有记忆")
    parser.add_argument("--search", help="搜索记忆")
    parser.add_argument("--clear", action="store_true", help="清除记忆")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    memory = load_memory()

    if args.clear:
        save_memory({"important": [], "preferences": [], "events": [], "notes": []})
        print("✓ 已清除所有记忆")
        return 0

    if args.remember:
        item = {"content": args.remember, "time": datetime.now().isoformat()}
        memory["important"].insert(0, item)
        save_memory(memory)
        print(f"✓ 已记住: {args.remember}")
        return 0

    if args.preference:
        item = {"content": args.preference, "time": datetime.now().isoformat()}
        memory["preferences"].insert(0, item)
        save_memory(memory)
        print(f"✓ 已记录偏好: {args.preference}")
        return 0

    if args.event:
        item = {"content": args.event, "time": datetime.now().isoformat()}
        memory["events"].insert(0, item)
        save_memory(memory)
        print(f"✓ 已记录事件: {args.event}")
        return 0

    if args.note:
        item = {"content": args.note, "time": datetime.now().isoformat()}
        memory["notes"].insert(0, item)
        save_memory(memory)
        print(f"✓ 已添加笔记: {args.note}")
        return 0

    if args.search:
        keyword = args.search.lower()
        results = {"important": [], "preferences": [], "events": [], "notes": []}
        for cat in ["important", "preferences", "events", "notes"]:
            for item in memory.get(cat, []):
                if keyword in item.get("content", "").lower():
                    results[cat].append(item)
        
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"===== 搜索结果 =====")
            for cat, items in results.items():
                if items:
                    print(f"\n【{cat}】")
                    for item in items:
                        print(f"  • {item['content']}")
        return 0

    if args.list:
        if args.json:
            print(json.dumps(memory, indent=2, ensure_ascii=False))
        else:
            print("===== 记忆系统 =====")
            
            print("\n【重要信息】")
            if memory["important"]:
                for item in memory["important"][:5]:
                    print(f"  • {item['content']}")
            else:
                print("  (无)")
            
            print("\n【偏好】")
            if memory["preferences"]:
                for item in memory["preferences"][:5]:
                    print(f"  • {item['content']}")
            else:
                print("  (无)")
            
            print("\n【事件】")
            if memory["events"]:
                for item in memory["events"][:5]:
                    print(f"  • {item['content']}")
            else:
                print("  (无)")
            
            print("\n【笔记】")
            if memory["notes"]:
                for item in memory["notes"][:5]:
                    print(f"  • {item['content']}")
            else:
                print("  (无)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
