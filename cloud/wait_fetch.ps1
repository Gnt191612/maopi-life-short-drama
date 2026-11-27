# 等云端某轮完成标记出现后取回指定镜头（本地后台运行；每条 ssh/scp 都有心跳和硬超时，不会卡死）
#   powershell -File cloud\wait_fetch.ps1 -Flag DONE_R8 -Ids s07_00_0171,s10_00_0102 -Dst build\cloud_out\pulled_next\real8 [-Hours 6]
param([Parameter(Mandatory = $true)][string]$Flag, [Parameter(Mandatory = $true)][string]$Ids, [Parameter(Mandatory = $true)][string]$Dst,
      [double]$Hours = 6, [string]$SshHost = 'root@tdtjxa8cdyzuands.ssh.x-gpu.com', [int]$Port = 49855)
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R
$k = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $k, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
New-Item -ItemType Directory -Force $Dst | Out-Null
$t0 = Get-Date; $done = $false
while (((Get-Date) - $t0).TotalHours -lt $Hours) {
    $j = Start-Job { param($O, $H, $P, $F) & ssh.exe @O -p $P $H "ls /root/v11_out/$F 2>/dev/null" } -ArgumentList (, $O), $SshHost, $Port, $Flag
    if (Wait-Job $j -Timeout 60) { $r = (Receive-Job $j) -join ' ' } else { Stop-Job $j; $r = '' }; Remove-Job $j -Force
    if ($r -match $Flag) { $done = $true; break }
    Start-Sleep 120
}
"$Flag=$done $(Get-Date -f HH:mm)"
$list = $Ids -split ','
foreach ($t in $list) {
    $j = Start-Job { param($O, $H, $P, $t, $d) & scp.exe @O -P $P "${H}:/root/v11_out/real/$t.mp4" "$d\" } -ArgumentList (, $O), $SshHost, $Port, $t, (Resolve-Path $Dst).Path
    if (-not (Wait-Job $j -Timeout 300)) { Stop-Job $j; "取回超时 $t" }; Remove-Job $j -Force
}
"取回 $((Get-ChildItem $Dst -Filter *.mp4).Count)/$($list.Count)：$(Get-Date -f HH:mm)"
