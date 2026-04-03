#!/usr/bin/env python3
"""
Service Manager Skill for OpenClaw
Windows 服务管理技能，支持服务操作和定时任务管理
支持 OpenClaw 技能系统调用
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime


def run_powershell(command):
    """
    执行 PowerShell 命令并返回结果
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


def list_services(status_filter=None):
    """获取服务列表"""
    if status_filter and status_filter.lower() == 'running':
        ps_command = 'Get-Service | Where-Object {$_.Status -eq "Running"} | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    elif status_filter and status_filter.lower() == 'stopped':
        ps_command = 'Get-Service | Where-Object {$_.Status -eq "Stopped"} | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    else:
        ps_command = 'Get-Service | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    
    success, output, error = run_powershell(ps_command)
    
    if not success or not output:
        return []
    
    try:
        services = json.loads(output)
        return services if isinstance(services, list) else [services]
    except json.JSONDecodeError:
        return []


def get_service_status(service_name):
    """获取单个服务状态"""
    ps_command = f'Get-Service -Name "{service_name}" | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json -Depth 2'
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None


def start_service(service_name):
    """启动服务"""
    ps_command = f'Start-Service -Name "{service_name}" -PassThru'
    success, output, error = run_powershell(ps_command)
    
    if success:
        return True, f'服务 "{service_name}" 已启动'
    else:
        return False, f'启动服务失败: {error}'


def stop_service(service_name):
    """停止服务"""
    ps_command = f'Stop-Service -Name "{service_name}" -PassThru'
    success, output, error = run_powershell(ps_command)
    
    if success:
        return True, f'服务 "{service_name}" 已停止'
    else:
        return False, f'停止服务失败: {error}'


def restart_service(service_name):
    """重启服务"""
    ps_command = f'Restart-Service -Name "{service_name}" -PassThru'
    success, output, error = run_powershell(ps_command)
    
    if success:
        return True, f'服务 "{service_name}" 已重启'
    else:
        return False, f'重启服务失败: {error}'


def create_scheduled_task(task_name, command, schedule='daily', time='01:00'):
    """
    创建定时任务 - Windows schtasks
    
    Args:
        task_name: 任务名称（英文，避免编码问题）
        command: 要执行的命令
        schedule: 调度频率 (daily, weekly, hourly, once)
        time: 执行时间 (HH:MM 格式)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # 使用 schtasks 创建定时任务
    if schedule == 'daily':
        schtasks_cmd = f'schtasks /create /tn "{task_name}" /tr "{command}" /sc daily /st {time} /f'
    elif schedule == 'weekly':
        schtasks_cmd = f'schtasks /create /tn "{task_name}" /tr "{command}" /sc weekly /st {time} /d MON /f'
    elif schedule == 'hourly':
        schtasks_cmd = f'schtasks /create /tn "{task_name}" /tr "{command}" /sc hourly /st {time} /f'
    elif schedule == 'once':
        schtasks_cmd = f'schtasks /create /tn "{task_name}" /tr "{command}" /sc once /st {time} /f'
    else:
        schtasks_cmd = f'schtasks /create /tn "{task_name}" /tr "{command}" /sc daily /st {time} /f'
    
    success, output, error = run_powershell(schtasks_cmd)
    
    if success:
        return True, f'定时任务 "{task_name}" 已创建 (每天 {time})'
    else:
        return False, f'创建定时任务失败: {error}'


def delete_scheduled_task(task_name):
    """删除定时任务"""
    schtasks_cmd = f'schtasks /delete /tn "{task_name}" /f'
    success, output, error = run_powershell(schtasks_cmd)
    
    if success:
        return True, f'定时任务 "{task_name}" 已删除'
    else:
        return False, f'删除定时任务失败: {error}'


def query_scheduled_tasks():
    """查询所有定时任务"""
    ps_command = 'schtasks /query /fo CSV | ConvertFrom-Csv | ConvertTo-Json -Depth 2'
    success, output, error = run_powershell(ps_command)
    
    if success and output:
        try:
            tasks = json.loads(output)
            return tasks if isinstance(tasks, list) else [tasks]
        except json.JSONDecodeError:
            return []
    return []


def main():
    """
    主函数 - 支持 OpenClaw 技能系统调用
    
    使用方式:
        python service_manager.py list
        python service_manager.py start <service_name>
        python service_manager.py task-create "DailyNews" "powershell ..." --schedule daily --time 01:00
    """
    parser = argparse.ArgumentParser(
        description='Windows 服务管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    parser_list = subparsers.add_parser('list', help='列出服务')
    parser_list.add_argument('--status', choices=['running', 'stopped', 'all'], default='all')
    
    # status 命令
    parser_status = subparsers.add_parser('status', help='查看服务状态')
    parser_status.add_argument('service_name', help='服务名称')
    
    # start 命令
    parser_start = subparsers.add_parser('start', help='启动服务')
    parser_start.add_argument('service_name', help='服务名称')
    
    # stop 命令
    parser_stop = subparsers.add_parser('stop', help='停止服务')
    parser_stop.add_argument('service_name', help='服务名称')
    
    # restart 命令
    parser_restart = subparsers.add_parser('restart', help='重启服务')
    parser_restart.add_argument('service_name', help='服务名称')
    
    # task-create 命令
    parser_task_create = subparsers.add_parser('task-create', help='创建定时任务')
    parser_task_create.add_argument('task_name', help='任务名称（英文）')
    parser_task_create.add_argument('command', help='要执行的命令')
    parser_task_create.add_argument('--schedule', choices=['daily', 'weekly', 'hourly', 'once'],
                                    default='daily', help='调度频率')
    parser_task_create.add_argument('--time', default='01:00', help='执行时间 (HH:MM)')
    
    # task-delete 命令
    parser_task_delete = subparsers.add_parser('task-delete', help='删除定时任务')
    parser_task_delete.add_argument('task_name', help='任务名称')
    
    # task-list 命令
    subparsers.add_parser('task-list', help='列出定时任务')
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == 'list':
        services = list_services(args.status)
        if services:
            print('=' * 70)
            print('Windows 服务列表')
            print('=' * 70)
            print(f"{'服务名称':<30} {'显示名称':<25} {'状态':<10}")
            print('-' * 70)
            for service in services:
                name = service.get('Name', 'N/A')[:28]
                display_name = service.get('DisplayName', 'N/A')[:23]
                status = service.get('Status', 'N/A')
                status_text = '运行中' if status == 'Running' else ('已停止' if status == 'Stopped' else status)
                print(f'{name:<30} {display_name:<25} {status_text:<10}')
            print('=' * 70)
            print(f'共 {len(services)} 个服务')
        else:
            print('未找到服务')
    
    elif args.command == 'status':
        service = get_service_status(args.service_name)
        if service:
            status = service.get('Status', 'N/A')
            status_text = '运行中' if status == 'Running' else ('已停止' if status == 'Stopped' else status)
            print(f'服务名称: {service.get("Name", "N/A")}')
            print(f'显示名称: {service.get("DisplayName", "N/A")}')
            print(f'状态: {status_text}')
            print(f'启动类型: {service.get("StartType", "N/A")}')
        else:
            print(f'未找到服务: {args.service_name}')
    
    elif args.command == 'start':
        success, message = start_service(args.service_name)
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.command == 'stop':
        success, message = stop_service(args.service_name)
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.command == 'restart':
        success, message = restart_service(args.service_name)
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.command == 'task-create':
        success, message = create_scheduled_task(
            args.task_name, args.command, args.schedule, args.time
        )
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.command == 'task-delete':
        success, message = delete_scheduled_task(args.task_name)
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.command == 'task-list':
        tasks = query_scheduled_tasks()
        if tasks:
            print(f'找到 {len(tasks)} 个定时任务')
        else:
            print('未找到定时任务或查询失败')
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
