# 代码审查技能

## Skill: code_review

对代码进行静态分析和审查

## Description

分析代码文件，检查常见问题、代码质量、安全漏洞等。

## Parameters

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| path | string | 是 | - | 代码文件路径 |
| language | string | 否 | auto | 编程语言 |
| level | string | 否 | standard | 审查级别: basic, standard, strict |

## Examples

```
code_review path="/project/main.py"
code_review path="/project" language="python" level="strict"
```

## Triggers

- 审查代码
- 代码检查
- 代码分析
