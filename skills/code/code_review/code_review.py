#!/usr/bin/env python3
"""
代码审查技能脚本

对代码进行静态分析和审查
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional


class CodeReviewer:
    """代码审查器"""
    
    def __init__(self, language: str = "auto", level: str = "standard"):
        self.language = language
        self.level = level
        self.issues = []
    
    def detect_language(self, path: str) -> str:
        """检测编程语言"""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
        }
        ext = Path(path).suffix.lower()
        return ext_map.get(ext, "unknown")
    
    def review_python(self, content: str) -> list:
        """审查 Python 代码"""
        issues = []
        lines = content.split("\n")
        
        # 检查常见问题
        for i, line in enumerate(lines, 1):
            # 打印语句
            if re.match(r"^\s*print\s*\(.*\)", line):
                issues.append({
                    "line": i,
                    "severity": "info",
                    "type": "debug",
                    "message": "发现 print 语句，可能需要移除"
                })
            
            # TODO/FIXME
            if re.search(r"#\s*(TODO|FIXME|HACK|XXX)", line, re.I):
                issues.append({
                    "line": i,
                    "severity": "warning",
                    "type": "todo",
                    "message": f"发现标记: {re.search(r"#\s*(TODO|FIXME|HACK|XXX)[^:]*:?\s*(.*)", line).group(0)}"
                })
            
            # 硬编码凭证
            if re.search(r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", line, re.I):
                issues.append({
                    "line": i,
                    "severity": "error",
                    "type": "security",
                    "message": "发现可能的硬编码凭证"
                })
            
            # 空 except
            if re.match(r"^\s*except\s*:", line):
                issues.append({
                    "line": i,
                    "severity": "warning",
                    "type": "error-handling",
                    "message": "空 except 语句，应指定异常类型"
                })
            
            # 未使用的变量
            if re.match(r"^\s*_\w+\s*=", line):
                issues.append({
                    "line": i,
                    "severity": "info",
                    "type": "style",
                    "message": "变量以下划线开头，通常表示未使用"
                })
            
            # 行过长
            if self.level in ["standard", "strict"] and len(line) > 120:
                issues.append({
                    "line": i,
                    "severity": "info",
                    "type": "style",
                    "message": f"行过长 ({len(line)} 字符)"
                })
        
        return issues
    
    def review_file(self, path: str) -> dict:
        """审查文件"""
        file_path = Path(path)
        
        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {path}"}
        
        if not file_path.is_file():
            return {"success": False, "error": f"不是文件: {path}"}
        
        try:
            content = file_path.read_text(encoding="utf-8")
        except:
            return {"success": False, "error": "无法读取文件"}
        
        # 检测语言
        language = self.language
        if language == "auto":
            language = self.detect_language(path)
        
        # 根据语言审查
        if language == "python":
            self.issues = self.review_python(content)
        else:
            self.issues = [{"severity": "info", "message": f"暂不支持 {language} 的详细审查"}]
        
        return {
            "success": True,
            "language": language,
            "lines": len(lines := content.split("\n")),
            "issues": self.issues,
            "summary": {
                "errors": len([i for i in self.issues if i["severity"] == "error"]),
                "warnings": len([i for i in self.issues if i["severity"] == "warning"]),
                "info": len([i for i in self.issues if i["severity"] == "info"]),
            }
        }


def main():
    params = json.loads(sys.stdin.read())
    
    path = params.get("path")
    language = params.get("language", "auto")
    level = params.get("level", "standard")
    
    if not path:
        result = {"success": False, "error": "缺少 path 参数"}
        print(json.dumps(result))
        return
    
    reviewer = CodeReviewer(language, level)
    review_result = reviewer.review_file(path)
    
    # 格式化输出
    if review_result["success"]:
        output_lines = [f"=== 代码审查报告 ==="]
        output_lines.append(f"文件: {path}")
        output_lines.append(f"语言: {review_result['language']}")
        output_lines.append(f"行数: {review_result['lines']}")
        output_lines.append("")
        output_lines.append(f"=== 问题汇总 ===")
        summary = review_result["summary"]
        output_lines.append(f"错误: {summary['errors']}")
        output_lines.append(f"警告: {summary['warnings']}")
        output_lines.append(f"提示: {summary['info']}")
        output_lines.append("")
        
        if review_result["issues"]:
            output_lines.append("=== 详细信息 ===")
            for issue in review_result["issues"]:
                line_info = f"行 {issue['line']}: " if "line" in issue else ""
                output_lines.append(f"[{issue['severity'].upper()}] {line_info}{issue['message']}")
        
        review_result["output"] = "\n".join(output_lines)
    
    print(json.dumps(review_result, ensure_ascii=False))


if __name__ == "__main__":
    main()
