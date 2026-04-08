#!/usr/bin/env python3
"""
MySQL Database Skill for Ruyi72
Execute SQL queries and database operations
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import os


class MySQLHandler:
    def __init__(self, host='localhost', port=3306, user='', password='', database=''):
        self.connection = None
        self.config = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }
        self.connected = False
        self.last_error = None
    
    def connect(self):
        """建立数据库连接"""
        try:
            import mysql.connector
            from mysql.connector import Error
            
            self.config['autocommit'] = True
            
            self.connection = mysql.connector.connect(**self.config)
            
            if self.connection.is_connected():
                self.connected = True
                db_info = self.connection.get_server_info()
                return f"成功连接到 MySQL 服务器 (版本: {db_info})"
                
        except ImportError:
            return "❌ 缺少 mysql-connector-python 库\n请安装: pip install mysql-connector-python"
            
        except Exception as e:
            self.last_error = str(e)
            return f"❌ 连接失败: {e}"
    
    def execute_query(self, query: str, fetch: bool = True) -> dict:
        """执行 SQL 查询"""
        result = {
            'success': False,
            'query': query,
            'data': None,
            'message': '',
            'row_count': 0
        }
        
        if not self.connected:
            conn_result = self.connect()
            if not self.connected:
                result['message'] = conn_result
                return result
        
        try:
            import mysql.connector
            from mysql.connector import Error
            
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute(query)
            
            if fetch and cursor.description:
                result['data'] = cursor.fetchall()
                result['row_count'] = len(result['data'])
                result['success'] = True
                result['message'] = f"✅ 查询成功，返回 {result['row_count']} 行"
            elif not fetch:
                self.connection.commit()
                result['success'] = True
                result['message'] = f"✅ 执行成功，影响 {cursor.rowcount} 行"
            else:
                result['success'] = True
                result['message'] = "✅ 执行成功"
            
            cursor.close()
            
        except ImportError:
            result['message'] = "❌ 缺少 mysql-connector-python 库"
            
        except Exception as e:
            result['message'] = f"❌ 执行失败: {e}"
        
        return result
    
    def get_table_schema(self, table_name: str) -> dict:
        """获取表结构"""
        query = f"DESCRIBE {table_name}"
        return self.execute_query(query)
    
    def list_tables(self, database: str = None) -> dict:
        """列出所有表"""
        if database:
            query = f"SHOW TABLES FROM {database}"
        else:
            query = "SHOW TABLES"
        return self.execute_query(query)
    
    def list_databases(self) -> dict:
        """列出所有数据库"""
        return self.execute_query("SHOW DATABASES")
    
    def execute_file(self, file_path: str) -> dict:
        """执行 SQL 文件"""
        path = Path(file_path)
        if not path.exists():
            return {'success': False, 'message': f'文件不存在: {file_path}'}
        
        sql_content = path.read_text(encoding='utf-8')
        
        # 分割多条语句
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        results = {
            'success': True,
            'file': str(path),
            'statements': len(statements),
            'results': []
        }
        
        for stmt in statements:
            result = self.execute_query(stmt, fetch=False)
            results['results'].append({
                'query': stmt[:100] + '...' if len(stmt) > 100 else stmt,
                'success': result['success'],
                'message': result['message']
            })
        
        return results
    
    def close(self):
        """关闭连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.connected = False


def format_query_results(result: dict) -> str:
    """格式化查询结果"""
    output = []
    
    output.append(f"📊 查询结果:")
    output.append("=" * 70)
    output.append(f"查询: {result.get('query', '')}")
    output.append(f"状态: {result.get('message', '')}")
    output.append("")
    
    if result.get('data'):
        data = result['data']
        if not data:
            output.append("无数据")
        else:
            # 获取列名
            columns = list(data[0].keys()) if data else []
            
            # 表头
            header = " | ".join(columns)
            output.append(header)
            output.append("-" * len(header))
            
            # 数据行（限制显示 20 行）
            for i, row in enumerate(data[:20]):
                row_data = " | ".join(str(row.get(col, '')) for col in columns)
                output.append(row_data)
            
            if len(data) > 20:
                output.append(f"... 还有 {len(data) - 20} 行数据")
    
    output.append("=" * 70)
    
    return "\n".join(output)


def format_execution_results(result: dict) -> str:
    """格式化执行结果"""
    output = []
    
    output.append(f"📋 执行结果:")
    output.append("=" * 70)
    output.append(result.get('message', ''))
    output.append("=" * 70)
    
    return "\n".join(output)


def format_list_results(result: dict, item_type: str) -> str:
    """格式化列表结果"""
    output = []
    
    output.append(f"📋 {item_type} 列表:")
    output.append("=" * 70)
    
    if result.get('data'):
        for item in result['data']:
            if isinstance(item, dict):
                values = list(item.values())
                output.append("  " + " | ".join(str(v) for v in values))
            else:
                output.append(f"  {item}")
    
    output.append(f"总计: {result.get('row_count', 0)} 条")
    output.append("=" * 70)
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description='MySQL Database Tool for Ruyi72',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mysql_writer.py --query "SELECT * FROM users LIMIT 10"
  python mysql_writer.py --query "SHOW DATABASES"
  python mysql_writer.py --execute "UPDATE users SET email='new@test.com' WHERE id=1"
  python mysql_writer.py --list-tables
  python mysql_writer.py --list-databases
        """
    )
    
    parser.add_argument('--host', default='localhost', help='MySQL host')
    parser.add_argument('--port', type=int, default=3306, help='MySQL port')
    parser.add_argument('--user', default=os.environ.get('MYSQL_USER', ''), help='MySQL user')
    parser.add_argument('--password', default=os.environ.get('MYSQL_PASSWORD', ''), help='MySQL password')
    parser.add_argument('--database', default='', help='Database name')
    
    # 操作参数
    parser.add_argument('--query', '-q', help='SQL query to execute')
    parser.add_argument('--execute', '-e', help='SQL statement to execute (no result)')
    parser.add_argument('--list-databases', action='store_true', help='List all databases')
    parser.add_argument('--list-tables', action='store_true', help='List all tables')
    parser.add_argument('--table-schema', help='Get table schema')
    parser.add_argument('--file', '-f', help='SQL file to execute')
    
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # 创建连接
    mysql = MySQLHandler(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    # 执行操作
    if args.query:
        result = mysql.execute_query(args.query)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_query_results(result))
            
    elif args.execute:
        result = mysql.execute_query(args.execute, fetch=False)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_execution_results(result))
            
    elif args.list_databases:
        result = mysql.list_databases()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_list_results(result, "数据库"))
            
    elif args.list_tables:
        result = mysql.list_tables(args.database)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_list_results(result, "数据表"))
            
    elif args.table_schema:
        result = mysql.get_table_schema(args.table_schema)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_query_results(result))
            
    elif args.file:
        result = mysql.execute_file(args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()
    
    mysql.close()


if __name__ == '__main__':
    main()
