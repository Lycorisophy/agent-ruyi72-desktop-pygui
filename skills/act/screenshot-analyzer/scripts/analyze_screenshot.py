#!/usr/bin/env python3
"""截图分析脚本 - 分析截图内容"""
import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 存储目录
STORAGE_DIR = os.path.expanduser("~/.ruyi72/workspace/memory/screenshot-analyzer")


def find_latest_screenshot():
    """查找最新的截图"""
    if not os.path.exists(STORAGE_DIR):
        return None
    
    screenshots = [f for f in os.listdir(STORAGE_DIR) if f.endswith('.png')]
    if not screenshots:
        return None
    
    # 按修改时间排序
    screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(STORAGE_DIR, x)), reverse=True)
    return os.path.join(STORAGE_DIR, screenshots[0])


def list_screenshots():
    """列出所有截图"""
    if not os.path.exists(STORAGE_DIR):
        return []
    
    screenshots = [f for f in os.listdir(STORAGE_DIR) if f.endswith('.png')]
    screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(STORAGE_DIR, x)), reverse=True)
    
    result = []
    for s in screenshots:
        filepath = os.path.join(STORAGE_DIR, s)
        stat = os.stat(filepath)
        result.append({
            "filename": s,
            "filepath": filepath,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return result


def cleanup_old_screenshots(keep=5):
    """清理旧截图，保留最新的N张"""
    screenshots = list_screenshots()
    if len(screenshots) <= keep:
        return 0
    
    deleted = 0
    for s in screenshots[keep:]:
        try:
            os.remove(s["filepath"])
            deleted += 1
        except:
            pass
    return deleted


def main():
    parser = argparse.ArgumentParser(description="截图分析工具")
    parser.add_argument("--image", help="截图文件路径（省略则使用最新截图）")
    parser.add_argument("--list", action="store_true", help="列出所有截图")
    parser.add_argument("--cleanup", action="store_true", help="清理旧截图")
    parser.add_argument("--keep", type=int, default=5, help="保留最新截图数量")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    # 列出截图
    if args.list:
        screenshots = list_screenshots()
        if args.json:
            print(json.dumps({"screenshots": screenshots, "count": len(screenshots)}, indent=2))
        else:
            print(f"共有 {len(screenshots)} 张截图:")
            for s in screenshots:
                size_kb = s["size"] / 1024
                print(f"  {s['filename']} ({size_kb:.1f}KB) - {s['modified']}")
        return 0
    
    # 清理截图
    if args.cleanup:
        deleted = cleanup_old_screenshots(args.keep)
        print(f"已清理 {deleted} 张旧截图，保留最新 {args.keep} 张")
        return 0
    
    # 确定图片路径
    if args.image:
        image_path = args.image
    else:
        image_path = find_latest_screenshot()
    
    if not image_path or not os.path.exists(image_path):
        print("错误: 未找到截图文件")
        print("请先运行截图命令: python capture_screen.py")
        if args.json:
            print(json.dumps({"success": False, "error": "未找到截图文件"}))
        return 1
    
    print(f"截图文件: {image_path}")
    print(f"\n请使用Ruyi72的image-understanding技能分析此图片")
    print(f"或直接告诉我，我会使用技能帮你分析")
    
    if args.json:
        print(json.dumps({
            "success": True,
            "filepath": image_path,
            "message": "请使用image-understanding技能分析"
        }))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
