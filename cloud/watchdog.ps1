# 看门狗：无人值守时每 5 分钟巡查一次，防止本地进程卡死、云端空转（2026-11-25：取回程序被一条 ssh 卡了 4 小时、
# 盯进度的进程卡死导致云端空等 40 分钟，用户要求自己做防范）。
#   1) 本地：pull_done 进程不在就重启；存活超过 10 分钟的 ssh/scp 视为卡死，直接结束
#   2) 云端（每次远程命令限时 60 秒）：GPU 占用、正在跑的队列/会话数、最近一次出视频的时间、ComfyUI 是否在线
#   3) 云端空闲但最后一批还没完成、或 40 分钟没有新视频、或 ComfyUI 掉线 → 写 build\logs\WATCHDOG_ALERT（附原因），由值守的 Claude 处理
# 用法：powershell -File cloud\watchdog.ps1 -LastDone DONE_9 [-SshHost ... -Port ...]；建 build\logs\STOP_WATCHDOG 停止
param([string]$LastDone = 'DONE_9', [string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent
$log = Join-Path $R 'build\logs\watchdog.log'; $alert = Join-Path $R 'build\logs\WATCHDOG_ALERT'
function L($m) { Add-Content $log -Encoding utf8 -Value ("{0:MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) }
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$Opt = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
function Rx([string]$c, [int]$Sec = 60) {
    $j = Start-Job -ScriptBlock { param($o, $p, $h, $c) & ssh.exe @o -p $p $h $c } -ArgumentList (,$Opt), $Port, $SshHost, $c
    if (Wait-Job $j -Timeout $Sec) { $r = Receive-Job $j; Remove-Job $j -Force; return $r }
    Stop-Job $j; Remove-Job $j -Force; return $null
}
$probe = @'
echo GPU $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
echo BUSY $(ps -eo args | grep -E "cloud_queue|chain[0-9]|session_realism|keyframes.py|video_run.py" | grep -v grep | wc -l)
echo LASTVID $(stat -c %Y $(ls -t /root/v11_out/real/*.mp4 2>/dev/null | head -1) 2>/dev/null || echo 0)
echo LASTKF $(stat -c %Y $(ls -t /root/v11_out/kf/*.png 2>/dev/null | head -1) 2>/dev/null || echo 0)
echo NOW $(date +%s)
echo COMFY $(curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8188/system_stats)
echo FINAL $(ls /root/v11_out/LASTDONE 2>/dev/null | wc -l)
'@
$tmp = Join-Path $env:TEMP 'watchdog_probe.sh'; $fails = 0
while (-not (Test-Path (Join-Path $R 'build\logs\STOP_WATCHDOG'))) {
    # 1) 本地
    foreach ($p in Get-CimInstance Win32_Process -Filter "Name='ssh.exe' OR Name='scp.exe'") {
        if ($p.CreationDate -lt (Get-Date).AddMinutes(-10)) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; L "结束卡死的 $($p.Name)（pid $($p.ProcessId)，启动于 $($p.CreationDate)）" }
    }
    if (-not (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pull_done\.ps1' })) {
        Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$R\cloud\pull_done.ps1`""; CurrentDirectory = $R } | Out-Null
        L '取回程序不在，已重启'
    }
    # 2) 云端
    [IO.File]::WriteAllText($tmp, $probe.Replace('LASTDONE', $LastDone).Replace("`r`n", "`n"))
    $up = Start-Job -ScriptBlock { param($o, $p, $h, $f) & scp.exe @o -P $p $f "${h}:/root/watchdog_probe.sh" } -ArgumentList (,$Opt), $Port, $SshHost, $tmp
    Wait-Job $up -Timeout 60 | Out-Null; Remove-Job $up -Force
    $o = Rx 'bash /root/watchdog_probe.sh'
    if (-not $o) {
        $fails++; L "连不上云端（连续 $fails 次）"
        if ($fails -ge 3) { Set-Content $alert -Encoding utf8 -Value ("{0:HH:mm} 连续 3 次连不上云端（实例可能被关机或网络断了）" -f (Get-Date)) }
    } else {
        $fails = 0; $v = @{}; foreach ($l in $o) { $a = -split $l; if ($a.Count -ge 2) { $v[$a[0]] = $a[1] } }
        $now = [long]$v['NOW']; $vid = [long]$v['LASTVID']; $kf = [long]$v['LASTKF']; $last = [Math]::Max($vid, $kf)
        $idleMin = if ($last) { [int](($now - $last) / 60) } else { -1 }
        L ("GPU {0}% 任务进程 {1} 最近产出 {2} 分钟前 ComfyUI {3} 最后一批完成 {4}" -f $v['GPU'], $v['BUSY'], $idleMin, $v['COMFY'], $v['FINAL'])
        $why = @()
        if ($v['FINAL'] -eq '1') { L '最后一批已完成，看门狗结束'; break }
        if ([int]$v['BUSY'] -eq 0) { $why += '云端没有任何任务进程，但最后一批还没完成（队列断了）' }
        if ($idleMin -ge 40) { $why += "已经 $idleMin 分钟没有新的关键帧或视频" }
        if ($v['COMFY'] -ne '200') { $why += "ComfyUI 不在线（$($v['COMFY'])）" }
        if ($why) { Set-Content $alert -Encoding utf8 -Value (("{0:HH:mm} " -f (Get-Date)) + ($why -join '；')); L ('警报：' + ($why -join '；')) }
    }
    Start-Sleep 300
}
L '看门狗退出'
