#!/usr/bin/env python3
"""音乐控制器 - 控制音乐播放器和获取播放信息"""
import argparse
import json
import subprocess
import sys


def get_media_info():
    """获取当前媒体播放信息"""
    ps_script = '''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
$session = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetResults().GetCurrentSession()
if ($session) {
    $props = $session.TryGetMediaPropertiesAsync().GetResults()
    $state = $session.PlaybackState
    $info = @{
        "title" = if ($props.Title) { $props.Title.ToString() } else { "" }
        "artist" = if ($props.Artist) { $props.Artist.ToString() } else { "" }
        "album" = if ($props.AlbumTitle) { $props.AlbumTitle.ToString() } else { "" }
        "state" = $state.ToString()
    }
    $info | ConvertTo-Json
} else {
    @{"error" = "No media session"} | ConvertTo-Json
}
'''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        else:
            return {"error": "无法获取媒体信息", "details": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def media_control(action):
    """执行媒体控制操作"""
    actions = {
        "play": "Play",
        "pause": "Pause", 
        "toggle": "TogglePlayPause",
        "next": "Next",
        "previous": "Previous"
    }
    
    if action not in actions:
        return {"error": f"未知操作: {action}"}
    
    ps_script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
$session = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetResults().GetCurrentSession()
if ($session) {{
    $session.{actions[action]}()
    @{{"success" = "true", "action" = "{action}"}} | ConvertTo-Json
}} else {{
    @{{"error" = "No media session"}} | ConvertTo-Json
}}
'''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        else:
            return {"error": "操作失败", "details": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def format_output(data):
    """格式化输出"""
    if "error" in data:
        return f"错误: {data['error']}"
    
    if "success" in data:
        action_names = {
            "play": "播放",
            "pause": "暂停",
            "toggle": "切换播放/暂停",
            "next": "下一首",
            "previous": "上一首"
        }
        return f"✓ {action_names.get(data['action'], data['action'])} 操作已执行"
    
    # 播放信息
    state_names = {
        "Playing": "正在播放",
        "Paused": "已暂停",
        "Stopped": "已停止",
        "None": "无媒体"
    }
    
    lines = ["===== 播放信息 ====="]
    state = data.get("state", "None")
    lines.append(f"状态: {state_names.get(state, state)}")
    
    if data.get("title"):
        lines.append(f"歌曲: {data['title']}")
    if data.get("artist"):
        lines.append(f"艺术家: {data['artist']}")
    if data.get("album"):
        lines.append(f"专辑: {data['album']}")
    
    if not any([data.get("title"), data.get("artist"), data.get("album")]):
        lines.append("(无媒体播放)")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="音乐控制器")
    parser.add_argument("--status", action="store_true", help="获取播放状态")
    parser.add_argument("--play", action="store_true", help="播放")
    parser.add_argument("--pause", action="store_true", help="暂停")
    parser.add_argument("--toggle", action="store_true", help="切换播放/暂停")
    parser.add_argument("--next", action="store_true", help="下一首")
    parser.add_argument("--previous", action="store_true", help="上一首")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    # 确定操作
    if args.status:
        data = get_media_info()
    elif args.play:
        data = media_control("play")
    elif args.pause:
        data = media_control("pause")
    elif args.toggle:
        data = media_control("toggle")
    elif args.next:
        data = media_control("next")
    elif args.previous:
        data = media_control("previous")
    else:
        data = get_media_info()
    
    # 输出
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_output(data))
    
    return 0 if "error" not in data else 1


if __name__ == "__main__":
    sys.exit(main())
