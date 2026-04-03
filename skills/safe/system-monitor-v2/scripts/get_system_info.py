#!/usr/bin/env python3
"""系统监控脚本 - 获取系统状态信息"""
import argparse
import os
import sys
import json
import time
from datetime import datetime

try:
    import psutil
except ImportError:
    print("错误: 需要安装 psutil 库")
    print("请运行: pip install psutil")
    sys.exit(1)


def format_bytes(bytes_val):
    """格式化字节数"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def format_speed(speed_val):
    """格式化网速"""
    return format_bytes(speed_val) + "/s"


def get_uptime():
    """获取系统运行时间"""
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    now = datetime.now()
    uptime = now - boot_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}天 {hours}小时 {minutes}分钟"
    elif hours > 0:
        return f"{hours}小时 {minutes}分钟"
    else:
        return f"{minutes}分钟"


def get_cpu_info():
    """获取CPU信息"""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    freq_str = ""
    if cpu_freq:
        freq_str = f" (当前: {cpu_freq.current:.0f} MHz)"
    
    return {
        "usage": cpu_percent,
        "count": cpu_count,
        "frequency": cpu_freq.current if cpu_freq else None
    }


def get_memory_info():
    """获取内存信息"""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        "total": vm.total,
        "available": vm.available,
        "used": vm.used,
        "percent": vm.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent
    }


def get_disk_info():
    """获取磁盘信息"""
    disks = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disks.append({
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            })
        except:
            pass
    return disks


def get_network_info():
    """获取网络信息"""
    # 需要先获取初始值
    net1 = psutil.net_io_counters()
    time.sleep(1)
    net2 = psutil.net_io_counters()
    
    bytes_sent = net2.bytes_sent - net1.bytes_sent
    bytes_recv = net2.bytes_recv - net1.bytes_recv
    
    # 获取网络接口
    interfaces = []
    for iface, addrs in psutil.net_if_addrs().items():
        if iface != 'Loopback Pseudo-Interface 1':
            interfaces.append(iface)
    
    return {
        "bytes_sent": bytes_sent,
        "bytes_recv": bytes_recv,
        "packets_sent": net2.packets_sent - net1.packets_sent,
        "packets_recv": net2.packets_recv - net1.packets_recv,
        "interfaces": interfaces
    }


def get_battery_info():
    """获取电池信息"""
    battery = psutil.sensors_battery()
    if battery is None:
        return None
    
    percent = battery.percent
    seconds = battery.secsleft
    is_charging = battery.power_plugged
    
    # 格式化剩余时间
    if seconds == psutil.POWER_TIME_UNLIMITED:
        time_left = "充电中"
    elif seconds == psutil.POWER_TIME_UNKNOWN:
        time_left = "未知"
    else:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        time_left = f"{hours}小时 {minutes}分钟"
    
    return {
        "percent": percent,
        "time_left": time_left,
        "is_charging": is_charging,
        "power_plugged": is_charging
    }


def format_output(data, simple=False):
    """格式化输出"""
    if simple:
        # 简洁输出
        lines = []
        if "cpu" in data:
            lines.append(f"CPU: {data['cpu']['usage']}%")
        if "memory" in data:
            lines.append(f"内存: {data['memory']['used_gb']:.1f}GB / {data['memory']['total_gb']:.1f}GB ({data['memory']['percent']}%)")
        if "disk" in data:
            for d in data["disk"]:
                lines.append(f"磁盘 {d['mountpoint']}: {d['used_gb']:.1f}GB / {d['total_gb']:.1f}GB ({d['percent']}%)")
        if "network" in data:
            lines.append(f"网络: ↓{data['network']['download']}/s ↑{data['network']['upload']}/s")
        if "battery" in data and data["battery"]:
            status = "充电中" if data["battery"]["is_charging"] else f"{data['battery']['percent']}%"
            lines.append(f"电池: {status}")
        return "\n".join(lines)
    
    # 完整输出
    lines = ["===== 系统状态 ====="]
    
    # 主机信息
    hostname = os.environ.get('COMPUTERNAME', 'Unknown')
    lines.append(f"主机名: {hostname}")
    lines.append(f"运行时间: {data['uptime']}")
    lines.append("")
    
    # CPU
    if "cpu" in data:
        lines.append("【CPU】")
        lines.append(f"  使用率: {data['cpu']['usage']}%")
        lines.append(f"  核心数: {data['cpu']['count']}")
        if data['cpu'].get('frequency'):
            lines.append(f"  频率: {data['cpu']['frequency']:.0f} MHz")
        lines.append("")
    
    # 内存
    if "memory" in data:
        lines.append("【内存】")
        lines.append(f"  已用: {data['memory']['used_gb']:.1f} GB / {data['memory']['total_gb']:.1f} GB")
        lines.append(f"  使用率: {data['memory']['percent']}%")
        if data['memory']['swap_gb'] > 0:
            lines.append(f"  虚拟内存: {data['memory']['swap_gb']:.1f} GB")
        lines.append("")
    
    # 磁盘
    if "disk" in data:
        lines.append("【磁盘】")
        for d in data["disk"]:
            lines.append(f"  {d['mountpoint']}: {d['used_gb']:.1f} GB / {d['total_gb']:.1f} GB ({d['percent']}%)")
        lines.append("")
    
    # 网络
    if "network" in data:
        lines.append("【网络】")
        lines.append(f"  下载: {data['network']['download']}/s")
        lines.append(f"  上传: {data['network']['upload']}/s")
        if data["network"].get("interfaces"):
            lines.append(f"  接口: {', '.join(data['network']['interfaces'][:3])}")
        lines.append("")
    
    # 电池
    if "battery" in data and data["battery"]:
        lines.append("【电池】")
        status = "充电中" if data["battery"]["is_charging"] else f"{data['battery']['percent']}%"
        lines.append(f"  电量: {status}")
        if data["battery"]["time_left"] != "未知":
            lines.append(f"  剩余: {data['battery']['time_left']}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="系统监控工具")
    parser.add_argument("--cpu", action="store_true", help="仅显示CPU信息")
    parser.add_argument("--memory", action="store_true", help="仅显示内存信息")
    parser.add_argument("--disk", action="store_true", help="仅显示磁盘信息")
    parser.add_argument("--network", action="store_true", help="仅显示网络信息")
    parser.add_argument("--battery", action="store_true", help="仅显示电池信息")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--simple", action="store_true", help="简洁输出")
    
    args = parser.parse_args()
    
    # 收集数据
    data = {
        "uptime": get_uptime(),
        "timestamp": datetime.now().isoformat()
    }
    
    # 根据参数决定获取哪些数据
    get_all = not any([args.cpu, args.memory, args.disk, args.network, args.battery])
    
    if get_all or args.cpu:
        cpu = get_cpu_info()
        data["cpu"] = {
            "usage": cpu["usage"],
            "count": cpu["count"],
            "frequency": cpu.get("frequency")
        }
    
    if get_all or args.memory:
        mem = get_memory_info()
        data["memory"] = {
            "total": mem["total"],
            "available": mem["available"],
            "used": mem["used"],
            "percent": mem["percent"],
            "total_gb": mem["total"] / (1024**3),
            "available_gb": mem["available"] / (1024**3),
            "used_gb": mem["used"] / (1024**3),
            "swap_percent": mem["swap_percent"],
            "swap_gb": mem["swap_used"] / (1024**3)
        }
    
    if get_all or args.disk:
        disks = get_disk_info()
        data["disk"] = [{
            "device": d["device"],
            "mountpoint": d["mountpoint"],
            "total": d["total"],
            "used": d["used"],
            "free": d["free"],
            "percent": d["percent"],
            "total_gb": d["total"] / (1024**3),
            "used_gb": d["used"] / (1024**3),
            "free_gb": d["free"] / (1024**3)
        } for d in disks]
    
    if get_all or args.network:
        net = get_network_info()
        data["network"] = {
            "bytes_sent": net["bytes_sent"],
            "bytes_recv": net["bytes_recv"],
            "download": format_bytes(net["bytes_recv"]),
            "upload": format_bytes(net["bytes_sent"]),
            "interfaces": net["interfaces"]
        }
    
    if get_all or args.battery:
        battery = get_battery_info()
        data["battery"] = battery
    
    # 输出
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_output(data, simple=args.simple))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
