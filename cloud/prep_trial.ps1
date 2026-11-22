# 上云前的本地准备（不花钱，全部在本机做完，开实例后只跑写实化）：
#   1) 七个角色按定稿流程重建到正式目录 assets\cast（build_cast + 贴标准长相照片 face_project）
#   2) 用新角色重拍、重渲试片片段（EEVEE 预览画质：白模画面 + 深度图）
#   3) 导出骨架图、按镜头打包成 dist\cloud_pack.zip（含标准长相照片 canon_<cid>.png、每个镜头首帧）
# 用法：powershell -ExecutionPolicy Bypass -File cloud\prep_trial.ps1 [-Segs s03_00,s03_01,s03_02,s03_03] [-SkipCast] [-SkipRender]
# 低优先级运行、一次一个 Blender（显卡至少留 1.5G）
param([string]$Segs = 's03_00,s03_01,s03_02,s03_03', [string[]]$Cast = @('lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB'),
      [switch]$SkipCast, [switch]$SkipRender)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$BL = Join-Path $Root '.tools\blender\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $Root '.tools\blender_user'; $env:PYTHONIOENCODING = 'utf-8'
$env:V11_MH_COMMUNITY = 'E:\v11_assets\mh_community'; $env:V11_NO_LINEUP = '1'
Remove-Item Env:V11_CAST_DIR -ErrorAction SilentlyContinue    # 正式目录 assets\cast（不是试验目录）
$Logs = Join-Path $Root 'build\logs'; New-Item -ItemType Directory -Force $Logs | Out-Null
function Low([string]$exe, [string[]]$a, [string]$log) {
    $p = Start-Process -FilePath $exe -ArgumentList $a -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WorkingDirectory $Root
    $p.PriorityClass = 'BelowNormal'; $p.WaitForExit(); return $p.ExitCode
}
$T0 = Get-Date
if (-not $SkipCast) {
    foreach ($c in $Cast) {
        Write-Host ("[角色] {0} 建模" -f $c)
        Low $BL @('-b', '--factory-startup', '-P', 'blender\build_cast.py', '--', $c) "$Logs\prep_cast_$c.log" | Out-Null
        if (-not (Select-String -Path "$Logs\prep_cast_$c.log" -Pattern 'CAST OK' -Quiet)) { throw "建模失败：$c（见 $Logs\prep_cast_$c.log）" }
        Write-Host ("[角色] {0} 贴标准长相照片" -f $c)
        Low $BL @('-b', "assets\cast\$c.blend", '--factory-startup', '-P', 'blender\face_project.py', '--', $c) "$Logs\prep_proj_$c.log" | Out-Null
        if (-not (Select-String -Path "$Logs\prep_proj_$c.log" -Pattern 'IDENTITY OK' -Quiet)) { throw "贴脸失败：$c（见 $Logs\prep_proj_$c.log）" }
    }
}
$env:V11_PREVIEW = '1'; $env:V11_ONLY = $Segs
if (-not $SkipRender) {
    foreach ($s in ($Segs -split ',')) { $d = Join-Path $Root "build\renders_preview\$s"; if (Test-Path $d) { Remove-Item -Recurse -Force $d } }   # 旧角色拍的画面作废，重拍
    Write-Host "[渲染] $Segs（重拍 + EEVEE 预览画质）"
    Low 'python' @('run_all.py') "$Logs\prep_render.log" | Out-Null
    Get-Content (Join-Path $Root 'build\logs\run_all.log') -Tail 8 -Encoding utf8
}
Write-Host '[打包] 骨架 + 镜头任务'
Low 'python' (@('cloud\pack_for_cloud.py', '--pose') + ($Segs -split ',')) "$Logs\prep_pack.log" | Out-Null
Get-Content "$Logs\prep_pack.log" -Tail 3 -Encoding utf8
Write-Host ('本地准备完成，用时 {0:N0} 分钟。下一步：开写实化实例 → cloud\session.ps1 -Stage probe' -f ((Get-Date) - $T0).TotalMinutes)
