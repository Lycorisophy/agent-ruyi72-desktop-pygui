# 技能系统设计规范

## SKILL.md 技能定义格式

每个技能目录包含：
- `SKILL.md` - 技能定义文件
- `*.py` 或 `*.ps1` - 技能执行脚本

### SKILL.md 格式

```markdown
# 技能名称

## Skill: skill_name

技能的唯一标识符，用于 Agent 调用。

## Description

技能的详细描述，说明技能的功能和用途。

## Parameters

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| param1 | string | 是 | - | 参数1描述 |
| param2 | integer | 否 | 10 | 参数2描述 |

## Examples

```
skill_name param1="value1"
skill_name param1="value1" param2=20
```

## Triggers

触发关键词列表：
- 触发词1
- 触发词2

## Constraints

- 约束条件1
- 约束条件2
```

### 脚本格式

技能脚本接收 JSON 参数，通过 stdin 输入，返回 JSON 结果到 stdout。

**Python 脚本：**
```python
#!/usr/bin/env python3
"""技能脚本模板"""
import json
import sys

def main():
    # 从 stdin 读取参数
    params = json.loads(sys.stdin.read())
    
    # 执行逻辑
    result = {
        "success": True,
        "output": "执行结果",
        "metadata": {}
    }
    
    # 输出到 stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

**PowerShell 脚本：**
```powershell
# 技能脚本模板
param(
    [Parameter(Mandatory=$true)]
    [string]$Param1,
    
    [Parameter(Mandatory=$false)]
    [int]$Param2 = 10
)

# 接收 stdin 参数（JSON 格式）
$input = $input

# 执行逻辑
$result = @{
    success = $true
    output = "执行结果"
    metadata = @{}
}

# 输出到 stdout
$result | ConvertTo-Json -Compress
```

### 执行协议

1. **输入**：通过环境变量或 stdin 传递参数
2. **输出**：JSON 格式结果

```json
{
    "success": true,
    "output": "执行结果内容",
    "error": null,
    "metadata": {
        "execution_time": 1.23,
        "files_affected": ["file1.txt"]
    }
}
```

### 内置变量

| 变量 | 描述 |
|------|------|
| `{WORKSPACE}` | 当前工作目录 |
| `{SESSION_ID}` | 会话 ID |
| `{USER_HOME}` | 用户主目录 |
