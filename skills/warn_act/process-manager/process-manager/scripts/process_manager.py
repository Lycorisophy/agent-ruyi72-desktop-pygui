#!/usr/bin/env python3
"""
Process Manager Skill for Ruyi72
Windows 进程管理技能，支持进程查看和控制
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


def list_processes(sort_by='name', top_n=None):
    """
    获取进程列表
    
    Args:
        sort_by: 排序字段 (name, cpu, memory, pid)
        top_n: 返回前 N 个进程
        
    Returns:
        list: 进程列表
    """
    ps_command = '''
    Get-Process | Select-Object Id,ProcessName,CPU,WorkingSet64,StartTime,Handles | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if not success or not output:
        return []
    
    try:
        processes = json.loads(output)
        processes = processes if isinstance(processes, list) else [processes]
        
        # 转换内存单位
        for p in processes:
            ws = p.get('WorkingSet64', 0)
            p['MemoryMB'] = round(ws / (1024 * 1024), 2)
        
        # 排序
        if sort_by == 'cpu':
            processes.sort(key=lambda x: float(x.get('CPU', 0)), reverse=True)
        elif sort_by == 'memory':
            processes.sort(key=lambda x: x.get('MemoryMB', 0), reverse=True)
        elif sort_by == 'pid':
            processes.sort(key=lambda x: x.get('Id', 0))
        
        # 限制数量
        if top_n:
            processes = processes[:top_n]
        
        return processes
    except json.JSONDecodeError:
        return []


def get_process_by_name(process_name):
    """
    按名称查找进程
    
    Args:
        process_name: 进程名称
        
    Returns:
        list: 匹配的进程列表
    """
    ps_command = f'''
    Get-Process -Name "{process_name}" | 
    Select-Object Id,ProcessName,CPU,WorkingSet64,StartTime,Handles,Path,Description | 
    ConvertTo-Json -Depth 2
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            processes = json.loads(output)
            return processes if isinstance(processes, list) else [processes]
        except json.JSONDecodeError:
            return []
    return []


def get_process_by_id(pid):
    """
    按 PID 获取进程详情
    
    Args:
        pid: 进程 ID
        
    Returns:
        dict: 进程详情
    """
    ps_command = f'''
    Get-Process -Id {pid} | 
    Select-Object Id,ProcessName,CPU,WorkingSet64,StartTime,Handles,Path,Description, 
    MainModule,Modules | ConvertTo-Json -Depth 3
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None


def kill_process_by_name(process_name, force=False):
    """
    按名称结束进程
    
    Args:
        process_name: 进程名称
        force: 是否强制结束
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if force:
        ps_command = f'Stop-Process -Name "{process_name}" -Force -PassThru | ConvertTo-Json'
    else:
        ps_command = f'Stop-Process -Name "{process_name}" -PassThru | ConvertTo-Json'
    
    success, output, error = run_powershell(ps_command)
    
    if success:
        return True, f'进程 "{process_name}" 已结束'
    else:
        return False, f'结束进程失败: {error}'


def kill_process_by_id(pid, force=False):
    """
    按 PID 结束进程
    
    Args:
        pid: 进程 ID
        force: 是否强制结束
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if force:
        ps_command = f'Stop-Process -Id {pid} -Force -PassThru | ConvertTo-Json'
    else:
        ps_command = f'Stop-Process -Id {pid} -PassThru | ConvertTo-Json'
    
    success, output, error = run_powershell(ps_command)
    
    if success:
        return True, f'进程 (PID: {pid}) 已结束'
    else:
        return False, f'结束进程失败: {error}'


def get_process_tree():
    """
    获取进程树
    
    Returns:
        list: 进程树结构
    """
    ps_command = '''
    Get-Process | ForEach-Object {
        $proc = $_
        $parentId = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).ParentProcessId
        [PSCustomObject]@{
            Id = $proc.Id
            ProcessName = $proc.ProcessName
            ParentId = $parentId
            CPU = $proc.CPU
            WorkingSet64 = $proc.WorkingSet64
        }
    } | ConvertTo-Json -Depth 3
    '''
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            processes = json.loads(output)
            return processes if isinstance(processes, list) else [processes]
        except json.JSONDecodeError:
            return []
    return []


def format_process_list(processes, title='进程列表'):
    """
    格式化进程列表输出
    
    Args:
        processes: 进程列表
        title: 标题
        
    Returns:
        str: 格式化后的输出
    """
    if not processes:
        return '未找到进程'
    
    lines = []
    lines.append('=' * 80)
    lines.append(title)
    lines.append('=' * 80)
    lines.append(f'{'PID':<8} {'进程名':<25} {'CPU':<12} {'内存(MB)':<12} {'启动时间':<20}')
    lines.append('-' * 80)
    
    for proc in processes:
        pid = proc.get('Id', 'N/A')
        name = proc.get('ProcessName', 'N/A')[:23]
        cpu = proc.get('CPU', '0')
        memory = proc.get('MemoryMB', 0)
        start_time = proc.get('StartTime', 'N/A')
        if isinstance(start_time, dict):
            start_time = 'N/A'
        elif start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                start_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                start_time = str(start_time)[:19]
        
        lines.append(f'{pid:<8} {name:<25} {cpu:<12} {memory:<12} {start_time:<20}')
    
    lines.append('=' * 80)
    lines.append(f'共 {len(processes)} 个进程')
    
    return '\n'.join(lines)


def format_process_detail(process):
    """
    格式化进程详情输出
    
    Args:
        process: 进程详情
        
    Returns:
        str: 格式化后的输出
    """
    if not process:
        return '未找到进程'
    
    lines = []
    lines.append('=' * 60)
    lines.append('进程详情')
    lines.append('=' * 60)
    
    lines.append(f'进程 ID (PID): {process.get("Id", "N/A")}')
    lines.append(f'进程名称: {process.get("ProcessName", "N/A")}')
    lines.append(f'CPU 使用: {process.get("CPU", "N/A")}')
    lines.append(f'内存使用: {round(process.get("WorkingSet64", 0) / (1024 * 1024), 2) if process.get("WorkingSet64") else "N/A"} MB')
    lines.append(f'句柄数: {process.get("Handles", "N/A")}')
    lines.append(f'启动时间: {process.get("StartTime", "N/A")}')
    lines.append(f'进程路径: {process.get("Path", "N/A")}')
    lines.append(f'描述: {process.get("Description", "N/A")}')
    
    lines.append('=' * 60)
    
    return '\n'.join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Windows 进程管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    parser_list = subparsers.add_parser('list', help='列出进程')
    parser_list.add_argument('--sort', choices=['name', 'cpu', 'memory', 'pid'], default='name',
                             help='排序字段')
    parser_list.add_argument('--top', type=int, help='只显示前 N 个进程')
    
    # find 命令
    parser_find = subparsers.add_parser('find', help='查找进程')
    parser_find.add_argument('process_name', help='进程名称')
    
    # detail 命令
    parser_detail = subparsers.add_parser('detail', help='查看进程详情')
    parser_detail.add_argument('pid', type=int, help='进程 ID')
    
    # kill 命令
    parser_kill = subparsers.add_parser('kill', help='结束进程')
    parser_kill.add_argument('target', help='进程名称或 PID')
    parser_kill.add_argument('--type', choices=['name', 'pid'], default='name',
                             help='目标类型')
    parser_kill.add_argument('--force', action='store_true', help='强制结束')
    
    # top 命令
    parser_top = subparsers.add_parser('top', help='显示资源占用最高的进程')
    parser_top.add_argument('--count', type=int, default=10, help='显示数量')
    parser_top.add_argument('--by', choices=['cpu', 'memory'], default='cpu',
                            help='排序依据')
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == 'list':
        processes = list_processes(args.sort, args.top)
        print(format_process_list(processes))
    
    elif args.command == 'find':
        processes = get_process_by_name(args.process_name)
        if processes:
            print(format_process_list(processes, f'进程 "{args.process_name}" 的搜索结果'))
        else:
            print(f'未找到进程: {args.process_name}')
    
    elif args.command == 'detail':
        process = get_process_by_id(args.pid)
        if process:
            print(format_process_detail(process))
        else:
            print(f'未找到进程 (PID: {args.pid})')
    
    elif args.command == 'kill':
        if args.type == 'name':
            success, message = kill_process_by_name(args.target, args.force)
        else:
            try:
                pid = int(args.target)
                success, message = kill_process_by_id(pid, args.force)
            except ValueError:
                print(f'无效的 PID: {args.target}')
                return
        
        if success:
            print(f'✅ {message}')
        else:
            print(f'❌ {message}')
    
    elif args.command == 'top':
        processes = list_processes(args.by)
        processes = processes[:args.count]
        print(format_process_list(processes, f'资源占用 Top {args.count} ({args.by})'))
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
