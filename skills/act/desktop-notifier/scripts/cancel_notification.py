#!/usr/bin/env python3
"""取消通知"""
import argparse
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from lib.storage import load_notifications, save_notifications


def main():
    parser = argparse.ArgumentParser(description="取消通知")
    parser.add_argument("--id", type=int, required=True, help="通知ID")
    
    args = parser.parse_args()
    
    data = load_notifications()
    notifications = data.get("notifications", [])
    
    # 查找并删除
    found = False
    new_notifications = []
    for n in notifications:
        if n.get("id") == args.id:
            found = True
            print(f"✓ 已取消通知: {n.get('title')}")
        else:
            new_notifications.append(n)
    
    if not found:
        print(f"✗ 未找到ID为 {args.id} 的通知")
        return 1
    
    data["notifications"] = new_notifications
    save_notifications(data)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
