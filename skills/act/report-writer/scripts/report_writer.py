#!/usr/bin/env python3
"""
Report Writer Skill for Ruyi72
综合报告生成技能，整合系统信息生成 Markdown 报告
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
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


def get_cpu_info():
    """获取 CPU 信息"""
    ps_command = '''
    Get-CimInstance Win32_Processor | 
    Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,LoadPercentage | 
    ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            cpu = json.loads(output)
            return cpu if isinstance(cpu, list) else cpu
        except json.JSONDecodeError:
            pass
    return None


def get_memory_info():
    """获取内存信息"""
    ps_command = '''
    Get-CimInstance Win32_OperatingSystem | 
    Select-Object TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,FreeVirtualMemory | 
    ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            mem = json.loads(output)
            if isinstance(mem, list):
                mem = mem[0]
            total = int(mem.get('TotalVisibleMemorySize', 0)) / 1024
            free = int(mem.get('FreePhysicalMemory', 0)) / 1024
            mem['TotalMB'] = round(total, 2)
            mem['FreeMB'] = round(free, 2)
            mem['UsedMB'] = round(total - free, 2)
            mem['Percent'] = round((total - free) / total * 100, 1) if total > 0 else 0
            return mem
        except json.JSONDecodeError:
            pass
    return None


def get_disk_info():
    """获取磁盘信息"""
    ps_command = '''
    Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | 
    Select-Object DeviceID,VolumeName,Size,FreeSpace | ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            disks = json.loads(output)
            disks = disks if isinstance(disks, list) else [disks]
            for disk in disks:
                size_gb = disk.get('Size', 0) / (1024**3)
                free_gb = disk.get('FreeSpace', 0) / (1024**3)
                disk['SizeGB'] = round(size_gb, 2)
                disk['FreeGB'] = round(free_gb, 2)
                disk['UsedGB'] = round(size_gb - free_gb, 2)
                disk['Percent'] = round((size_gb - free_gb) / size_gb * 100, 1) if size_gb > 0 else 0
            return disks
        except json.JSONDecodeError:
            pass
    return []


def get_network_info():
    """获取网络信息"""
    ps_command = '''
    Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | 
    Select-Object Name,InterfaceDescription,Speed,MacAddress | ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            adapters = json.loads(output)
            adapters = adapters if isinstance(adapters, list) else [adapters]
            for adapter in adapters:
                speed = adapter.get('Speed', 0)
                if speed >= 10**9:
                    adapter['SpeedText'] = f'{round(speed / 10**9, 2)} Gbps'
                elif speed >= 10**6:
                    adapter['SpeedText'] = f'{round(speed / 10**6, 2)} Mbps'
                else:
                    adapter['SpeedText'] = f'{speed} Kbps'
            return adapters
        except json.JSONDecodeError:
            pass
    return []


def get_system_info():
    """获取系统信息"""
    ps_command = '''
    Get-CimInstance Win32_OperatingSystem | 
    Select-Object CSName,Caption,Version,OSArchitecture,RegisteredUser,LastBootUpTime | 
    ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            sysinfo = json.loads(output)
            if isinstance(sysinfo, list):
                sysinfo = sysinfo[0]
            boot_time = sysinfo.get('LastBootUpTime')
            if boot_time and isinstance(boot_time, str):
                try:
                    dt = datetime.fromisoformat(boot_time.replace('Z', '+00:00'))
                    sysinfo['Uptime'] = str(datetime.now() - dt).split('.')[0]
                except:
                    pass
            return sysinfo
        except json.JSONDecodeError:
            pass
    return None


def get_processes(top_n=20, by='cpu'):
    """获取进程列表"""
    ps_command = f'''
    Get-Process | Sort-Object -Property {"CPU" if by == "cpu" else "WorkingSet64"} -Descending | 
    Select-Object -First {top_n} Id,ProcessName,CPU,WorkingSet64 | ConvertTo-Json -Depth 2
    '''
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            processes = json.loads(output)
            processes = processes if isinstance(processes, list) else [processes]
            for p in processes:
                p['MemoryMB'] = round(p.get('WorkingSet64', 0) / (1024**2), 2)
            return processes
        except json.JSONDecodeError:
            pass
    return []


def get_services(status=None):
    """获取服务列表"""
    if status == 'running':
        ps_command = 'Get-Service | Where-Object {$_.Status -eq "Running"} | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    elif status == 'stopped':
        ps_command = 'Get-Service | Where-Object {$_.Status -eq "Stopped"} | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    else:
        ps_command = 'Get-Service | Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2'
    
    success, output, _ = run_powershell(ps_command)
    if success and output:
        try:
            services = json.loads(output)
            return services if isinstance(services, list) else [services]
        except json.JSONDecodeError:
            pass
    return []


def generate_system_report(title='系统状态报告'):
    """生成系统状态综合报告"""
    cpu = get_cpu_info()
    memory = get_memory_info()
    disks = get_disk_info()
    network = get_network_info()
    sysinfo = get_system_info()
    processes = get_processes(15, 'cpu')
    
    report = []
    report.append('# ' + title)
    report.append('')
    report.append(f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    report.append('')
    report.append('---')
    report.append('')
    
    # 系统信息
    if sysinfo:
        report.append('## 系统信息')
        report.append('')
        report.append(f'- **计算机名称**: {sysinfo.get("CSName", "N/A")}')
        report.append(f'- **操作系统**: {sysinfo.get("Caption", "N/A")}')
        report.append(f'- **版本**: {sysinfo.get("Version", "N/A")}')
        report.append(f'- **架构**: {sysinfo.get("OSArchitecture", "N/A")}')
        report.append(f'- **运行时长**: {sysinfo.get("Uptime", "N/A")}')
        report.append('')
    
    # CPU 信息
    if cpu:
        report.append('## CPU 信息')
        report.append('')
        report.append(f'- **处理器**: {cpu.get("Name", "N/A")}')
        report.append(f'- **核心数**: {cpu.get("NumberOfCores", "N/A")} 核 / {cpu.get("NumberOfLogicalProcessors", "N/A")} 线程')
        report.append(f'- **主频**: {cpu.get("MaxClockSpeed", "N/A")} MHz')
        report.append(f'- **当前负载**: {cpu.get("LoadPercentage", "N/A")}%')
        report.append('')
    
    # 内存信息
    if memory:
        report.append('## 内存信息')
        report.append('')
        report.append(f'- **物理内存**: {memory.get("UsedMB", 0):.0f} MB / {memory.get("TotalMB", 0):.0f} MB ({memory.get("Percent", 0)}%)')
        report.append(f'- **可用内存**: {memory.get("FreeMB", 0):.0f} MB')
        report.append('')
    
    # 磁盘信息
    if disks:
        report.append('## 磁盘信息')
        report.append('')
        report.append('| 盘符 | 卷标 | 总容量 | 已用 | 可用 | 使用率 |')
        report.append('|------|------|--------|------|------|--------|')
        for disk in disks:
            drive = disk.get('DeviceID', 'N/A')
            label = disk.get('VolumeName', '')
            total = disk.get('SizeGB', 0)
            used = disk.get('UsedGB', 0)
            free = disk.get('FreeGB', 0)
            percent = disk.get('Percent', 0)
            report.append(f'| {drive} | {label} | {total:.1f} GB | {used:.1f} GB | {free:.1f} GB | {percent}% |')
        report.append('')
    
    # 网络信息
    if network:
        report.append('## 网络信息')
        report.append('')
        for adapter in network:
            name = adapter.get('Name', 'N/A')
            desc = adapter.get('InterfaceDescription', 'N/A')
            speed = adapter.get('SpeedText', 'N/A')
            mac = adapter.get('MacAddress', 'N/A')
            report.append(f'- **{name}**: {desc}')
            report.append(f'  - 速度: {speed}')
            report.append(f'  - MAC: {mac}')
        report.append('')
    
    # 进程信息
    if processes:
        report.append('## CPU 占用 Top 15')
        report.append('')
        report.append('| PID | 进程名 | CPU | 内存(MB) |')
        report.append('|-----|--------|-----|----------|')
        for p in processes:
            pid = p.get('Id', 'N/A')
            name = p.get('ProcessName', 'N/A')
            cpu_val = p.get('CPU', '0')
            mem = p.get('MemoryMB', 0)
            report.append(f'| {pid} | {name} | {cpu_val} | {mem:.1f} |')
        report.append('')
    
    report.append('---')
    report.append('')
    report.append('*报告由 如意72 自动生成*')
    
    return '\n'.join(report)


def generate_process_report(top_n=30, by='memory'):
    """生成进程分析报告"""
    processes = get_processes(top_n, by)
    
    report = []
    report.append('# 进程分析报告')
    report.append('')
    report.append(f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    report.append(f'**排序方式**: 按 {by} 降序')
    report.append(f'**进程数量**: {len(processes)}')
    report.append('')
    report.append('---')
    report.append('')
    report.append('## 进程列表')
    report.append('')
    report.append('| 排名 | PID | 进程名 | CPU | 内存(MB) |')
    report.append('|------|-----|--------|-----|----------|')
    
    for i, p in enumerate(processes, 1):
        pid = p.get('Id', 'N/A')
        name = p.get('ProcessName', 'N/A')
        cpu_val = p.get('CPU', '0')
        mem = p.get('MemoryMB', 0)
        report.append(f'| {i} | {pid} | {name} | {cpu_val} | {mem:.1f} |')
    
    report.append('')
    report.append('---')
    report.append('')
    report.append('*报告由 如意72 自动生成*')
    
    return '\n'.join(report)


def generate_service_report(status_filter=None):
    """生成服务状态报告"""
    all_services = get_services('all')
    running = [s for s in all_services if s.get('Status') == 'Running']
    stopped = [s for s in all_services if s.get('Status') == 'Stopped']
    
    report = []
    report.append('# 服务状态报告')
    report.append('')
    report.append(f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    report.append(f'**总计**: {len(all_services)} 个服务')
    report.append(f'**运行中**: {len(running)} 个')
    report.append(f'**已停止**: {len(stopped)} 个')
    report.append('')
    report.append('---')
    report.append('')
    
    if status_filter in [None, 'running']:
        report.append('## 运行中的服务')
        report.append('')
        if running:
            report.append('| 服务名 | 显示名称 |')
            report.append('|--------|----------|')
            for s in running:
                name = s.get('Name', 'N/A')
                display = s.get('DisplayName', 'N/A')
                report.append(f'| {name} | {display} |')
        else:
            report.append('无运行中的服务')
        report.append('')
    
    if status_filter in [None, 'stopped']:
        report.append('## 已停止的服务')
        report.append('')
        if stopped:
            report.append('| 服务名 | 显示名称 |')
            report.append('|--------|----------|')
            for s in stopped[:50]:  # 限制数量
                name = s.get('Name', 'N/A')
                display = s.get('DisplayName', 'N/A')
                report.append(f'| {name} | {display} |')
            if len(stopped) > 50:
                report.append(f'| ... | 还有 {len(stopped) - 50} 个服务 |')
        else:
            report.append('无已停止的服务')
        report.append('')
    
    report.append('---')
    report.append('')
    report.append('*报告由 如意72 自动生成*')
    
    return '\n'.join(report)


def save_report(content, output_path):
    """
    保存报告到文件
    
    Args:
        content: 报告内容
        output_path: 输出文件路径
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return True, str(path.absolute())
    except Exception as e:
        return False, f'保存失败: {str(e)}'


def format_save_result(saved_path, content_length):
    """格式化保存结果"""
    return f'''
✅ 报告生成成功！

📄 文件路径: {saved_path}
📏 内容长度: {content_length} 字符
'''


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='报告生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # system 命令
    parser_system = subparsers.add_parser('system', help='生成系统状态报告')
    parser_system.add_argument('--title', default='系统状态报告', help='报告标题')
    parser_system.add_argument('--output', '-o', help='输出文件路径')
    
    # process 命令
    parser_process = subparsers.add_parser('process', help='生成进程分析报告')
    parser_process.add_argument('--top', type=int, default=30, help='进程数量')
    parser_process.add_argument('--by', choices=['cpu', 'memory'], default='memory', help='排序依据')
    parser_process.add_argument('--output', '-o', help='输出文件路径')
    
    # service 命令
    parser_service = subparsers.add_parser('service', help='生成服务状态报告')
    parser_service.add_argument('--status', choices=['all', 'running', 'stopped'], default='all',
                               help='服务状态过滤')
    parser_service.add_argument('--output', '-o', help='输出文件路径')
    
    # custom 命令
    parser_custom = subparsers.add_parser('custom', help='生成自定义报告')
    parser_custom.add_argument('--title', required=True, help='报告标题')
    parser_custom.add_argument('--content', required=True, help='报告内容 (JSON 格式)')
    parser_custom.add_argument('--output', '-o', required=True, help='输出文件路径')
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == 'system':
        report = generate_system_report(args.title)
        if args.output:
            success, message = save_report(report, args.output)
            if success:
                print(format_save_result(message, len(report)))
            else:
                print(f'❌ {message}')
        else:
            print(report)
    
    elif args.command == 'process':
        report = generate_process_report(args.top, args.by)
        if args.output:
            success, message = save_report(report, args.output)
            if success:
                print(format_save_result(message, len(report)))
            else:
                print(f'❌ {message}')
        else:
            print(report)
    
    elif args.command == 'service':
        report = generate_service_report(args.status)
        if args.output:
            success, message = save_report(report, args.output)
            if success:
                print(format_save_result(message, len(report)))
            else:
                print(f'❌ {message}')
        else:
            print(report)
    
    elif args.command == 'custom':
        try:
            content_dict = json.loads(args.content)
            report = ['# ' + args.title, '', f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', '']
            report.append('---')
            report.append('')
            
            for key, value in content_dict.items():
                report.append(f'## {key}')
                report.append('')
                if isinstance(value, list):
                    for item in value:
                        report.append(f'- {item}')
                else:
                    report.append(str(value))
                report.append('')
            
            report.append('---')
            report.append('')
            report.append('*报告由 如意72 自动生成*')
            
            final_report = '\n'.join(report)
            success, message = save_report(final_report, args.output)
            if success:
                print(format_save_result(message, len(final_report)))
            else:
                print(f'❌ {message}')
        except json.JSONDecodeError as e:
            print(f'❌ JSON 解析错误: {e}')
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
