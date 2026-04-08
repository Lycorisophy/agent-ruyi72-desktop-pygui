#!/usr/bin/env python3
"""Windows Paint Skill for Ruyi72"""
import subprocess
import sys
import os

def open_paint(image_path=None):
    """打开 Windows 画图程序"""
    try:
        if image_path and os.path.exists(image_path):
            # 用画图打开指定图片
            subprocess.Popen(['start', 'mspaint', image_path], shell=True)
            return f"✅ 已用画图打开图片：{image_path}"
        else:
            # 打开画图程序
            subprocess.Popen(['start', 'mspaint'], shell=True)
            return "✅ 已打开 Windows 画图程序"
    except Exception as e:
        return f"❌ 打开画图失败：{str(e)}"

def open_snipping_tool():
    """打开 Windows 截图工具"""
    try:
        subprocess.Popen(['start', 'snippingtool'], shell=True)
        return "✅ 已打开截图工具"
    except Exception as e:
        return f"❌ 打开截图工具失败：{str(e)}"

def main():
    if len(sys.argv) < 2:
        print("""
🎨 Windows Paint Skill

使用方法：
  python windows_paint.py              # 打开画图程序
  python windows_paint.py <图片路径>    # 用画图打开图片
  python windows_paint.py --snip       # 打开截图工具
""")
        return
    
    if sys.argv[1] == '--snip':
        print(open_snipping_tool())
    else:
        image_path = sys.argv[1]
        print(open_paint(image_path))

if __name__ == '__main__':
    main()
