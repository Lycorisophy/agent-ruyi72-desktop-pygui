#!/usr/bin/env python3
"""Compression for Ruyi72 - ZIP compression and decompression"""
import argparse, os, zipfile
from pathlib import Path
from datetime import datetime

def compress_zip(source, output, include_folder=False):
    """压缩文件或文件夹为 ZIP"""
    source = Path(source)
    output = Path(output)
    
    if not source.exists():
        return {'error': f'源路径不存在: {source}'}
    
    try:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            if source.is_file():
                zf.write(source, source.name)
                arcname = source.name
            else:
                if include_folder:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            file_path = Path(root, file)
                            arcname = file_path.relative_to(source.parent)
                            zf.write(file_path, arcname)
                else:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            file_path = Path(root, file)
                            arcname = file_path.relative_to(source)
                            zf.write(file_path, arcname)
        
        size = output.stat().st_size
        return {
            'success': True,
            'file': str(output),
            'size': f'{size/1024:.1f} KB'
        }
    except Exception as e:
        return {'error': str(e)}

def decompress_zip(source, dest=None):
    """解压 ZIP 文件"""
    source = Path(source)
    
    if not source.exists():
        return {'error': f'文件不存在: {source}'}
    
    if dest is None:
        dest = source.parent / source.stem
    
    dest = Path(dest)
    
    try:
        dest.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(source, 'r') as zf:
            zf.extractall(dest)
        
        files = list(dest.rglob('*'))
        return {
            'success': True,
            'file': str(source),
            'destination': str(dest),
            'extracted': len(files)
        }
    except zipfile.BadZipFile:
        return {'error': '不是有效的 ZIP 文件'}
    except Exception as e:
        return {'error': str(e)}

def list_zip_contents(source):
    """列出 ZIP 文件内容"""
    source = Path(source)
    
    if not source.exists():
        return {'error': f'文件不存在: {source}'}
    
    try:
        with zipfile.ZipFile(source, 'r') as zf:
            info = zf.infolist()
            total_size = sum(z.file_size for z in info)
            
            return {
                'file': str(source),
                'count': len(info),
                'total_size': f'{total_size/1024:.1f} KB',
                'files': [{'name': z.filename, 'size': f'{z.file_size/1024:.1f} KB'} for z in info[:50]]
            }
    except zipfile.BadZipFile:
        return {'error': '不是有效的 ZIP 文件'}
    except Exception as e:
        return {'error': str(e)}

def format_compress_result(result):
    if 'error' in result:
        return f"❌ {result['error']}"
    return f"✅ 压缩成功!\n📦 文件: {result['file']}\n📏 大小: {result['size']}"

def format_decompress_result(result):
    if 'error' in result:
        return f"❌ {result['error']}"
    return f"✅ 解压成功!\n📦 源文件: {result['file']}\n📁 目标: {result['destination']}\n📊 文件数: {result['extracted']}"

def format_list_result(result):
    if 'error' in result:
        return f"❌ {result['error']}"
    lines = [f"📦 {result['file']}", f"文件数: {result['count']}", f"总大小: {result['total_size']}", "="*50]
    for f in result['files']:
        lines.append(f"  {f['name']:<40} {f['size']}")
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='Compression Tool for Ruyi72')
    sub = parser.add_subparsers(dest='cmd')
    
    sub.add_parser('compress', help='Compress files').add_argument('source').add_argument('output', default='archive.zip')
    sub.add_parser('extract', help='Extract ZIP').add_argument('source').add_argument('--dest', '-d')
    sub.add_parser('list', help='List ZIP contents').add_argument('source')
    
    args = parser.parse_args()
    
    if args.cmd == 'compress':
        r = compress_zip(args.source, args.output)
        print(format_compress_result(r))
    elif args.cmd == 'extract':
        r = decompress_zip(args.source, args.dest)
        print(format_decompress_result(r))
    elif args.cmd == 'list':
        r = list_zip_contents(args.source)
        print(format_list_result(r))
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
