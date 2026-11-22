# 写实化一键会话（本地运行）：上传脚本与素材包 → 云端后台跑指定阶段 → 盯进度 → 下载结果 → 提醒关机
# 用法：powershell -ExecutionPolicy Bypass -File cloud\session.ps1 -SshHost root@xxx.ssh.x-gpu.com -Port 12345 -Stage probe
#   -Stage probe | keys | test | video | all     （顺序建议：probe → 填 video_map.json → test → 看效果 → all）
#   -Only s03_01_0001,s03_02          只跑这些镜头（任务 id 前缀）
#   -Rate 1.89                        每小时价格（元），用来估算这次花了多少
#   -IdleMin 20                       日志这么久没动静就判定卡住：中止云端任务、下载已有结果、提醒关机
param([Parameter(Mandatory = $true)][string]$SshHost, [Parameter(Mandatory = $true)][int]$Port,
      [ValidateSet('probe', 'keys', 'test', 'video', 'all')][string]$Stage = 'probe',
      [string]$Only = '', [double]$Rate = 1.89, [int]$IdleMin = 20)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$Opt = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ServerAliveInterval=30')
function R([string]$cmd) { & ssh.exe @Opt -p $Port $SshHost $cmd }
$T0 = Get-Date
Push-Location $Root
try {
    Write-Host "[1/4] 连接 $SshHost"
    R "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; df -h /root | tail -1"
    Write-Host '[2/4] 上传脚本（几 KB）'
    $tgz = Join-Path $env:TEMP 'v11_scripts.tgz'
    & tar.exe -czf $tgz -C cloud comfy_run.py looks.py probe_comfy.py keyframes.py video_run.py video_map.json session_realism.sh
    R 'mkdir -p /root/v11_upload/scripts /root/v11_out'
    & scp.exe @Opt -P $Port $tgz "${SshHost}:/root/v11_upload/scripts.tgz"
    R 'tar -xzf /root/v11_upload/scripts.tgz -C /root/v11_upload/scripts && sed -i "s/\r$//" /root/v11_upload/scripts/*.sh'
    $zip = Join-Path $Root 'dist\cloud_pack.zip'
    if ($Stage -ne 'probe') {
        if (-not (Test-Path $zip)) { throw '没有 dist\cloud_pack.zip：先在本地跑 cloud\prep_trial.ps1' }
        $local = (Get-Item $zip).Length; $remote = (R "stat -c %s /root/v11_upload/cloud_pack.zip 2>/dev/null || echo 0") -as [long]
        if ($local -ne $remote) {
            Write-Host ('    上传素材包 {0:N1} MB（上行慢，约 {1:N0} 秒）' -f ($local / 1MB), ($local / 1MB / 0.35))
            & scp.exe @Opt -P $Port $zip "${SshHost}:/root/v11_upload/cloud_pack.zip"
        } else { Write-Host '    素材包已在云端（大小一致），跳过上传' }
    }
    Write-Host "[3/4] 云端后台运行阶段 $Stage"
    $pre = ($Only -split ',' | Where-Object { $_ }) -join ' '
    R "rm -f /root/v11_out/DONE_$Stage; nohup bash /root/v11_upload/scripts/session_realism.sh $Stage $pre > /root/v11_out/session_$Stage.log 2>&1 &"
    $last = ''; $lastChange = Get-Date
    while ($true) {
        Start-Sleep -Seconds 30
        $st = R "tail -4 /root/v11_out/session_$Stage.log; tail -2 /root/v11_out/video_progress.log 2>/dev/null; ls /root/v11_out/DONE_$Stage 2>/dev/null"
        $txt = ($st -join "`n")
        if ($txt -ne $last) { Write-Host ("  [{0:HH:mm:ss}] " -f (Get-Date)) ($st | Select-Object -Last 3 | Out-String).Trim(); $last = $txt; $lastChange = Get-Date }
        if ($txt -match "DONE_$Stage") { break }
        if (((Get-Date) - $lastChange).TotalMinutes -gt $IdleMin) {
            Write-Host "!! $IdleMin 分钟没有进展，判定卡住：中止云端任务" -ForegroundColor Red
            R "pkill -f keyframes.py; pkill -f video_run.py; cd /root/v11_out && tar -czf /root/v11_result_$Stage.tgz --exclude=vtmp probe.* kf real *.log 2>/dev/null; touch /root/v11_out/DONE_$Stage"
            break
        }
    }
    Write-Host '[4/4] 下载结果'
    $dst = Join-Path $Root ("build\cloud_out\{0}_{1:MMdd_HHmm}" -f $Stage, (Get-Date)); New-Item -ItemType Directory -Force $dst | Out-Null
    & scp.exe @Opt -P $Port "${SshHost}:/root/v11_result_$Stage.tgz" "$dst\result.tgz"
    & scp.exe @Opt -P $Port "${SshHost}:/root/v11_out/session_$Stage.log" "$dst\"
    & tar.exe -xzf "$dst\result.tgz" -C $dst; Remove-Item "$dst\result.tgz"
    Write-Host "结果在 $dst"
} finally {
    Pop-Location
    $min = ((Get-Date) - $T0).TotalMinutes
    Write-Host ('本次会话 {0:N0} 分钟，约 ¥{1:N2}（按 ¥{2}/时；开机等待时间另计）' -f $min, ($min / 60 * $Rate), $Rate) -ForegroundColor Yellow
    Write-Host '>>> 如果接下来没有马上要跑的阶段，现在就去控制台关机（只释放 GPU，磁盘保留）<<<' -ForegroundColor Yellow
}
