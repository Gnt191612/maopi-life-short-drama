# 改完建模脚本后一键更新：重建指定人物（暂存演员表 assets/cast_next）→ 导出给审阅器 → 打开审阅器
# 用法（任意目录）：powershell -ExecutionPolicy Bypass -File D:\v11\viewer\更新模型.ps1 classB zhou
#        不带参数 = 全部 7 人；加 -NoBuild 只导出不重建（只改了 export_viewer.py 时用）
param([switch]$NoBuild, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Ids)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Blender = Join-Path $Root '.tools\blender\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $Root '.tools\blender_user'
$env:V11_CAST_DIR = Join-Path $Root 'assets\cast_next'
$sel = @(); if ($Ids) { $sel = @('--') + $Ids }
Push-Location $Root
try {
    if (-not $NoBuild) {
        Write-Host "[1/3] 重建人物 $($Ids -join ' ')"
        & $Blender -b --factory-startup -P blender\build_cast.py @sel
        if ($LASTEXITCODE -ne 0) { throw "重建失败（退出码 $LASTEXITCODE），看上面的报错" }
    }
    Write-Host '[2/3] 导出给审阅器'
    & $Blender -b --factory-startup -P blender\export_viewer.py @sel
    if ($LASTEXITCODE -ne 0) { throw "导出失败（退出码 $LASTEXITCODE），看上面的报错" }
} finally { Pop-Location }
Write-Host '[3/3] 打开审阅器（已开着的窗口按 F5 刷新即可）'
& (Join-Path $PSScriptRoot 'launch.ps1')
