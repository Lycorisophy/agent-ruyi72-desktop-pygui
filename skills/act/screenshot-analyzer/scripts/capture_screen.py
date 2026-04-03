#!/usr/bin/env python3
"""截图脚本 - 截取屏幕"""
import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 确保可以导入mss
try:
    import mss
    import mss.tools
except ImportError:
    print("错误: 需要安装 mss 库")
    print("请运行: pip install mss")
    sys.exit(1)

# 存储目录
STORAGE_DIR = os.path.expanduser("~/.openclaw/workspace/memory/screenshot-analyzer")


def ensure_dir():
    """确保目录存在"""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def capture_fullscreen(monitor_id=1):
    """截取全屏"""
    with mss.mss() as sct:
        # 获取指定显示器
        monitor = sct.monitors[monitor_id]
        screenshot = sct.grab(monitor)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(STORAGE_DIR, filename)
        
        # 保存图片
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=filepath)
        
        return filepath, screenshot.size


def capture_region(x, y, width, height):
    """截取指定区域"""
    with mss.mss() as sct:
        # 定义区域
        region = {
            "left": x,
            "top": y,
            "width": width,
            "height": height
        }
        
        screenshot = sct.grab(region)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_region_{timestamp}.png"
        filepath = os.path.join(STORAGE_DIR, filename)
        
        # 保存图片
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=filepath)
        
        return filepath, screenshot.size


def capture_active_window():
    """截取活动窗口（使用PowerShell）"""
    import subprocess
    
    # 使用PowerShell获取活动窗口并截图
    ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;
public class ScreenCapture {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left, Top, Right, Bottom;
    }
}
"@

$hwnd = [ScreenCapture]::GetForegroundWindow()
$rect = New-Object ScreenCapture+RECT
[ScreenCapture]::GetWindowRect($hwnd, [ref]$rect)

$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top

Add-Type -AssemblyName System.Windows.Forms
$bitmap = New-Object System.Drawing.Bitmap($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size($width, $height)))

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$filename = "screenshot_window_$timestamp.png"
$filepath = Join-Path $env:USERPROFILE ".openclaw\\workspace\\memory\\screenshot-analyzer\\screenshots\\$filename"

if (!(Test-Path (Split-Path $filepath))) { New-Item -ItemType Directory -Path (Split-Path $filepath) -Force | Out-Null }
$bitmap.Save($filepath, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()

Write-Output $filepath
'''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            filepath = result.stdout.strip()
            if os.path.exists(filepath):
                # 获取图片尺寸
                from PIL import Image
                with Image.open(filepath) as img:
                    size = img.size
                return filepath, size
        return None, None
    except Exception as e:
        print(f"截图失败: {e}")
        return None, None


def list_monitors():
    """列出所有显示器"""
    with mss.mss() as sct:
        monitors = []
        for i, mon in enumerate(sct.monitors):
            if i == 0:
                continue  # 跳过合并的矩形
            monitors.append({
                "id": i,
                "width": mon["width"],
                "height": mon["height"],
                "left": mon["left"],
                "top": mon["top"]
            })
        return monitors


def main():
    parser = argparse.ArgumentParser(description="屏幕截图工具")
    parser.add_argument("--mode", choices=["fullscreen", "region", "window", "list-monitors"],
                       default="fullscreen", help="截图模式")
    parser.add_argument("--monitor", type=int, default=1, help="显示器编号（1=主屏）")
    parser.add_argument("--x", type=int, help="区域截图 X坐标")
    parser.add_argument("--y", type=int, help="区域截图 Y坐标")
    parser.add_argument("--width", type=int, help="区域截图 宽度")
    parser.add_argument("--height", type=int, help="区域截图 高度")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    ensure_dir()
    
    if args.mode == "list-monitors":
        monitors = list_monitors()
        if args.json:
            print(json.dumps({"monitors": monitors}, indent=2))
        else:
            print("可用显示器:")
            for m in monitors:
                print(f"  显示器 {m['id']}: {m['width']}x{m['height']} (left:{m['left']}, top:{m['top']})")
        return 0
    
    if args.mode == "fullscreen":
        filepath, size = capture_fullscreen(args.monitor)
        mode_name = f"显示器{args.monitor}"
    elif args.mode == "region":
        if args.x is None or args.y is None or args.width is None or args.height is None:
            parser.error("区域模式需要指定 --x, --y, --width, --height")
        filepath, size = capture_region(args.x, args.y, args.width, args.height)
        mode_name = f"区域({args.x},{args.y},{args.width},{args.height})"
    elif args.mode == "window":
        filepath, size = capture_active_window()
        mode_name = "活动窗口"
    else:
        parser.error("未知模式")
        return 1
    
    if filepath and size:
        print(f"✓ 截图成功: {mode_name}")
        print(f"  文件: {filepath}")
        print(f"  尺寸: {size[0]}x{size[1]}")
        if args.json:
            print(json.dumps({
                "success": True,
                "filepath": filepath,
                "width": size[0],
                "height": size[1],
                "mode": mode_name,
                "timestamp": datetime.now().isoformat()
            }, indent=2))
        return 0
    else:
        print("✗ 截图失败")
        if args.json:
            print(json.dumps({"success": False, "error": "截图失败"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
