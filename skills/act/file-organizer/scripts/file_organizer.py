#!/usr/bin/env python3
"""
File Organizer Skill for OpenClaw
Helps organize files and documents in folders
"""

import argparse
import json
import sys
from pathlib import Path
import shutil
import hashlib
from datetime import datetime
import re


# 文件类型分类
FILE_CATEGORIES = {
    'Documents': ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt', '.epub'],
    'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.psd'],
    'Videos': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'],
    'Audio': ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.aiff'],
    'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'],
    'Spreadsheets': ['.xlsx', '.xls', '.csv', '.ods'],
    'Presentations': ['.pptx', '.ppt', '.key', '.odp'],
    'Code': ['.py', '.js', '.ts', '.html', '.css', '.java', '.c', '.cpp', '.h',
             '.json', '.yaml', '.yml', '.xml', '.sql', '.sh', '.bat', '.ps1'],
    'Executables': ['.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.app']
}


def get_file_category(file_path: Path) -> str:
    """获取文件的分类"""
    suffix = file_path.suffix.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if suffix in extensions:
            return category
    return 'Others'


def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def calculate_file_hash(file_path: Path) -> str:
    """计算文件的 MD5 哈希"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def organize_by_type(folder_path: Path, dry_run: bool = True) -> dict:
    """
    按文件类型整理文件夹
    
    Args:
        folder_path: 要整理的文件夹路径
        dry_run: 是否仅模拟运行（不实际执行）
    
    Returns:
        整理结果统计
    """
    results = {
        'total_files': 0,
        'organized': [],
        'errors': [],
        'categories': {}
    }
    
    if not folder_path.exists():
        results['errors'].append(f"文件夹不存在: {folder_path}")
        return results
    
    if not folder_path.is_dir():
        results['errors'].append(f"路径不是文件夹: {folder_path}")
        return results
    
    files = list(folder_path.glob("*"))
    files = [f for f in files if f.is_file()]
    results['total_files'] = len(files)
    
    for file_path in files:
        category = get_file_category(file_path)
        target_folder = folder_path / category
        
        if category not in results['categories']:
            results['categories'][category] = []
        
        results['categories'][category].append({
            'file': file_path.name,
            'size': file_path.stat().st_size
        })
        
        if not dry_run and category != 'Others':
            try:
                target_folder.mkdir(exist_ok=True)
                new_path = target_folder / file_path.name
                
                # 处理文件名冲突
                if new_path.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    counter = 1
                    while new_path.exists():
                        new_path = target_folder / f"{stem}_{counter}{suffix}"
                        counter += 1
                
                shutil.move(str(file_path), str(new_path))
                results['organized'].append({
                    'from': str(file_path),
                    'to': str(new_path),
'category': category
                })
            except Exception as e:
                results['errors'].append(f"移动文件失败 {file_path.name}: {str(e)}")
    
    return results


def find_duplicates(folder_path: Path, by_content: bool = True) -> dict:
    """
    查找重复文件
    
    Args:
        folder_path: 要搜索的文件夹路径
        by_content: 是否按内容检测（True）还是仅按文件名（False）
    
    Returns:
        重复文件组
    """
    duplicates = {}
    file_map = {}
    
    if not folder_path.exists():
        return {'error': f"文件夹不存在: {folder_path}"}
    
    files = list(folder_path.glob("**/*"))
    files = [f for f in files if f.is_file()]
    
    for file_path in files:
        if by_content:
            try:
                file_hash = calculate_file_hash(file_path)
                key = (file_hash, file_path.stat().st_size)
            except Exception:
                continue
        else:
            key = file_path.name.lower()
        
        if key not in file_map:
            file_map[key] = []
        file_map[key].append({
            'path': str(file_path),
            'size': file_path.stat().st_size,
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        })
    
    for key, files_list in file_map.items():
        if len(files_list) > 1:
            duplicates[str(key)] = files_list
    
    return {
        'total_files': len(files),
        'duplicate_groups': len(duplicates),
        'duplicates': duplicates
    }


def rename_files(folder_path: Path, pattern: str, replacement: str, 
                 use_regex: bool = False, dry_run: bool = True) -> dict:
    """
    批量重命名文件
    
    Args:
        folder_path: 目标文件夹
        pattern: 匹配模式
        replacement: 替换内容
        use_regex: 是否使用正则表达式
        dry_run: 是否仅模拟运行
    """
    results = {
        'total': 0,
        'renamed': [],
        'errors': []
    }
    
    if not folder_path.exists():
        results['errors'].append(f"文件夹不存在: {folder_path}")
        return results
    
    files = list(folder_path.glob("*"))
    files = [f for f in files if f.is_file()]
    results['total'] = len(files)
    
    for file_path in files:
        try:
            if use_regex:
                new_name = re.sub(pattern, replacement, file_path.name)
            else:
                new_name = file_path.name.replace(pattern, replacement)
            
            if new_name != file_path.name:
                new_path = file_path.parent / new_name
                
                results['renamed'].append({
                    'from': file_path.name,
                    'to': new_name,
                    'path': str(new_path)
                })
                
                if not dry_run:
                    # 处理文件名冲突
                    if new_path.exists():
                        stem = new_path.stem
                        suffix = new_path.suffix
                        counter = 1
                        while new_path.exists():
                            new_path = file_path.parent / f"{stem}_{counter}{suffix}"
                            counter += 1
                    
                    file_path.rename(new_path)
                    
        except Exception as e:
            results['errors'].append(f"重命名失败 {file_path.name}: {str(e)}")
    
    return results


def create_folder_structure(folder_path: Path, structure: dict) -> dict:
    """
    创建文件夹结构
    
    Args:
        folder_path: 根文件夹路径
        structure: 文件夹结构字典
    
    Returns:
        创建结果
    """
    results = {
        'created': [],
        'errors': []
    }
    
    if not folder_path.exists():
        try:
            folder_path.mkdir(parents=True)
            results['created'].append(str(folder_path))
        except Exception as e:
            results['errors'].append(f"创建根文件夹失败: {str(e)}")
            return results
    
    def create_recursive(current_path, structure):
        for name, content in structure.items():
            new_path = current_path / name
            try:
                new_path.mkdir(exist_ok=True)
                results['created'].append(str(new_path))
            except Exception as e:
                results['errors'].append(f"创建文件夹失败 {name}: {str(e)}")
            
            if isinstance(content, dict):
                create_recursive(new_path, content)
    
    create_recursive(folder_path, structure)
    return results


def format_organize_results(results: dict, dry_run: bool = True) -> str:
    """格式化整理结果"""
    output = []
    
    mode = "模拟运行" if dry_run else "执行"
    output.append(f"📁 文件整理结果 ({mode}):")
    output.append("=" * 60)
    
    if results.get('errors'):
        output.append("\n❌ 错误:")
        for error in results['errors']:
            output.append(f"   - {error}")
    
    if results.get('categories'):
        output.append("\n📊 文件分类统计:")
        for category, files in sorted(results['categories'].items()):
            total_size = sum(f['size'] for f in files)
            output.append(f"   {category}: {len(files)} 个文件 ({format_file_size(total_size)})")
    
    if results.get('organized'):
        output.append(f"\n✅ 已整理 {len(results['organized'])} 个文件:")
        for item in results['organized'][:10]:  # 只显示前10个
            output.append(f"   {item['from'].split('/')[-1]} → {item['category']}/")
        if len(results['organized']) > 10:
            output.append(f"   ... 还有 {len(results['organized']) - 10} 个文件")
    
    output.append("\n" + "=" * 60)
    
    return "\n".join(output)


def format_duplicate_results(results: dict) -> str:
    """格式化重复文件检测结果"""
    output = []
    
    output.append(f"🔍 重复文件检测结果:")
    output.append("=" * 60)
    output.append(f"总文件数: {results.get('total_files', 0)}")
    output.append(f"重复组数: {results.get('duplicate_groups', 0)}")
    output.append("")
    
    duplicates = results.get('duplicates', {})
    if not duplicates:
        output.append("✅ 未发现重复文件")
    else:
        for i, (key, files) in enumerate(duplicates.items(), 1):
            output.append(f"\n📋 重复组 {i}:")
            for j, f in enumerate(files, 1):
                output.append(f"   {j}. {f['path']}")
                output.append(f"      大小: {format_file_size(f['size'])}")
    
    output.append("\n" + "=" * 60)
    
    return "\n".join(output)


def format_rename_results(results: dict, dry_run: bool = True) -> str:
    """格式化重命名结果"""
    output = []
    
    mode = "模拟运行" if dry_run else "执行"
    output.append(f"📝 文件重命名结果 ({mode}):")
    output.append("=" * 60)
    output.append(f"总文件数: {results.get('total', 0)}")
    output.append(f"待重命名: {len(results.get('renamed', []))}")
    output.append("")
    
    if results.get('renamed'):
        output.append("待重命名文件:")
        for item in results['renamed'][:15]:
            output.append(f"   {item['from']} → {item['to']}")
        if len(results['renamed']) > 15:
            output.append(f"   ... 还有 {len(results['renamed']) - 15} 个文件")
    
    if results.get('errors'):
        output.append("\n❌ 错误:")
        for error in results['errors']:
            output.append(f"   - {error}")
    
    output.append("\n" + "=" * 60)
    
    return "\n".join(output)


def format_folder_structure_results(results: dict) -> str:
    """格式化文件夹结构创建结果"""
    output = []
    
    output.append(f"📂 文件夹结构创建结果:")
    output.append("=" * 60)
    output.append(f"已创建: {len(results.get('created', []))} 个文件夹")
    output.append("")
    
    if results.get('created'):
        output.append("创建的文件夹:")
        for folder in results['created']:
            output.append(f"   📁 {folder}")
    
    if results.get('errors'):
        output.append("\n❌ 错误:")
        for error in results['errors']:
            output.append(f"   - {error}")
    
    output.append("\n" + "=" * 60)
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description='File Organizer Tool for OpenClaw',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_organizer.py organize "C:\\Downloads"
  python file_organizer.py duplicates "C:\\Downloads"
  python file_organizer.py rename "C:\\Downloads" "old" "new"
  python file_organizer.py structure "C:\\Project" --structure '{"src": {}, "tests": {}}'
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Organize command
    parser_org = subparsers.add_parser('organize', help='Organize files by type')
    parser_org.add_argument('path', help='Target folder path')
    parser_org.add_argument('--dry-run', action='store_true', default=True,
                           help='Dry run (default: True)')
    parser_org.add_argument('--execute', action='store_true',
                           help='Actually execute the organization')
    
    # Duplicates command
    parser_dup = subparsers.add_parser('duplicates', help='Find duplicate files')
    parser_dup.add_argument('path', help='Target folder path')
    parser_dup.add_argument('--by-name', action='store_true',
                           help='Find duplicates by name only')
    
    # Rename command
    parser_ren = subparsers.add_parser('rename', help='Rename files')
    parser_ren.add_argument('path', help='Target folder path')
    parser_ren.add_argument('pattern', help='Pattern to match')
    parser_ren.add_argument('replacement', help='Replacement string')
    parser_ren.add_argument('--regex', action='store_true', help='Use regex')
    parser_ren.add_argument('--dry-run', action='store_true', default=True)
    parser_ren.add_argument('--execute', action='store_true')
    
    # Structure command
    parser_str = subparsers.add_parser('structure', help='Create folder structure')
    parser_str.add_argument('path', help='Root folder path')
    parser_str.add_argument('--structure', default='{}',
                           help='Folder structure as JSON')
    
    args = parser.parse_args()
    
    if args.command == 'organize':
        folder = Path(args.path)
        dry_run = not args.execute
        results = organize_by_type(folder, dry_run)
        print(format_organize_results(results, dry_run))
        
    elif args.command == 'duplicates':
        folder = Path(args.path)
        by_content = not args.by_name
        results = find_duplicates(folder, by_content)
        print(format_duplicate_results(results))
        
    elif args.command == 'rename':
        folder = Path(args.path)
        dry_run = not args.execute
        results = rename_files(folder, args.pattern, args.replacement, 
                              args.regex, dry_run)
        print(format_rename_results(results, dry_run))
        
    elif args.command == 'structure':
        folder = Path(args.path)
        import json as json_lib
        try:
            structure = json_lib.loads(args.structure)
        except:
            structure = {}
        results = create_folder_structure(folder, structure)
        print(format_folder_structure_results(results))
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
