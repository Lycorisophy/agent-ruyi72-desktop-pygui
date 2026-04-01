# 文件树技能脚本 (PowerShell)
# 显示目录的树形结构

param(
    [Parameter(Mandatory=$true)]
    [string]$Path,
    
    [Parameter(Mandatory=$false)]
    [int]$Depth = 3,
    
    [Parameter(Mandatory=$false)]
    [string]$Exclude = ""
)

$inputData = $input | ForEach-Object { $_ } | Out-String
if ($inputData) {
    try {
        $params = $inputData | ConvertFrom-Json
        $Path = if ($params.path) { $params.path } else { $Path }
        $Depth = if ($params.depth) { $params.depth } else { $Depth }
        $Exclude = if ($params.exclude) { $params.exclude } else { $Exclude }
    } catch {}
}

# 排除目录
$excludeSet = @(".git", "node_modules", "__pycache__", ".venv", "venv")
if ($Exclude) {
    $excludeSet += ($Exclude -split ",").Trim()
}

function Build-Tree {
    param(
        [string]$Path,
        [string]$Prefix = "",
        [int]$CurrentDepth = 0,
        [int]$MaxDepth = 3
    )
    
    if ($CurrentDepth -ge $MaxDepth) {
        return @()
    }
    
    $items = Get-ChildItem -Path $Path -ErrorAction SilentlyContinue | Sort-Object { -not $_.PSIsContainer }, Name
    $tree = @()
    $count = $items.Count
    $i = 0
    
    foreach ($item in $items) {
        $i++
        if ($excludeSet -contains $item.Name) {
            continue
        }
        
        $isLast = ($i -eq $count)
        $connector = if ($isLast) { "└── " } else { "├── " }
        
        $tree += "$Prefix$connector$($item.Name)"
        
        if ($item.PSIsContainer) {
            $extension = if ($isLast) { "    " } else { "│   " }
            $tree += Build-Tree -Path $item.FullName -Prefix "$Prefix$extension" -CurrentDepth ($CurrentDepth + 1) -MaxDepth $MaxDepth
        }
    }
    
    return $tree
}

$rootPath = $Path
if (-not (Test-Path $rootPath)) {
    $result = @{
        success = $false
        output = $null
        error = "路径不存在: $rootPath"
    }
    $result | ConvertTo-Json -Compress
    exit
}

if (-not (Test-Path $rootPath -PathType Container)) {
    $result = @{
        success = $false
        output = $null
        error = "不是目录: $rootPath"
    }
    $result | ConvertTo-Json -Compress
    exit
}

$tree = @((Resolve-Path $rootPath).Path)
$tree += Build-Tree -Path $rootPath -MaxDepth $Depth

$result = @{
    success = $true
    output = $tree -join "`n"
    metadata = @{ path = (Resolve-Path $rootPath).Path }
}

$result | ConvertTo-Json -Compress
