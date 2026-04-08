#!/usr/bin/env python3
"""File Search for Ruyi72 - Full text search in files"""
import argparse, os, re
from pathlib import Path

def search_files(path, pattern, file_types=None, use_regex=False, context=2):
    results = []
    path = Path(path)
    
    if not path.exists():
        return {'error': f'路径不存在: {path}'}
    
    # 编译正则表达式
    try:
        if use_regex:
            regex = re.compile(pattern)
        else:
            regex = re.compile(re.escape(pattern))
    except re.error as e:
        return {'error': f'正则表达式错误: {e}'}
    
    # 遍历文件
    for file_path in path.rglob('*'):
        if file_path.is_file():
            # 检查文件类型
            if file_types:
                if file_path.suffix.lower() not in file_types:
                    continue
            
            # 跳过隐藏文件和系统文件
            if file_path.name.startswith('.') or 'node_modules' in str(file_path):
                continue
            
            try:
                # 读取文件（限制大小）
                if file_path.stat().st_size > 1024 * 1024:  # 跳过大于1MB的文件
                    continue
                
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                matches = []
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        # 获取上下文
                        start = max(0, i - context - 1)
                        end = min(len(lines), i + context)
                        context_lines = []
                        for j in range(start, end):
                            prefix = '>>>' if j == i - 1 else '   '
                            context_lines.append(f"{prefix} {j+1}: {lines[j]}")
                        matches.append({
                            'line': i,
                            'content': '\n'.join(context_lines)
                        })
                
                if matches:
                    results.append({
                        'file': str(file_path),
                        'relative_path': str(file_path.relative_to(path)),
                        'match_count': len(matches),
                        'matches': matches
                    })
                    
            except Exception:
                continue
    
    return {
        'search_path': str(path),
        'pattern': pattern,
        'total_files': len(results),
        'results': results
    }

def format_results(result):
    if 'error' in result:
        return f"❌ {result['error']}"
    
    output = []
    output.append(f"🔍 搜索结果: {result['pattern']}")
    output.append(f"📁 搜索路径: {result['search_path']}")
    output.append(f"📊 找到 {result['total_files']} 个匹配文件")
    output.append("=" * 70)
    
    for item in result['results'][:20]:  # 限制显示20个文件
        output.append(f"\n📄 {item['relative_path']}")
        output.append(f"   匹配行数: {item['match_count']}")
        for match in item['matches'][:3]:  # 每个文件最多显示3处
            output.append(match['content'])
    
    if result['total_files'] > 20:
        output.append(f"\n... 还有 {result['total_files'] - 20} 个文件")
    
    return '\n'.join(output)

def main():
    parser = argparse.ArgumentParser(description='File Search for Ruyi72')
    parser.add_argument('path', nargs='?', default='.', help='Search path')
    parser.add_argument('pattern', help='Search pattern')
    parser.add_argument('--types', '-t', help='File types (e.g., .py,.md)')
    parser.add_argument('--regex', '-r', action='store_true', help='Use regex')
    parser.add_argument('--context', '-c', type=int, default=2, help='Context lines')
    
    args = parser.parse_args()
    
    file_types = None
    if args.types:
        file_types = [t.strip().lower() for t in args.types.split(',')]
    
    result = search_files(args.path, args.pattern, file_types, args.regex, args.context)
    print(format_results(result))

if __name__ == '__main__':
    main()
