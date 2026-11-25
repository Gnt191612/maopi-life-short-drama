# 逐步取回：powershell -File cloud\pull_done.ps1 [-SshHost root@xxx -Port 12345]；建 build\logs\STOP_PULL 停止
# 逐步取回已经审查没有异议的写实视频（2026-11-25 用户：拍完全片后要尽快关机）：每 10 分钟查一次云端 real/*.mp4，
# 不在重跑名单里（post_final_tasks / drift_tasks / redo_tasks / patch_v*_tasks）的就下载到 build\cloud_out\pulled\real 并拆成逐帧
param([string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent   # 仓库根目录（原来写死 D:\v11）
$log = "$R\build\logs\pull_done.log"
function L($m) { Add-Content $log -Encoding utf8 -Value ("{0:MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) }
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$Opt = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20')
$dst = "$R\build\cloud_out\pulled\real"; New-Item -ItemType Directory -Force $dst | Out-Null
$dst2 = "$R\build\cloud_out\pulled_rerun\real"; New-Item -ItemType Directory -Force $dst2 | Out-Null
$RERUN0 = [DateTimeOffset]::new([datetime]'2026-11-25 08:40').ToUnixTimeSeconds()
while (-not (Test-Path "$R\build\logs\STOP_PULL")) {
    $skip = @{}
    foreach ($f in @('post_final_tasks.txt', 'drift_tasks.txt', 'redo_tasks.txt') + @(Get-ChildItem "$R\build\logs\patch_v*_tasks.txt" -ErrorAction SilentlyContinue | ForEach-Object Name)) {
        $p = Join-Path "$R\build\logs" $f
        if (Test-Path $p) { foreach ($i in ((Get-Content $p) -join ',' -split ',')) { if ($i) { $skip[$i.Trim()] = 1 } } }
    }
    $redo = @{}; if (Test-Path "$R\build\logs\redo_tasks.txt") { foreach ($i in ((Get-Content "$R\build\logs\redo_tasks.txt") -join ',' -split ',')) { if ($i) { $redo[$i.Trim()] = 1 } } }
    $ls = & ssh.exe @Opt -p $Port $SshHost 'cd /root/v11_out/real 2>/dev/null && ls -l --time-style=+%s *.mp4'
    $new = @()
    foreach ($line in $ls) {
        $c = -split $line; if ($c.Count -lt 7) { continue }   # ls -l --time-style=+%s：权限 链接 用户 组 大小 时间戳 文件名
        $name = $c[-1]; $size = [long]$c[4]; $id = $name -replace '\.mp4$', ''
        $mt = [long]$c[5]
        $to = $dst
        if ($redo[$id]) { continue }   # 已判不合格、等细分重拍的，不取
        if ($skip[$id]) { if ($mt -lt $RERUN0) { continue }; $to = $dst2 }   # 重跑名单里的镜头：只取补跑开始（08:40）之后新生成的，放 pulled_rerun 等审查
        $lp = Join-Path $to $name
        if ((Test-Path $lp) -and (Get-Item $lp).Length -eq $size) { continue }
        & scp.exe @Opt -P $Port "${SshHost}:/root/v11_out/real/$name" $lp
        if ((Test-Path $lp) -and (Get-Item $lp).Length -eq $size) { $new += $lp }
    }
    if ($new) {
        & python "$R\cloud\pull_frames.py" @new
        L ("取回 {0} 个：{1}" -f $new.Count, (($new | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) }) -join ','))
    }
    Start-Sleep 300
}
L '结束'