#!/usr/bin/env python3
"""存储模块 - 管理通知数据"""
import json
import os
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/desktop-notifier")
NOTIFICATIONS_FILE = os.path.join(STORAGE_DIR, "notifications.json")


def ensure_storage_dir():
    """确保存储目录存在"""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_notifications():
    """加载通知列表"""
    ensure_storage_dir()
    if not os.path.exists(NOTIFICATIONS_FILE):
        return {"notifications": [], "last_id": 0}
    try:
        with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"notifications": [], "last_id": 0}


def save_notifications(data):
    """保存通知列表"""
    ensure_storage_dir()
    with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_notification(notification):
    """添加新通知"""
    data = load_notifications()
    data["last_id"] += 1
    notification["id"] = data["last_id"]
    notification["created_at"] = datetime.now().isoformat()
    data["notifications"].append(notification)
    save_notifications(data)
    return notification["id"]


def remove_notification(notif_id):
    """删除通知"""
    data = load_notifications()
    original_count = len(data["notifications"])
    data["notifications"] = [n for n in data["notifications"] if n.get("id") != notif_id]
    save_notifications(data)
    return len(data["notifications"]) < original_count


def get_pending_notifications():
    """获取待发送的通知"""
    data = load_notifications()
    now = datetime.now()
    pending = []
    for n in data["notifications"]:
        if n.get("status") == "pending":
            scheduled = datetime.fromisoformat(n["scheduled_at"])
            if scheduled <= now:
                pending.append(n)
    return pending


def mark_sent(notif_id):
    """标记通知已发送"""
    data = load_notifications()
    for n in data["notifications"]:
        if n.get("id") == notif_id:
            n["status"] = "sent"
            n["sent_at"] = datetime.now().isoformat()
    save_notifications(data)
