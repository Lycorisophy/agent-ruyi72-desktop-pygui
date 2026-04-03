#!/usr/bin/env python3
"""快捷命令"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.openclaw/workspace/memory/quick-commands")
COMMANDS_FILE = os.path.join(STORAGE_DIR, "commands.json")


def ensure_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def load_commands():
    ensure_dir()
    if not os.path.exists(COMMANDS_FILE):
        return {}
    try:
        with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_commands(commands):
    ensure_dir()
    with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="快捷命令")
    parser.add_argument("--add", help="添加命令: --add 命令名 命令内容")
    parser.add_argument("--run", help="执行命令")
    parser.add_argument("--list", action="store_true", help="列出命令")
    parser.add_argument("--delete", help="删除命令")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    commands = load_commands()

    if args.add:
        parts = args.add.split(" ", 1)
        if len(parts) < 2:
            print("用法: --add 命令名 命令内容")
            return 1
        name, cmd = parts
        commands[name] = {"cmd": cmd, "time": datetime.now().isoformat()}
        save_commands(commands)
        print(f"✓ 已添加命令: {name} -> {cmd}")
        return 0

    if args.delete:
        if args.delete in commands:
            del commands[args.delete]
            save_commands(commands)
            print(f"✓ 已删除命令: {args.delete}")
        else:
            print(f"命令不存在: {args.delete}")
        return 0

    if args.list:
        if args.json:
            print(json.dumps({"commands": commands}, indent=2, ensure_ascii=False))
        else:
            print("===== 快捷命令 =====")
            if commands:
                for name, info in commands.items():
                    print(f"{name}: {info['cmd']}")
            else:
                print("暂无命令")
        return 0

    if args.run:
        if args.run in commands:
            cmd = commands[args.run]["cmd"]
            print(f"> 执行: {cmd}")
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                print(result.stdout)
                if result.stderr:
                    print(f"错误: {result.stderr}")
            except Exception as e:
                print(f"执行失败: {e}")
        else:
            print(f"命令不存在: {args.run}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
