#!/usr/bin/env python3
"""
系统信息技能脚本

获取系统基本信息和资源使用情况
"""
import json
import platform
import sys


def get_system_info(info_type: str = "all"):
    """获取系统信息"""
    info = {}
    
    if info_type in ["all", "os"]:
        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
    
    if info_type in ["all", "cpu"]:
        try:
            import psutil
            info["cpu"] = {
                "count": psutil.cpu_count(),
                "percent": psutil.cpu_percent(interval=0.1),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            }
        except ImportError:
            info["cpu"] = {"count": platform.os.cpu_count(), "note": "psutil not installed"}
    
    if info_type in ["all", "memory"]:
        try:
            import psutil
            mem = psutil.virtual_memory()
            info["memory"] = {
                "total": f"{mem.total / (1024**3):.2f} GB",
                "available": f"{mem.available / (1024**3):.2f} GB",
                "percent": mem.percent,
                "used": f"{mem.used / (1024**3):.2f} GB",
            }
        except ImportError:
            info["memory"] = {"note": "psutil not installed"}
    
    if info_type in ["all", "disk"]:
        try:
            import psutil
            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total": f"{usage.total / (1024**3):.2f} GB",
                        "used": f"{usage.used / (1024**3):.2f} GB",
                        "free": f"{usage.free / (1024**3):.2f} GB",
                        "percent": usage.percent,
                    })
                except:
                    pass
            info["disk"] = partitions
        except ImportError:
            info["disk"] = {"note": "psutil not installed"}
    
    return info


def main():
    params = json.loads(sys.stdin.read())
    
    info_type = params.get("info_type", "all")
    
    info = get_system_info(info_type)
    
    # 格式化输出
    lines = []
    for category, data in info.items():
        lines.append(f"=== {category.upper()} ===")
        if isinstance(data, dict):
            for key, value in data.items():
                lines.append(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    for key, value in item.items():
                        lines.append(f"  {key}: {value}")
                    lines.append("")
    
    result = {
        "success": True,
        "output": "\n".join(lines),
        "metadata": info,
    }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
