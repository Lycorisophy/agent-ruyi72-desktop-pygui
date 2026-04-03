#!/usr/bin/env python3
"""
System Monitor Skill for OpenClaw
Windows 系统监控技能，监控 CPU、内存、磁盘、网络等系统资源
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime


def run_powershell(command):
    """
    执行 PowerShell 命令并返回结果
    
    Args:
        command: PowerShell 命令字符串
        
    Returns:
        tuple: (success: bool, output: str, error: str)
    """
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, '', '命令执行超时'
    except Exception as e:
        return False, '', f'执行错误: {str(e)}'


def get_cpu_info():
    """
    获取 CPU 信息
    
    Returns:
        dict: CPU 信息
    """
    ps_command = '''
    Get-CimInstance Win32_Processor | 
    Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,
    L2CacheSize,L3CacheSize,LoadPercentage | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            cpu = json.loads(output)
            return cpu if isinstance(cpu, list) else cpu
        except json.JSONDecodeError:
            return None
    return None


def get_memory_info():
    """
    获取内存信息
    
    Returns:
        dict: 内存信息
    """
    ps_command = '''
    Get-CimInstance Win32_OperatingSystem | 
    Select-Object TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,FreeVirtualMemory,
    CSName,Version,BuildNumber | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            mem = json.loads(output)
            if isinstance(mem, list):
                mem = mem[0]
            
            # 转换内存单位
            total_phys_mb = round(int(mem.get('TotalVisibleMemorySize', 0)) / 1024, 2)
            free_phys_mb = round(int(mem.get('FreePhysicalMemory', 0)) / 1024, 2)
            used_phys_mb = total_phys_mb - free_phys_mb
            phys_percent = round(used_phys_mb / total_phys_mb * 100, 1) if total_phys_mb > 0 else 0
            
            total_virt_mb = round(int(mem.get('TotalVirtualMemorySize', 0)) / 1024, 2)
            free_virt_mb = round(int(mem.get('FreeVirtualMemory', 0)) / 1024, 2)
            used_virt_mb = total_virt_mb - free_virt_mb
            virt_percent = round(used_virt_mb / total_virt_mb * 100, 1) if total_virt_mb > 0 else 0
            
            mem['TotalPhysicalMB'] = total_phys_mb
            mem['FreePhysicalMB'] = free_phys_mb
            mem['UsedPhysicalMB'] = used_phys_mb
            mem['PhysicalPercent'] = phys_percent
            mem['TotalVirtualMB'] = total_virt_mb
            mem['FreeVirtualMB'] = free_virt_mb
            mem['UsedVirtualMB'] = used_virt_mb
            mem['VirtualPercent'] = virt_percent
            
            return mem
        except json.JSONDecodeError:
            return None
    return None


def get_disk_info():
    """
    获取磁盘信息
    
    Returns:
        list: 磁盘分区列表
    """
    ps_command = '''
    Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | 
    Select-Object DeviceID,VolumeName,Size,FreeSpace,DriveType,FileSystem | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            disks = json.loads(output)
            disks = disks if isinstance(disks, list) else [disks]
            
            for disk in disks:
                size_gb = round(disk.get('Size', 0) / (1024**3), 2)
                free_gb = round(disk.get('FreeSpace', 0) / (1024**3), 2)
                used_gb = size_gb - free_gb
                percent = round(used_gb / size_gb * 100, 1) if size_gb > 0 else 0
                
                disk['SizeGB'] = size_gb
                disk['FreeGB'] = free_gb
                disk['UsedGB'] = used_gb
                disk['UsedPercent'] = percent
            
            return disks
        except json.JSONDecodeError:
            return []
    return []


def get_network_info():
    """
    获取网络信息
    
    Returns:
        list: 网络适配器列表
    """
    ps_command = '''
    Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | 
    Select-Object Name,InterfaceDescription,Status,Speed,MacAddress,ReceiveBufferSize,TransmitBufferSize | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            adapters = json.loads(output)
            adapters = adapters if isinstance(adapters, list) else [adapters]
            
            for adapter in adapters:
                speed = adapter.get('Speed', 0)
                if speed > 0:
                    if speed >= 10**9:
                        adapter['SpeedText'] = f'{round(speed / 10**9, 2)} Gbps'
                    elif speed >= 10**6:
                        adapter['SpeedText'] = f'{round(speed / 10**6, 2)} Mbps'
                    else:
                        adapter['SpeedText'] = f'{speed} Kbps'
                else:
                    adapter['SpeedText'] = 'N/A'
            
            return adapters
        except json.JSONDecodeError:
            return []
    return []


def get_system_info():
    """
    获取系统信息
    
    Returns:
        dict: 系统信息
    """
    ps_command = '''
    Get-CimInstance Win32_OperatingSystem | 
    Select-Object CSName,Caption,Version,BuildNumber,OSArchitecture,RegisteredUser,
    SerialNumber,InstallDate,LastBootUpTime,LocalDateTime | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            sysinfo = json.loads(output)
            if isinstance(sysinfo, list):
                sysinfo = sysinfo[0]
            
            # 格式化时间
            boot_time = sysinfo.get('LastBootUpTime')
            if boot_time and isinstance(boot_time, str):
                try:
                    dt = datetime.fromisoformat(boot_time.replace('Z', '+00:00'))
                    sysinfo['LastBootUpTime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    uptime = datetime.now() - dt
                    days = uptime.days
                    hours, remainder = divmod(uptime.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    sysinfo['Uptime'] = f'{days} 天 {hours} 小时 {minutes} 分钟'
                except:
                    sysinfo['Uptime'] = 'N/A'
            
            current_time = sysinfo.get('LocalDateTime')
            if current_time and isinstance(current_time, str):
                try:
                    dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
                    sysinfo['LocalDateTime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            return sysinfo
        except json.JSONDecodeError:
            return None
    return None


def get_top_processes(by='cpu', top_n=10):
    """
    获取资源占用最高的进程
    
    Args:
        by: 排序字段 (cpu, memory)
        top_n: 返回数量
        
    Returns:
        list: 进程列表
    """
    ps_command = f'''
    Get-Process | Sort-Object -Property {"CPU" if by == "cpu" else "WorkingSet64"} -Descending | 
    Select-Object -First {top_n} Id,ProcessName,CPU,WorkingSet64 | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            processes = json.loads(output)
            processes = processes if isinstance(processes, list) else [processes]
            
            for p in processes:
                ws = p.get('WorkingSet64', 0)
                p['MemoryMB'] = round(ws / (1024 * 1024), 2)
            
            return processes
        except json.JSONDecodeError:
            return []
    return []


def format_system_status(cpu, memory, disks, network, sysinfo):
    """
    格式化系统状态输出
    
    Returns:
        str: 格式化后的输出
    """
    lines = []
    lines.append('=' * 70)
    lines.append('Windows 系统资源监控')
    lines.append('=' * 70)
    lines.append(f'监控时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('')
    
    # CPU 信息
    if cpu:
        lines.append('─' * 70)
        lines.append('📊 CPU 信息')
        lines.append('─' * 70)
        lines.append(f'  处理器: {cpu.get("Name", "N/A")}')
        lines.append(f'  核心数: {cpu.get("NumberOfCores", "N/A")} 核 / {cpu.get("NumberOfLogicalProcessors", "N/A")} 线程')
        lines.append(f'  主频: {cpu.get("CurrentClockSpeed", "N/A")} MHz (最大: {cpu.get("MaxClockSpeed", "N/A")} MHz)')
        lines.append(f'  当前负载: {cpu.get("LoadPercentage", "N/A")}%')
        lines.append('')
    
    # 内存信息
    if memory:
        lines.append('─' * 70)
        lines.append('💾 内存信息')
        lines.append('─' * 70)
        phys_used = memory.get('UsedPhysicalMB', 0)
        phys_total = memory.get('TotalPhysicalMB', 0)
        phys_percent = memory.get('PhysicalPercent', 0)
        
        virt_used = memory.get('UsedVirtualMB', 0)
        virt_total = memory.get('TotalVirtualMB', 0)
        virt_percent = memory.get('VirtualPercent', 0)
        
        lines.append(f'  物理内存: {phys_used:.0f} MB / {phys_total:.0f} MB ({phys_percent}%)')
        lines.append(f'  虚拟内存: {virt_used:.0f} MB / {virt_total:.0f} MB ({virt_percent}%)')
        lines.append(f'  计算机名: {memory.get("CSName", "N/A")}')
        lines.append('')
    
    # 磁盘信息
    if disks:
        lines.append('─' * 70)
        lines.append('💿 磁盘信息')
        lines.append('─' * 70)
        for disk in disks:
            device_id = disk.get('DeviceID', 'N/A')
            volume_name = disk.get('VolumeName', '')
            size_gb = disk.get('SizeGB', 0)
            used_gb = disk.get('UsedGB', 0)
            free_gb = disk.get('FreeGB', 0)
            percent = disk.get('UsedPercent', 0)
            fs = disk.get('FileSystem', 'N/A')
            
            bar_length = 20
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            lines.append(f'  {device_id}: {volume_name} ({fs})')
            lines.append(f'    容量: {used_gb:.1f} GB / {size_gb:.1f} GB [{bar}] {percent}%')
            lines.append(f'    可用: {free_gb:.1f} GB')
        lines.append('')
    
    # 网络信息
    if network:
        lines.append('─' * 70)
        lines.append('🌐 网络信息')
        lines.append('─' * 70)
        for adapter in network:
            name = adapter.get('Name', 'N/A')
            desc = adapter.get('InterfaceDescription', 'N/A')[:40]
            speed = adapter.get('SpeedText', 'N/A')
            mac = adapter.get('MacAddress', 'N/A')
            lines.append(f'  {name}')
            lines.append(f'    {desc}')
            lines.append(f'    速度: {speed} | MAC: {mac}')
        lines.append('')
    
    # 系统信息
    if sysinfo:
        lines.append('─' * 70)
        lines.append('🖥️ 系统信息')
        lines.append('─' * 70)
        lines.append(f'  系统: {sysinfo.get("Caption", "N/A")}')
        lines.append(f'  版本: {sysinfo.get("Version", "N/A")} (Build {sysinfo.get("BuildNumber", "N/A")})')
        lines.append(f'  架构: {sysinfo.get("OSArchitecture", "N/A")}')
        lines.append(f'  运行时间: {sysinfo.get("Uptime", "N/A")}')
        lines.append('')
    
    lines.append('=' * 70)
    
    return '\n'.join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Windows 系统监控工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # all 命令 - 显示所有信息
    subparsers.add_parser('all', help='显示所有系统信息')
    
    # cpu 命令
    subparsers.add_parser('cpu', help='显示 CPU 信息')
    
    # memory 命令
    subparsers.add_parser('memory', help='显示内存信息')
    
    # disk 命令
    subparsers.add_parser('disk', help='显示磁盘信息')
    
    # network 命令
    subparsers.add_parser('network', help='显示网络信息')
    
    # system 命令
    subparsers.add_parser('system', help='显示系统信息')
    
    # top 命令
    parser_top = subparsers.add_parser('top', help='显示资源占用最高的进程')
    parser_top.add_argument('--count', type=int, default=10, help='显示数量')
    parser_top.add_argument('--by', choices=['cpu', 'memory'], default='cpu', help='排序依据')
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == 'all':
        cpu = get_cpu_info()
        memory = get_memory_info()
        disks = get_disk_info()
        network = get_network_info()
        sysinfo = get_system_info()
        print(format_system_status(cpu, memory, disks, network, sysinfo))
    
    elif args.command == 'cpu':
        cpu = get_cpu_info()
        if cpu:
            print(f'处理器: {cpu.get("Name", "N/A")}')
            print(f'核心数: {cpu.get("NumberOfCores", "N/A")} 核 / {cpu.get("NumberOfLogicalProcessors", "N/A")} 线程')
            print(f'主频: {cpu.get("CurrentClockSpeed", "N/A")} MHz')
            print(f'当前负载: {cpu.get("LoadPercentage", "N/A")}%')
        else:
            print('无法获取 CPU 信息')
    
    elif args.command == 'memory':
        memory = get_memory_info()
        if memory:
            phys_used = memory.get('UsedPhysicalMB', 0)
            phys_total = memory.get('TotalPhysicalMB', 0)
            phys_percent = memory.get('PhysicalPercent', 0)
            print(f'物理内存: {phys_used:.0f} MB / {phys_total:.0f} MB ({phys_percent}%)')
            
            bar_length = 30
            filled = int(bar_length * phys_percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f'使用率: [{bar}]')
        else:
            print('无法获取内存信息')
    
    elif args.command == 'disk':
        disks = get_disk_info()
        if disks:
            for disk in disks:
                device_id = disk.get('DeviceID', 'N/A')
                size_gb = disk.get('SizeGB', 0)
                used_percent = disk.get('UsedPercent', 0)
                print(f'{device_id}: {used_percent}% ({size_gb:.1f} GB)')
        else:
            print('无法获取磁盘信息')
    
    elif args.command == 'network':
        network = get_network_info()
        if network:
            for adapter in network:
                name = adapter.get('Name', 'N/A')
                speed = adapter.get('SpeedText', 'N/A')
                print(f'{name}: {speed}')
        else:
            print('无法获取网络信息或无活动的网络适配器')
    
    elif args.command == 'system':
        sysinfo = get_system_info()
        if sysinfo:
            print(f'计算机名: {sysinfo.get("CSName", "N/A")}')
            print(f'系统: {sysinfo.get("Caption", "N/A")}')
            print(f'版本: {sysinfo.get("Version", "N/A")} (Build {sysinfo.get("BuildNumber", "N/A")})')
            print(f'架构: {sysinfo.get("OSArchitecture", "N/A")}')
            print(f'运行时间: {sysinfo.get("Uptime", "N/A")}')
        else:
            print('无法获取系统信息')
    
    elif args.command == 'top':
        processes = get_top_processes(args.by, args.count)
        if processes:
            print(f'资源占用 Top {args.count} ({args.by}):')
            print(f'{"PID":<8} {"进程名":<25} {"CPU":<12} {"内存(MB)":<12}')
            print('-' * 60)
            for proc in processes:
                pid = proc.get('Id', 'N/A')
                name = proc.get('ProcessName', 'N/A')[:23]
                cpu = proc.get('CPU', '0')
                memory = proc.get('MemoryMB', 0)
                print(f'{pid:<8} {name:<25} {cpu:<12} {memory:<12}')
        else:
            print('无法获取进程信息')
    
    else:
        # 默认显示所有信息
        cpu = get_cpu_info()
        memory = get_memory_info()
        disks = get_disk_info()
        network = get_network_info()
        sysinfo = get_system_info()
        print(format_system_status(cpu, memory, disks, network, sysinfo))


if __name__ == '__main__':
    main()
