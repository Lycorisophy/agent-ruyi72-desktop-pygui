#!/usr/bin/env python3
"""发送即时或定时通知"""
import argparse
import os
import sys
import subprocess
import threading
import time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from lib.storage import load_notifications, save_notifications, ensure_storage_dir

# 通知模板
TEMPLATES = {
    "default": {
        "icon": "ℹ️",
        "sound": "Default"
    },
    "urgent": {
        "icon": "⚠️",
        "sound": "Urgent"
    },
    "health": {
        "icon": "💧",
        "sound": "Reminder"
    },
    "success": {
        "icon": "✅",
        "sound": "Default"
    }
}

# 健康提醒模板
HEALTH_REMINDERS = {
    "drink_water": {
        "title": "喝水时间到！",
        "message": "忙碌了很久吧？来喝杯水休息一下哦～💧"
    },
    "exercise": {
        "title": "运动时间到！",
        "message": "久坐对身体不好，起来活动一下吧！🏃"
    },
    "rest": {
        "title": "休息一下！",
        "message": "眼睛也需要休息，看看远处放松一下吧～👀"
    },
    "stand": {
        "title": "站起来走动！",
        "message": "坐太久了对身体不好，站起来走动一下吧！🚶"
    }
}


def send_windows_notification(title, message, template="default"):
    """发送Windows系统通知"""
    template_info = TEMPLATES.get(template, TEMPLATES["default"])
    icon = template_info["icon"]
    
    # 使用PowerShell发送通知
    ps_script = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    
    $template = @"
    <toast>
        <visual>
            <binding template="ToastText02">
                <text id="1">{icon} {title}</text>
                <text id="2">{message}</text>
            </binding>
        </visual>
        <audio src="ms-winsoundevent:Notification.{template_info['sound']}"/>
    </toast>
"@
    
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OpenClaw").Show($toast)
    '''
    
    try:
        # 尝试使用Windows PowerShell发送通知
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "通知已发送"
        else:
            # 降级方案：使用msg命令
            return send_notification_fallback(title, message)
    except Exception as e:
        return send_notification_fallback(title, message)


def send_notification_fallback(title, message):
    """降级方案：使用msg命令发送通知"""
    try:
        subprocess.run(
            ["msg", "*", f"{title}\n{message}"],
            capture_output=True,
            timeout=5
        )
        return True, "通知已发送（降级方案）"
    except Exception:
        return False, f"发送失败: {str(e)}"


def send_immediate_notification(title, message, template="default"):
    """发送即时通知"""
    success, info = send_windows_notification(title, message, template)
    if success:
        print(f"✓ 通知已发送: {title}")
        print(f"  内容: {message}")
    else:
        print(f"✗ 通知发送失败: {info}")
    return {"success": success, "message": info}


def schedule_notification(notif_id, title, message, scheduled_at, template="default"):
    """定时发送通知"""
    scheduled = datetime.fromisoformat(scheduled_at)
    now = datetime.now()
    delay = (scheduled - now).total_seconds()
    
    if delay <= 0:
        # 如果是过去的时间，立即发送
        return send_immediate_notification(title, message, template)
    
    print(f"✓ 定时通知已设置: {title}")
    print(f"  将在 {scheduled.strftime('%Y-%m-%d %H:%M:%S')} 发送")
    
    # 在后台线程中等待并发送
    def delayed_send():
        time.sleep(delay)
        send_windows_notification(title, message, template)
    
    thread = threading.Thread(target=delayed_send, daemon=True)
    thread.start()
    
    return {"success": True, "message": f"将在 {scheduled.strftime('%H:%M')} 发送"}


def parse_time_expression(time_expr):
    """解析时间表达式"""
    now = datetime.now()
    time_expr = time_expr.strip().lower()
    
    # 解析 "in X minutes/hours"
    if time_expr.startswith("in "):
        parts = time_expr[3:].strip()
        if "minute" in parts or "min" in parts:
            num = int(''.join(filter(str.isdigit, parts)))
            return (now + timedelta(minutes=num)).isoformat()
        elif "hour" in parts or "hr" in parts:
            num = int(''.join(filter(str.isdigit, parts)))
            return (now + timedelta(hours=num)).isoformat()
        elif "second" in parts or "sec" in parts:
            num = int(''.join(filter(str.isdigit, parts)))
            return (now + timedelta(seconds=num)).isoformat()
        elif "day" in parts:
            num = int(''.join(filter(str.isdigit, parts)))
            return (now + timedelta(days=num)).isoformat()
    
    # 解析具体时间 "at 14:30"
    if time_expr.startswith("at "):
        time_str = time_expr[3:].strip()
        try:
            target_time = datetime.strptime(time_str, "%H:%M")
            scheduled = now.replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0
            )
            if scheduled <= now:
                scheduled += timedelta(days=1)
            return scheduled.isoformat()
        except:
            pass
    
    # 默认：1小时后
    return (now + timedelta(hours=1)).isoformat()


def main():
    parser = argparse.ArgumentParser(description="发送桌面通知")
    parser.add_argument("--title", help="通知标题")
    parser.add_argument("--message", help="通知内容")
    parser.add_argument("--template", default="default", 
                       choices=["default", "urgent", "health", "success"],
                       help="通知模板类型")
    parser.add_argument("--schedule", help="定时表达式，如 'in 30 minutes' 或 'at 14:30'")
    parser.add_argument("--health-type", choices=["drink_water", "exercise", "rest", "stand"],
                       help="使用健康提醒模板")
    
    args = parser.parse_args()
    
    # 如果指定了健康提醒类型，使用对应模板
    if args.health_type:
        health = HEALTH_REMINDERS.get(args.health_type, HEALTH_REMINDERS["drink_water"])
        title = health["title"]
        message = health["message"]
        template = "health"
    else:
        if not args.title or not args.message:
            parser.error("--title 和 --message 是必需的（除非使用 --health-type）")
        title = args.title
        message = args.message
        template = args.template
    
    # 定时或即时发送
    if args.schedule:
        scheduled_at = parse_time_expression(args.schedule)
        result = schedule_notification(None, title, message, scheduled_at, template)
    else:
        result = send_immediate_notification(title, message, template)
    
    print(result)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
