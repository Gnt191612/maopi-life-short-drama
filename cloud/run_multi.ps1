# 多实例并行写实化（本地运行）：同时操控 N 台实例，每台跑一份镜头（cloud/shard.py 按时长均衡分配，片头只在第 1 台）
# 用法：powershell -ExecutionPolicy Bypass -File cloud\run_multi.ps1 -Hosts "root@aaa.ssh.x-gpu.com:12345","root@bbb.ssh.x-gpu.com:23456" [-Stage final] [-MaxHours 6]
#   每台实例都要用同一个镜像（ComfyUI + 同样的工作流），控制台「SSH」里看地址和端口
#   任意一台跑完会立刻提醒「关这一台」；全部完成后：cloud\make_final.ps1 -Result <各台结果目录…>
param([Parameter(Mandatory = $true)][string[]]$Hosts, [string]$Stage = 'final', [double]$MaxHours = 0, [double]$Rate = 1.89)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent; $N = $Hosts.Count
$Logs = Join-Path $Root 'build\logs'; New-Item -ItemType Directory -Force $Logs | Out-Null
Write-Host "镜头分配（共 $N 台）："; & python (Join-Path $Root 'cloud\shard.py') (Join-Path $Root 'dist\cloud_pack') $N
$procs = @()
for ($i = 1; $i -le $N; $i++) {
    $h, $port = $Hosts[$i - 1] -split ':(?=\d+$)'
    $log = Join-Path $Logs "session_s$i.log"
    $a = @('-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Root 'cloud\session.ps1'), '-SshHost', $h, '-Port', $port, '-Stage', $Stage, '-Shard', "$i/$N", '-Rate', $Rate, '-MaxHours', $MaxHours)
    $p = Start-Process powershell -ArgumentList $a -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    $procs += [pscustomobject]@{ I = $i; Host = $h; P = $p; Log = $log; Done = $false }
    Write-Host "实例 $i 已启动（$h），日志 $log"
    Start-Sleep 5   # 错开上传，避免同时挤占上行带宽
}
$T0 = Get-Date
while ($procs | Where-Object { -not $_.Done }) {
    Start-Sleep 60
    foreach ($x in $procs | Where-Object { -not $_.Done }) {
        $tail = Get-Content $x.Log -Tail 1 -Encoding utf8 -ErrorAction SilentlyContinue
        if ($x.P.HasExited) {
            $x.Done = $true
            Write-Host ("[{0:HH:mm}] 实例 {1} 完成 >>> 现在去控制台关掉这台（{2}）<<<" -f (Get-Date), $x.I, $x.Host) -ForegroundColor Yellow
            Get-Content $x.Log -Tail 4 -Encoding utf8
        } elseif ($tail) { Write-Host ("[{0:HH:mm}] 实例 {1}：{2}" -f (Get-Date), $x.I, $tail.Trim()) }
    }
}
$hrs = ((Get-Date) - $T0).TotalHours
Write-Host ('全部完成，用时 {0:N1} 小时，约 ¥{1:N1}（{2} 台）。结果目录：' -f $hrs, ($hrs * $Rate * $N), $N)
Get-ChildItem (Join-Path $Root 'build\cloud_out') -Directory | Where-Object { $_.Name -like "${Stage}_*_s*" } | Sort-Object LastWriteTime | Select-Object -Last $N | ForEach-Object { '  ' + $_.FullName }
Write-Host '下一步：cloud\make_final.ps1 -Result <上面这些目录，用逗号隔开>'
