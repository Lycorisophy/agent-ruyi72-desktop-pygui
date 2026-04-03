#!/usr/bin/env python3
"""列出所有通知"""
import argparse
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from lib.storage import load_notifications


def format_datetime(dt_str):
    """格式化日期时间"""
    if not dt_str:
        return "-"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return dt_str


def main():
    parser = argparse.ArgumentParser(description="列出通知")
    parser.add_argument("--status", choices=["all", "pending", "sent"],
                       default="all", help="筛选状态")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    data = load_notifications()
    notifications = data.get("notifications", [])
    
    # 筛选
    if args.status != "all":
        notifications = [n for n in notifications if n.get("status") == args.status]
    
    if args.json:
        import json
        print(json.dumps({"notifications": notifications, "count": len(notifications)}, 
                        ensure_ascii=False, indent=2))
        return 0
    
    if not notifications:
        print("暂无通知记录")
        return 0
    
    # 表格输出
    print(f"共 {len(notifications)} 条通知")
    print("-" * 70)
    print(f"{'ID':<4} {'状态':<8} {'标题':<20} {'时间':<15}")
    print("-" * 70)
    
    for n in notifications:
        status = n.get("status", "unknown")
        title = n.get("title", "")[:18]
        if args.status == "all":
            time_info = format_datetime(n.get("scheduled_at") or n.get("sent_at") or n.get("created_at"))
        else:
            time_info = format_datetime(n.get("scheduled_at") or n.get("created_at"))
        
        print(f"{n.get('id', '-'):<4} {status:<8} {title:<20} {time_info:<15}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
