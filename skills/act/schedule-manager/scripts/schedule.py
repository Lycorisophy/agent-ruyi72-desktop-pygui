#!/usr/bin/env python3
"""日程管理器"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

STORAGE_DIR = os.path.expanduser("~/.openclaw/workspace/memory/schedule-manager")
DATA_FILE = os.path.join(STORAGE_DIR, "data.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_data():
    ensure_dir()
    if not os.path.exists(DATA_FILE):
        return {"schedule": [], "memories": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"schedule": [], "memories": []}


def save_data(data):
    ensure_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


def get_week_range():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="日程管理")
    parser.add_argument("--add", help="添加日程")
    parser.add_argument("--date", help="日程日期 (YYYY-MM-DD)")
    parser.add_argument("--today", action="store_true", help="查看今日日程")
    parser.add_argument("--week", action="store_true", help="查看本周日程")
    parser.add_argument("--add-memory", help="添加纪念日")
    parser.add_argument("--memories", action="store_true", help="查看纪念日")
    parser.add_argument("--delete", type=int, help="删除日程(ID)")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    data = load_data()

    if args.add:
        date = args.date or get_today()
        item = {"id": len(data["schedule"]) + 1, "content": args.add, "date": date, "time": datetime.now().isoformat()}
        data["schedule"].append(item)
        save_data(data)
        print(f"✓ 已添加日程: {args.add} ({date})")
        return 0

    if args.add_memory:
        item = {"id": len(data["memories"]) + 1, "name": args.add_memory, "date": args.date or get_today()[5:], "time": datetime.now().isoformat()}
        data["memories"].append(item)
        save_data(data)
        print(f"✓ 已添加纪念日: {args.add_memory} ({item['date']})")
        return 0

    if args.delete:
        data["schedule"] = [s for s in data["schedule"] if s["id"] != args.delete]
        save_data(data)
        print(f"✓ 已删除日程 ID: {args.delete}")
        return 0

    if args.today:
        today = get_today()
        items = [s for s in data["schedule"] if s["date"] == today]
        if args.json:
            print(json.dumps({"today": items}, indent=2, ensure_ascii=False))
        else:
            print(f"===== 今日日程 ({today}) =====")
            if items:
                for s in items:
                    print(f"{s['id']}. {s['content']}")
            else:
                print("无日程")
        return 0

    if args.week:
        monday, sunday = get_week_range()
        items = [s for s in data["schedule"] if monday <= s["date"] <= sunday]
        if args.json:
            print(json.dumps({"week": items, "start": monday, "end": sunday}, indent=2, ensure_ascii=False))
        else:
            print(f"===== 本周日程 ({monday} ~ {sunday}) =====")
            if items:
                for s in sorted(items, key=lambda x: x["date"]):
                    print(f"{s['date']}: {s['content']}")
            else:
                print("无日程")
        return 0

    if args.memories:
        if args.json:
            print(json.dumps({"memories": data["memories"]}, indent=2, ensure_ascii=False))
        else:
            print("===== 纪念日 =====")
            if data["memories"]:
                for m in data["memories"]:
                    print(f"• {m['name']} - {m['date']}")
            else:
                print("无纪念日")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
