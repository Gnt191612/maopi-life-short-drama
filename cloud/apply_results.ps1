# 云端结果一条命令替换进成片（本地）：
#   powershell -ExecutionPolicy Bypass -File cloud\apply_results.ps1 -From build\cloud_out\pulled_next\real [-Only s02_01_0852,s03_02_0001]
# 1) 把取回的 <任务id>.mp4 复制进 final_all\real，拆成逐帧（帧号 = 任务起始帧，和白模时间轴一致）
# 2) 检查帧数是否等于 task.json 里的帧数（不一致说明白模时间轴改过、云端用的是旧素材，会提示）
# 3) 多人镜头导出白模头部位置 → face_unify 逐帧统一五官
# 4) make_final：先 realign（节奏调整过的片段自动重对齐），再合成成片
param([Parameter(Mandatory = $true)][string]$From, [string]$Only = '', [switch]$NoFinal, [string]$Target = 'final_all')   # Target：替换进哪个结果目录（11-27 新方案用 final_fun，旧版 final_all 保留作对照和兜底）
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R
$dst = Join-Path $R "build\cloud_out\$Target\real"; $heads = Join-Path $R "build\cloud_out\$Target\heads"
$env:BLENDER_USER_RESOURCES = Join-Path $R '.tools\blender_user'; $env:PYTHONIOENCODING = 'utf-8'
$ids = @()
foreach ($m in Get-ChildItem $From -Filter *.mp4) {
    if ($m.BaseName -like '*_lips') { continue }   # 口型版另行处理：同名 <id>_lips.mp4 存在时用它代替 <id>.mp4
    $t = $m.BaseName; $lip = Join-Path $From ("{0}_lips.mp4" -f $t); if (Test-Path $lip) { $m = Get-Item $lip }; if ($Only -and ($Only -split ',') -notcontains $t) { continue }
    $tj = Join-Path $R "dist\cloud_pack\$t\task.json"; if (-not (Test-Path $tj)) { Write-Host "跳过（没有这个任务）：$t"; continue }
    $j = Get-Content $tj -Raw -Encoding utf8 | ConvertFrom-Json
    if (Test-Path "$dst\$t") { Remove-Item "$dst\$t" -Recurse -Force }
    Copy-Item $m.FullName "$dst\$t.mp4" -Force
    if ($t -match '^s07_0[13]_') {   # 回忆戏统一冷蓝调色（踩坑记录 42）
        $FF = & python -c "import config;print(config.FFMPEG)"
        & $FF -v error -y -i "$dst\$t.mp4" -vf "colorbalance=rs=-0.10:gs=-0.03:bs=0.14:rm=-0.08:bm=0.10:rh=-0.05:bh=0.06,eq=saturation=0.72:brightness=-0.035" -c:v libx264 -crf 14 -pix_fmt yuv420p "$dst\$t.g.mp4"; Move-Item "$dst\$t.g.mp4" "$dst\$t.mp4" -Force
    }
    & python cloud\pull_frames.py "$dst\$t.mp4" | Out-Null
    $n = (Get-ChildItem "$dst\$t" -Filter frame_*.png).Count
    if ($n -ne $j.n) { Write-Host "注意：$t 帧数 $n，任务应为 $($j.n)（白模时间轴可能改过，合成时会按时间轴截断或用白模补）" -ForegroundColor Yellow }
    if (@($j.characters).Count -ge 2) {
        & (Join-Path $R '.tools\blender\blender.exe') -b "build\shots\$($j.segment).blend" --factory-startup -P cloud\export_heads.py -- "$heads\$t.json" $j.frames[0] $j.frames[1] 2>$null | Out-Null
    }
    $ids += $t
}
if (-not $ids) { Write-Host '没有可替换的镜头'; exit }
Write-Host ("替换 {0} 个镜头：{1}" -f $ids.Count, ($ids -join ' '))
& python cloud\face_unify.py "build\cloud_out\$Target" @ids
if (-not $NoFinal) { & powershell -NoProfile -ExecutionPolicy Bypass -File cloud\make_final.ps1 -Result (Join-Path $R "build\cloud_out\$Target") }
