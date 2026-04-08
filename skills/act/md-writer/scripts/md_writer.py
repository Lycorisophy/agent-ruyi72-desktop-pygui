#!/usr/bin/env python3
"""
MD Document Writer for Ruyi72
Creates Markdown documents with full formatting support
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


class MDWriter:
    def __init__(self):
        self.content = []
        
    def add_title(self, text: str, level: int = 1):
        """添加标题"""
        if level < 1 or level > 6:
            level = 1
        self.content.append('#' * level + ' ' + text)
        
    def add_heading(self, text: str, level: int = 2):
        """添加小标题"""
        self.add_title(text, level)
        
    def add_paragraph(self, text: str):
        """添加段落"""
        self.content.append(text)
        self.content.append('')
        
    def add_bold(self, text: str) -> str:
        """粗体文本"""
        return f'**{text}**'
    
    def add_italic(self, text: str) -> str:
        """斜体文本"""
        return f'*{text}*'
    
    def add_strikethrough(self, text: str) -> str:
        """删除线"""
        return f'~~{text}~~'
    
    def add_list(self, items: list, ordered: bool = False):
        """添加列表"""
        for i, item in enumerate(items, 1):
            if ordered:
                self.content.append(f'{i}. {item}')
            else:
                self.content.append(f'- {item}')
        self.content.append('')
    
    def add_todo_list(self, items: list):
        """添加待办列表"""
        for item in items:
            self.content.append(f'- [ ] {item}')
        self.content.append('')
    
    def add_code_block(self, code: str, language: str = ''):
        """添加代码块"""
        if language:
            self.content.append(f'```{language}')
        else:
            self.content.append('```')
        self.content.append(code)
        self.content.append('```')
        self.content.append('')
    
    def add_inline_code(self, code: str) -> str:
        """行内代码"""
        return f'`{code}`'
    
    def add_blockquote(self, text: str):
        """添加引用块"""
        for line in text.split('\n'):
            self.content.append(f'> {line}')
        self.content.append('')
    
    def add_table(self, headers: list, rows: list, align: list = None):
        """添加表格"""
        # 表头
        header_row = '| ' + ' | '.join(headers) + ' |'
        self.content.append(header_row)
        
        # 分隔线
        if align:
            sep = '| ' + ' | '.join(['---' if a != 'c' else ':---:' for a in align]) + ' |'
        else:
            sep = '| ' + ' | '.join(['---'] * len(headers)) + ' |'
        self.content.append(sep)
        
        # 数据行
        for row in rows:
            data_row = '| ' + ' | '.join(str(cell) for cell in row) + ' |'
            self.content.append(data_row)
        
        self.content.append('')
    
    def add_image(self, alt_text: str, url: str, title: str = ''):
        """添加图片"""
        if title:
            self.content.append(f'![{alt_text}]({url} "{title}")')
        else:
            self.content.append(f'![{alt_text}]({url})')
    
    def add_link(self, text: str, url: str, title: str = ''):
        """添加链接"""
        if title:
            self.content.append(f'[{text}]({url} "{title}")')
        else:
            self.content.append(f'[{text}]({url})')
    
    def add_hr(self):
        """添加分隔线"""
        self.content.append('---')
        self.content.append('')
    
    def add_front_matter(self, data: dict):
        """添加 Front Matter (Jekyll/Hugo)"""
        self.content.append('---')
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                self.content.append(f'{key}: {json.dumps(value, ensure_ascii=False)}')
            else:
                self.content.append(f'{key}: {value}')
        self.content.append('---')
        self.content.append('')
    
    def create_document(self, title: str, content_dict: dict):
        """
        创建完整文档
        
        content_dict 结构:
        {
            'front_matter': {...},
            'title': '文档标题',
            'headings': [
                {'level': 1, 'text': '一级标题'},
                {'level': 2, 'text': '二级标题'}
            ],
            'paragraphs': ['段落1', '段落2'],
            'lists': [['项1', '项2'], ordered=True],
            'tables': [
                {'headers': ['列1', '列2'], 'rows': [['数据1', '数据2']]}
            ],
            'code_blocks': [
                {'code': 'print("hello")', 'language': 'python'}
            ],
            'blockquotes': ['引用文本'],
            'images': [{'alt': '图片描述', 'url': 'path/to/image.png'}],
            'todos': ['任务1', '任务2']
        }
        """
        # Front Matter
        if 'front_matter' in content_dict:
            self.add_front_matter(content_dict['front_matter'])
        
        # 标题
        if 'title' in content_dict:
            self.add_title(content_dict['title'], 1)
            self.content.append('')
        
        # 遍历所有内容
        content_types = ['headings', 'paragraphs', 'lists', 'tables', 'code_blocks', 
                        'blockquotes', 'images', 'todos']
        
        for content_type in content_types:
            if content_type not in content_dict:
                continue
                
            items = content_dict[content_type]
            
            if content_type == 'headings':
                for h in items:
                    self.add_heading(h.get('text', ''), h.get('level', 2))
                    
            elif content_type == 'paragraphs':
                for p in items:
                    self.add_paragraph(p)
                    
            elif content_type == 'lists':
                for lst in items:
                    if isinstance(lst, dict):
                        self.add_list(lst.get('items', []), lst.get('ordered', False))
                    else:
                        self.add_list(lst)
                        
            elif content_type == 'tables':
                for t in items:
                    self.add_table(
                        t.get('headers', []),
                        t.get('rows', []),
                        t.get('align', None)
                    )
                    
            elif content_type == 'code_blocks':
                for cb in items:
                    self.add_code_block(
                        cb.get('code', ''),
                        cb.get('language', '')
                    )
                    
            elif content_type == 'blockquotes':
                for bq in items:
                    self.add_blockquote(bq)
                    
            elif content_type == 'images':
                for img in items:
                    self.add_image(
                        img.get('alt', ''),
                        img.get('url', ''),
                        img.get('title', '')
                    )
                    
            elif content_type == 'todos':
                self.add_todo_list(items)
    
    def save(self, filepath: str):
        """保存文档"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(self.content), encoding='utf-8')
        return str(path)
    
    def get_content(self) -> str:
        """获取文档内容"""
        return '\n'.join(self.content)


def format_md_results(saved_path: str, content_length: int) -> str:
    """格式化保存结果"""
    return f"""
✅ Markdown 文档创建成功！

📄 文件路径: {saved_path}
📏 内容长度: {content_length} 字符

可使用任何 Markdown 编辑器打开和查看。
"""


def main():
    parser = argparse.ArgumentParser(
        description='MD Document Writer for Ruyi72',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--output', '-o', default='document.md', help='Output file path')
    parser.add_argument('--title', '-t', default='新文档', help='Document title')
    parser.add_argument('--content', '-c', default='{}', help='Content as JSON')
    parser.add_argument('--text', help='Simple text content')
    parser.add_argument('--code', help='Code block content')
    parser.add_argument('--language', default='python', help='Code language')
    
    args = parser.parse_args()
    
    writer = MDWriter()
    
    # 简单模式：直接添加文本
    if args.text:
        writer.add_title(args.title)
        writer.add_paragraph(args.text)
        saved_path = writer.save(args.output)
        print(format_md_results(saved_path, len(writer.get_content())))
        
    # 代码块模式
    elif args.code:
        writer.add_title(args.title)
        writer.add_code_block(args.code, args.language)
        saved_path = writer.save(args.output)
        print(format_md_results(saved_path, len(writer.get_content())))
        
    # 复杂模式：从 JSON 加载
    else:
        try:
            content_dict = json.loads(args.content)
            writer.create_document(args.title, content_dict)
            saved_path = writer.save(args.output)
            print(format_md_results(saved_path, len(writer.get_content())))
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析错误: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
