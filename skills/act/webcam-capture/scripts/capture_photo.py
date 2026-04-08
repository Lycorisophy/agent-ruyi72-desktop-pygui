"""
摄像头拍照脚本
调用摄像头拍照并保存

用法:
    python capture_photo.py                    # 拍照一张
    python capture_photo.py --burst 3          # 连拍3张
    python capture_photo.py --delay 3         # 3秒后拍照
    python capture_photo.py --list-devices    # 列出可用摄像头
    python capture_photo.py --device 0        # 指定摄像头设备
"""

import cv2
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# 配置
WORKSPACE = Path.home() / ".ruyi72" / "workspace"
CAPTURE_DIR = WORKSPACE / "memory" / "webcam-capture"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

def list_cameras(max_devices=10):
    """列出所有可用的摄像头"""
    available_cameras = []
    
    for i in range(max_devices):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(i)
        
        if cap is not None and cap.isOpened():
            # 获取摄像头信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            available_cameras.append({
                'index': i,
                'width': width,
                'height': height,
                'fps': fps
            })
            cap.release()
            print(f"[摄像头 {i}] 分辨率: {width}x{height}, FPS: {fps}")
        else:
            if cap:
                cap.release()
    
    if not available_cameras:
        print("[错误] 未找到可用的摄像头设备")
        return []
    
    print(f"\n共找到 {len(available_cameras)} 个摄像头设备")
    return available_cameras

def capture_photo(device=0, delay=0, filename=None, resolution=None):
    """拍照并保存"""
    # 打开摄像头
    cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(device)
    
    if not cap.isOpened():
        print(f"[错误] 无法打开摄像头设备 {device}")
        return None
    
    # 设置分辨率
    if resolution:
        width, height = map(int, resolution.split('x'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # 预热摄像头
    for _ in range(5):
        cap.read()
    
    # 延时拍照
    if delay > 0:
        print(f"[提示] {delay}秒后拍照...")
        time.sleep(delay)
    
    # 拍照
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("[错误] 拍照失败，无法读取帧")
        return None
    
    # 生成文件名
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{timestamp}.jpg"
    
    filepath = CAPTURE_DIR / filename
    
    # 保存图片
    cv2.imwrite(str(filepath), frame)
    print(f"[成功] 照片已保存: {filepath}")
    
    return str(filepath)

def capture_burst(device=0, count=3, interval=1):
    """连拍多张照片"""
    files = []
    
    for i in range(count):
        print(f"[连拍] 第 {i+1}/{count} 张...")
        filepath = capture_photo(device=device, delay=0 if i > 0 else 0)
        
        # 重命名为连拍格式
        if filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"photo_{timestamp}_burst_{i+1}.jpg"
            new_path = CAPTURE_DIR / new_name
            os.rename(filepath, new_path)
            files.append(str(new_path))
            print(f"[连拍] 第 {i+1} 张已保存: {new_path}")
        
        # 连拍间隔
        if i < count - 1 and interval > 0:
            time.sleep(interval)
    
    print(f"\n[完成] 连拍 {count} 张照片完成！")
    return files

def main():
    parser = argparse.ArgumentParser(description='摄像头拍照工具')
    parser.add_argument('--device', '-d', type=int, default=0, help='摄像头设备索引 (默认: 0)')
    parser.add_argument('--burst', '-b', type=int, default=0, help='连拍数量 (默认: 0, 表示单张)')
    parser.add_argument('--delay', type=float, default=0, help='拍照延时秒数 (默认: 0，支持小数如0.5)')
    parser.add_argument('--filename', '-f', type=str, default=None, help='自定义文件名')
    parser.add_argument('--resolution', '-r', type=str, default=None, help='分辨率，如 1920x1080')
    parser.add_argument('--list-devices', '-l', action='store_true', help='列出可用摄像头')
    parser.add_argument('--interval', type=float, default=1, help='连拍间隔秒数 (默认: 1，支持小数如0.5)')
    
    args = parser.parse_args()
    
    # 列出设备
    if args.list_devices:
        list_cameras()
        return
    
    # 拍照
    if args.burst > 0:
        capture_burst(device=args.device, count=args.burst, interval=args.interval)
    else:
        result = capture_photo(
            device=args.device,
            delay=args.delay,
            filename=args.filename,
            resolution=args.resolution
        )
        if result:
            print(f"\n照片路径: {result}")

if __name__ == "__main__":
    main()
