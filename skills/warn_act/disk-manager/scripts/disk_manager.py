#!/usr/bin/env python3
"""
Disk Manager Skill for OpenClaw
Windows 磁盘管理技能，查看磁盘分区、空间信息和目录大小
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


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
            timeout=60
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, '', '命令执行超时'
    except Exception as e:
        return False, '', f'执行错误: {str(e)}'


def get_physical_disks():
    """
    获取物理磁盘信息
    
    Returns:
        list: 物理磁盘列表
    """
    ps_command = '''
    Get-Disk | Select-Object Number,FriendlyName,SerialNumber,Model,Size,PartitionStyle,
    IsBoot,IsSystem,PhysicalSectorSize | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            disks = json.loads(output)
            disks = disks if isinstance(disks, list) else [disks]
            
            for disk in disks:
                size_gb = disk.get('Size', 0)
                if isinstance(size_gb, (int, float)):
                    disk['SizeGB'] = round(size_gb / (1024**3), 2)
            
            return disks
        except json.JSONDecodeError:
            return []
    return []


def get_partitions():
    """
    获取分区信息
    
    Returns:
        list: 分区列表
    """
    ps_command = '''
    Get-Partition | Select-Object DiskNumber,PartitionNumber,DriveLetter,Size,Offset,
    Type,OperationalStatus | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            partitions = json.loads(output)
            partitions = partitions if isinstance(partitions, list) else [partitions]
            
            for part in partitions:
                size_gb = part.get('Size', 0)
                if isinstance(size_gb, (int, float)):
                    part['SizeGB'] = round(size_gb / (1024**3), 2)
            
            return partitions
        except json.JSONDecodeError:
            return []
    return []


def get_volumes():
    """
    获取卷信息
    
    Returns:
        list: 卷列表
    """
    ps_command = '''
    Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,SizeRemaining,Size,
    DriveType,HealthStatus | ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            volumes = json.loads(output)
            volumes = volumes if isinstance(volumes, list) else [volumes]
            
            for vol in volumes:
                size_gb = vol.get('Size', 0)
                free_gb = vol.get('SizeRemaining', 0)
                if isinstance(size_gb, (int, float)):
                    vol['SizeGB'] = round(size_gb / (1024**3), 2)
                if isinstance(free_gb, (int, float)):
                    vol['FreeGB'] = round(free_gb / (1024**3), 2)
                    vol['UsedGB'] = vol.get('SizeGB', 0) - vol.get('FreeGB', 0)
                    used_percent = 0
                    if vol.get('SizeGB', 0) > 0:
                        used_percent = round(vol['UsedGB'] / vol['SizeGB'] * 100, 1)
                    vol['UsedPercent'] = used_percent
            
            return volumes
        except json.JSONDecodeError):
            return []
    return []


def get_drive_info(drive_letter):
    """
    获取指定驱动器的详细信息
    
    Args:
        drive_letter: 驱动器字母
        
    Returns:
        dict: 驱动器信息
    """
    ps_command = f'''
    Get-Volume -DriveLetter "{drive_letter}" | 
    Select-Object DriveLetter,FileSystemLabel,FileSystem,SizeRemaining,Size,
    DriveType,HealthStatus,ObjectId | ConvertTo-Json -Depth 3
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            vol = json.loads(output)
            
            size_gb = vol.get('Size', 0)
            free_gb = vol.get('SizeRemaining', 0)
            if isinstance(size_gb, (int, float)):
                vol['SizeGB'] = round(size_gb / (1024**3), 2)
            if isinstance(free_gb, (int, float)):
                vol['FreeGB'] = round(free_gb / (1024**3), 2)
                vol['UsedGB'] = vol.get('SizeGB', 0) - vol.get('FreeGB', 0)
                used_percent = 0
                if vol.get('SizeGB', 0) > 0:
                    used_percent = round(vol['UsedGB'] / vol['SizeGB'] * 100, 1)
                vol['UsedPercent'] = used_percent
            
            return vol
        except json.JSONDecodeError:
            return None
    return None


def get_directory_size(path):
    """
    获取目录大小
    
    Args:
        path: 目录路径
        
    Returns:
        dict: 目录大小信息
    """
    try:
        p = Path(path)
        if not p.exists() or not p.is_dir():
            return None
        
        total_size = 0
        file_count = 0
        dir_count = 0
        
        for item in p.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
            elif item.is_dir():
                dir_count += 1
        
        return {
            'path': str(p.absolute()),
            'size_bytes': total_size,
            'size_human': format_size(total_size),
            'size_gb': round(total_size / (1024**3), 2),
            'size_mb': round(total_size / (1024**2), 2),
            'file_count': file_count,
            'dir_count': dir_count
        }
    except Exception as e:
        return None


def format_size(size_bytes):
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节大小
        
    Returns:
        str: 格式化后的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f'{size_bytes:.2f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.2f} PB'


def get_disk_health(disk_number):
    """
    获取磁盘健康状态
    
    Args:
        disk_number: 磁盘编号
        
    Returns:
        dict: 磁盘健康信息
    """
    ps_command = f'''
    Get-Disk -Number {disk_number} | 
    Select-Object Number,FriendlyName,HealthStatus,OperationalStatus,IsOffline,IsReadOnly | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None


def format_disk_list(disks, partitions, volumes):
    """
    格式化磁盘列表输出
    
    Returns:
        str: 格式化后的输出
    """
    lines = []
    lines.append('=' * 70)
    lines.append('Windows 磁盘管理')
    lines.append('=' * 70)
    lines.append('')
    
    # 物理磁盘
    if disks:
        lines.append('─' * 70)
        lines.append('💿 物理磁盘')
        lines.append('─' * 70)
        lines.append(f'{'磁盘号':<8} {'型号':<35} {'容量(GB)':<12} {'状态':<15}')
        lines.append('-' * 70)
        
        for disk in disks:
            number = disk.get('Number', 'N/A')
            model = (disk.get('Model') or disk.get('FriendlyName', 'N/A'))[:33]
            size_gb = disk.get('SizeGB', 0)
            health = disk.get('HealthStatus', 'N/A')
            
            lines.append(f'{number:<8} {model:<35} {size_gb:<12} {health:<15}')
        
        lines.append('')
    
    # 卷信息
    if volumes:
        lines.append('─' * 70)
        lines.append('📁 驱动器卷')
        lines.append('─' * 70)
        lines.append(f'{'盘符':<8} {'卷标':<15} {'文件系统':<10} {'已用':<12} {'可用':<12} {'使用率':<10}')
        lines.append('-' * 70)
        
        for vol in volumes:
            drive_letter = vol.get('DriveLetter', 'N/A')
            if not drive_letter:
                continue
            label = vol.get('FileSystemLabel', ' ')[:13]
            fs = vol.get('FileSystem', 'N/A')
            used_gb = vol.get('UsedGB', 0)
            free_gb = vol.get('FreeGB', 0)
            percent = vol.get('UsedPercent', 0)
            
            bar_length = 15
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            lines.append(f'{drive_letter}:       {label:<15} {fs:<10} {used_gb:.1f} GB    {free_gb:.1f} GB    [{bar}] {percent}%')
        
        lines.append('')
    
    # 分区表
    if partitions:
        lines.append('─' * 70)
        lines.append('📊 分区表')
        lines.append('─' * 70)
        lines.append(f'{'磁盘号':<8} {'分区号':<10} {'盘符':<8} {'容量(GB)':<12} {'类型':<20}')
        lines.append('-' * 70)
        
        for part in partitions:
            disk_num = part.get('DiskNumber', 'N/A')
            part_num = part.get('PartitionNumber', 'N/A')
            drive = f'{part.get("DriveLetter", "N/A")}:' if part.get('DriveLetter') else 'N/A'
            size_gb = part.get('SizeGB', 0)
            part_type = part.get('Type', 'N/A')[:18]
            
            lines.append(f'{disk_num:<8} {part_num:<10} {drive:<8} {size_gb:<12} {part_type:<20}')
        
        lines.append('')
    
    lines.append('=' * 70)
    
    return '\n'.join(lines)


def format_directory_size(dir_info):
    """
    格式化目录大小输出
    
    Args:
        dir_info: 目录大小信息
        
    Returns:
        str: 格式化后的输出
    """
    if not dir_info:
        return '无法获取目录大小'
    
    lines = []
    lines.append('=' * 60)
    lines.append('目录大小分析')
    lines.append('=' * 60)
    lines.append(f'路径: {dir_info["path"]}')
    lines.append(f'总大小: {dir_info["size_human"]} ({dir_info["size_gb"]:.2f} GB)')
    lines.append(f'文件数: {dir_info["file_count"]}')
    lines.append(f'目录数: {dir_info["dir_count"]}')
    lines.append('=' * 60)
    
    return '\n'.join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Windows 磁盘管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # all 命令
    subparsers.add_parser('all', help='显示所有磁盘信息')
    
    # list 命令
    subparsers.add_parser('list', help='列出磁盘和分区')
    
    # volumes 命令
    subparsers.add_parser('volumes', help='显示驱动器卷信息')
    
    # disks 命令
    subparsers.add_parser('disks', help='显示物理磁盘信息')
    
    # info 命令
    parser_info = subparsers.add_parser('info', help='查看驱动器详细信息')
    parser_info.add_argument('drive', help='驱动器字母 (如 C)')
    
    # size 命令
    parser_size = subparsers.add_parser('size', help='计算目录大小')
    parser_size.add_argument('path', help='目录路径')
    
    # health 命令
    parser_health = subparsers.add_parser('health', help='检查磁盘健康状态')
    parser_health.add_argument('disk_number', type=int, help='磁盘编号')
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == 'all' or args.command == 'list':
        disks = get_physical_disks()
        partitions = get_partitions()
        volumes = get_volumes()
        print(format_disk_list(disks, partitions, volumes))
    
    elif args.command == 'volumes':
        volumes = get_volumes()
        if volumes:
            print(f'{'盘符':<8} {'卷标':<15} {'文件系统':<10} {'总容量':<12} {'已用':<10} {'可用':<10}')
            print('-' * 70)
            for vol in volumes:
                drive = f'{vol.get("DriveLetter", "N/A")}:' if vol.get('DriveLetter') else 'N/A'
                label = vol.get('FileSystemLabel', '')[:13]
                fs = vol.get('FileSystem', 'N/A')
                total = vol.get('SizeGB', 0)
                used = vol.get('UsedGB', 0)
                free = vol.get('FreeGB', 0)
                print(f'{drive:<8} {label:<15} {fs:<10} {total:.1f} GB     {used:.1f} GB   {free:.1f} GB')
        else:
            print('未找到卷信息')
    
    elif args.command == 'disks':
        disks = get_physical_disks()
        if disks:
            print(f'{'磁盘号':<8} {'型号':<40} {'容量(GB)':<12}')
            print('-' * 70)
            for disk in disks:
                number = disk.get('Number', 'N/A')
                model = (disk.get('Model') or disk.get('FriendlyName', 'N/A'))[:38]
                size_gb = disk.get('SizeGB', 0)
                print(f'{number:<8} {model:<40} {size_gb:<12}')
        else:
            print('未找到物理磁盘')
    
    elif args.command == 'info':
        vol = get_drive_info(args.drive.upper())
        if vol:
            print(f'驱动器: {vol.get("DriveLetter", "N/A")}:')
            print(f'卷标: {vol.get("FileSystemLabel", "(无)")}')
            print(f'文件系统: {vol.get("FileSystem", "N/A")}')
            print(f'总容量: {vol.get("SizeGB", 0)} GB')
            print(f'已用空间: {vol.get("UsedGB", 0):.1f} GB')
            print(f'可用空间: {vol.get("FreeGB", 0):.1f} GB')
            print(f'使用率: {vol.get("UsedPercent", 0)}%')
            print(f'驱动器类型: {vol.get("DriveType", "N/A")}')
            print(f'健康状态: {vol.get("HealthStatus", "N/A")}')
        else:
            print(f'未找到驱动器 {args.drive}:')
    
    elif args.command == 'size':
        dir_info = get_directory_size(args.path)
        if dir_info:
            print(format_directory_size(dir_info))
        else:
            print(f'无法访问路径: {args.path}')
    
    elif args.command == 'health':
        health = get_disk_health(args.disk_number)
        if health:
            print(f'磁盘号: {health.get("Number", "N/A")}')
            print(f'型号: {health.get("FriendlyName", "N/A")}')
            print(f'健康状态: {health.get("HealthStatus", "N/A")}')
            print(f'运行状态: {health.get("OperationalStatus", "N/A")}')
            print(f'离线状态: {"是" if health.get("IsOffline") else "否"}')
            print(f'只读状态: {"是" if health.get("IsReadOnly") else "否"}')
        else:
            print(f'未找到磁盘 {args.disk_number}')
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
