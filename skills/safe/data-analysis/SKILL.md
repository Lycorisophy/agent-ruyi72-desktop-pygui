---
name: data-analysis
description: 当用户上传 Excel（.xlsx/.xls）或 CSV 文件，并希望进行数据分析、生成统计信息、创建汇总、数据透视表、SQL 查询或任何形式的结构化数据探索时，使用此技能。支持多工作表 Excel 工作簿、聚合、过滤、连接以及将结果导出为 CSV/JSON/Markdown。
ask-enable: true
---

# 数据分析技能

## 概述

本技能使用 DuckDB（一个进程内分析型 SQL 引擎）分析用户上传的 Excel/CSV 文件。它通过单个 Python 脚本支持结构检查、基于 SQL 的查询、统计汇总和结果导出。

## 核心能力

- 检查 Excel/CSV 文件结构（工作表、列、类型、行数）
- 对上传的数据执行任意 SQL 查询
- 生成统计汇总（平均值、中位数、标准差、百分位数、空值）
- 支持多工作表 Excel 工作簿（每个工作表成为一个表）
- 将查询结果导出为 CSV、JSON 或 Markdown
- 利用 DuckDB 的列式引擎高效处理大文件

## 工作流程

### 步骤 1：理解需求

当用户上传数据文件并请求分析时，需要明确：

- **文件位置**：上传的 Excel/CSV 文件在 `/mnt/user-data/uploads/` 下的路径
- **分析目标**：用户想要什么洞察（汇总、过滤、聚合、比较等）
- **输出格式**：结果应以何种形式呈现（表格、CSV 导出、JSON 等）
- 你不需要检查 `/mnt/user-data` 下的文件夹

### 步骤 2：检查文件结构

首先检查上传的文件以了解其结构：

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/data.xlsx \
  --action inspect
```

返回内容：
- 工作表名称（Excel）或文件名（CSV）
- 列名、数据类型和非空计数
- 每个工作表/文件的行数
- 示例数据（前 5 行）

### 步骤 3：执行分析

根据结构，构造 SQL 查询来回答用户的问题。

#### 运行 SQL 查询

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/data.xlsx \
  --action query \
  --sql "SELECT category, COUNT(*) as count, AVG(amount) as avg_amount FROM Sheet1 GROUP BY category ORDER BY count DESC"
```

#### 生成统计汇总

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/data.xlsx \
  --action summary \
  --table Sheet1
```

对每个数值列返回：计数、均值、标准差、最小值、25%、50%、75%、最大值、空值计数。
对字符串列返回：计数、唯一值数、最高频值、频次、空值计数。

#### 导出结果

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/data.xlsx \
  --action query \
  --sql "SELECT * FROM Sheet1 WHERE amount > 1000" \
  --output-file /mnt/user-data/outputs/filtered-results.csv
```

支持的输出格式（根据扩展名自动识别）：
- `.csv` — 逗号分隔值
- `.json` — JSON 记录数组
- `.md` — Markdown 表格

### 参数

| 参数 | 是否必需 | 描述 |
|-----------|----------|-------------|
| `--files` | 是 | 以空格分隔的 Excel/CSV 文件路径 |
| `--action` | 是 | 取值：`inspect`、`query`、`summary` |
| `--sql` | 对于 `query` | 要执行的 SQL 查询 |
| `--table` | 对于 `summary` | 要汇总的表/工作表名称 |
| `--output-file` | 否 | 导出结果的路径（CSV/JSON/MD） |

> [!NOTE]
> 不要读取 Python 文件，直接调用它并传入参数即可。

## 表命名规则

- **Excel 文件**：每个工作表成为一个以工作表名称命名的表（例如 `Sheet1`、`Sales`、`Revenue`）
- **CSV 文件**：表名为去掉扩展名的文件名（例如 `data.csv` → `data`）
- **多文件**：所有文件中的所有表都在同一个查询上下文中可用，支持跨文件连接
- **特殊字符**：包含空格或特殊字符的工作表/文件名会被自动清理（空格转下划线）。对于以数字开头或包含特殊字符的名称，使用双引号，例如 `"2024_Sales"`

## 分析模式

### 基本探索
```sql
-- 行数
SELECT COUNT(*) FROM Sheet1

-- 列中的唯一值
SELECT DISTINCT category FROM Sheet1

-- 值分布
SELECT category, COUNT(*) as cnt FROM Sheet1 GROUP BY category ORDER BY cnt DESC

-- 日期范围
SELECT MIN(date_col), MAX(date_col) FROM Sheet1
```

### 聚合与分组
```sql
-- 按类别和月份统计收入
SELECT category, DATE_TRUNC('month', order_date) as month,
       SUM(revenue) as total_revenue
FROM Sales
GROUP BY category, month
ORDER BY month, total_revenue DESC

-- 消费最高的 10 位客户
SELECT customer_name, SUM(amount) as total_spend
FROM Orders GROUP BY customer_name
ORDER BY total_spend DESC LIMIT 10
```

### 跨文件连接
```sql
-- 将销售数据与不同文件中的客户信息连接
SELECT s.order_id, s.amount, c.customer_name, c.region
FROM sales s
JOIN customers c ON s.customer_id = c.id
WHERE s.amount > 500
```

### 窗口函数
```sql
-- 累计总额和排名
SELECT order_date, amount,
       SUM(amount) OVER (ORDER BY order_date) as running_total,
       RANK() OVER (ORDER BY amount DESC) as amount_rank
FROM Sales
```

### 数据透视式分析
```sql
-- 数据透视：按类别的月度收入
SELECT category,
       SUM(CASE WHEN MONTH(date) = 1 THEN revenue END) as Jan,
       SUM(CASE WHEN MONTH(date) = 2 THEN revenue END) as Feb,
       SUM(CASE WHEN MONTH(date) = 3 THEN revenue END) as Mar
FROM Sales
GROUP BY category
```

## 完整示例

用户上传 `sales_2024.xlsx`（包含工作表：`Orders`、`Products`、`Customers`）并询问："分析我的销售数据 — 按收入显示前 10 名产品和月度趋势。"

### 步骤 1：检查文件

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/sales_2024.xlsx \
  --action inspect
```

### 步骤 2：按收入统计前 10 名产品

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/sales_2024.xlsx \
  --action query \
  --sql "SELECT p.product_name, SUM(o.quantity * o.unit_price) as total_revenue, SUM(o.quantity) as total_units FROM Orders o JOIN Products p ON o.product_id = p.id GROUP BY p.product_name ORDER BY total_revenue DESC LIMIT 10"
```

### 步骤 3：月度收入趋势

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/sales_2024.xlsx \
  --action query \
  --sql "SELECT DATE_TRUNC('month', order_date) as month, SUM(quantity * unit_price) as revenue FROM Orders GROUP BY month ORDER BY month" \
  --output-file /mnt/user-data/outputs/monthly-trends.csv
```

### 步骤 4：统计汇总

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/sales_2024.xlsx \
  --action summary \
  --table Orders
```

向用户呈现结果，并清晰解释发现、趋势和可操作的洞察。

## 多文件示例

用户上传 `orders.csv` 和 `customers.xlsx` 并询问："哪个地区的平均订单金额最高？"

```bash
python /mnt/skills/safe/data-analysis/scripts/analyze.py \
  --files /mnt/user-data/uploads/orders.csv /mnt/user-data/uploads/customers.xlsx \
  --action query \
  --sql "SELECT c.region, AVG(o.amount) as avg_order_value, COUNT(*) as order_count FROM orders o JOIN Customers c ON o.customer_id = c.id GROUP BY c.region ORDER BY avg_order_value DESC"
```

## 输出处理

分析完成后：

- 直接在对话中以格式化的表格呈现查询结果
- 对于大型结果，导出到文件并通过 `present_files` 工具分享
- 始终用通俗语言解释发现，并提供关键结论
- 当发现有趣的模式时，建议后续分析方向
- 如果用户希望保留结果，主动提供导出功能

## 缓存

脚本会自动缓存加载的数据，避免每次调用都重新解析文件：

- 首次加载时，文件会被解析并存储在 `/mnt/user-data/workspace/.data-analysis-cache/` 下的持久化 DuckDB 数据库中
- 缓存键是所有输入文件内容的 SHA256 哈希值 — 如果文件发生变化，会创建新缓存
- 后续对相同文件的调用将直接使用缓存数据库（接近瞬时启动）
- 缓存是透明的 — 无需额外参数

这在针对相同数据文件运行多个查询时特别有用（检查 → 查询 → 汇总）。

## 备注

- DuckDB 支持完整的 SQL，包括窗口函数、CTE、子查询和高级聚合
- Excel 日期列会被自动解析；使用 DuckDB 的日期函数（`DATE_TRUNC`、`EXTRACT` 等）
- 对于超大文件（100MB+），DuckDB 能够高效处理而无需将所有内容加载到内存中
- 包含空格的列名可以使用双引号访问：`"Column Name"`