# 人物精修一轮（本地）：重建角色 → 贴标准长相照片 → 渲染对比图（照片 / 带皮肤 / 素模，正面·3/4·侧面）
# 用法：powershell -ExecutionPolicy Bypass -File blender\tests\identity_round.ps1 -Cid mom -Tag mom5 [-Back] [-Body] [-CamDz -0.04]
#   -Back  拍后脑勺（back34/back/side）；-Body 额外出全身检查图（正/3/4/侧/背，带衣服与 -NoCloth 两套）
# 输出：build\face_fit\<Cid>_<Tag>.png（对比总图）、build\face_fit\<Tag>\*.png
# 试验目录 build\face_fit\cast（V11_CAST_DIR），不影响正式的 assets\cast；定稿后用 cloud\prep_trial.ps1 重建到正式目录
param([Parameter(Mandatory = $true)][string]$Cid, [Parameter(Mandatory = $true)][string]$Tag, [switch]$Back, [switch]$Body, [double]$CamDz = 0)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent; Push-Location $Root
$BL = Join-Path $Root '.tools\blender\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $Root '.tools\blender_user'; $env:PYTHONIOENCODING = 'utf-8'
$env:V11_CAST_DIR = Join-Path $Root 'build\face_fit\cast'; $env:V11_NO_LINEUP = '1'
$Logs = Join-Path $Root 'build\logs'; New-Item -ItemType Directory -Force $Logs, $env:V11_CAST_DIR | Out-Null
function Low([string[]]$a, [string]$log) {   # 低优先级、一次一个 Blender（显卡至少留 1.5G）
    $p = Start-Process -FilePath $BL -ArgumentList $a -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WorkingDirectory $Root
    $p.PriorityClass = 'BelowNormal'; $p.WaitForExit()
}
try {
    Low @('-b', '--factory-startup', '-P', 'blender\build_cast.py', '--', $Cid) "$Logs\round_build.log"
    if (-not (Select-String "$Logs\round_build.log" -Pattern 'CAST OK' -Quiet)) { Get-Content "$Logs\round_build.log.err" -Tail 20; throw "建模失败（$Logs\round_build.log）" }
    $blend = Join-Path $env:V11_CAST_DIR "$Cid.blend"
    $idp = if (Test-Path "characters\$Cid\$Cid.png") { "characters\$Cid" } else { "assets\identity" }   # 人物库优先
    if (Test-Path "$idp\$Cid.png") {
        Low @('-b', $blend, '--factory-startup', '-P', 'blender\face_project.py', '--', $Cid) "$Logs\round_proj.log"
        if (-not (Select-String "$Logs\round_proj.log" -Pattern 'IDENTITY OK' -Quiet)) { Get-Content "$Logs\round_proj.log.err" -Tail 20; throw "贴脸失败（$Logs\round_proj.log）" }
    }
    $yaw = '0'; $fj = "$idp\${Cid}_face_fit.json"
    if (Test-Path $fj) { $yaw = [string]((Get-Content $fj -Raw -Encoding utf8 | ConvertFrom-Json).yaw_deg) }
    if ($Back) { $env:V11_BACK = '1' } else { Remove-Item Env:V11_BACK -ErrorAction SilentlyContinue }
    if ($CamDz -ne 0) { $env:V11_CAM_DZ = [string]$CamDz }
    Low @('-b', '--factory-startup', '-P', 'blender\tests\identity_compare.py', '--', $blend, $Cid, "build\face_fit\$Tag", $yaw) "$Logs\round_cmp.log"
    Remove-Item Env:V11_BACK, Env:V11_CAM_DZ -ErrorAction SilentlyContinue
    if (-not $Back) { & python blender\tests\identity_sheet.py $Cid "build\face_fit\$Tag" "build\face_fit\${Cid}_$Tag.png" }
    if ($Body) {
        Low @('-b', '--factory-startup', '-P', 'blender\tests\body_compare.py', '--', $blend, $Cid, "build\face_fit\body_$Tag") "$Logs\round_body.log"
        $env:V11_NOCLOTH = '1'; Low @('-b', '--factory-startup', '-P', 'blender\tests\body_compare.py', '--', $blend, $Cid, "build\face_fit\body_${Tag}_nocloth") "$Logs\round_body.log"; Remove-Item Env:V11_NOCLOTH
    }
    Write-Host "完成：build\face_fit\$Tag"
} finally { Pop-Location }
