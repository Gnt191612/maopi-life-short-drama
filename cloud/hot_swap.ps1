# 云端运行中热替换：powershell -File cloud\hot_swap.ps1 -TasksFile build\logs\patch_v9_tasks.txt [-SshHost ... -Port ...]
# 云端运行中热替换补拍过的镜头素材：覆盖 /root/v11cloud/cloud_pack/<id>/，删掉这些镜头已有的关键帧和视频。
# 还没轮到的镜头会直接用新素材生成；已经做过关键帧的记进 post_final_tasks.txt，全片结束后补一小轮（post_chain.ps1）
param([string]$TasksFile, [string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent   # 仓库根目录（原来写死 D:\v11）
Set-Location $R
$log = "$R\build\logs\hot_swap.log"
function L($m) { Add-Content $log -Encoding utf8 -Value ("{0:MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) }
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$Opt = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=30', '-o', 'ConnectTimeout=20')
$ids = ((Get-Content $TasksFile -Raw).Trim() -split ',') | Where-Object { $_ -and (Test-Path "dist\cloud_pack\$_") }
if (-not $ids) { L "没有要替换的镜头：$TasksFile"; exit }
$tgz = Join-Path $env:TEMP 'v11_swap.tgz'
& tar.exe -czf $tgz -C dist\cloud_pack @ids
& scp.exe @Opt -P $Port $tgz "${SshHost}:/root/v11_upload/swap.tgz"
$cmd = 'cd /root/v11cloud/cloud_pack && for i in ' + ($ids -join ' ') + '; do rm -rf $i; done && tar -xzf /root/v11_upload/swap.tgz && for i in ' + ($ids -join ' ') + '; do grep -q "\"$i\"" manifest.json || echo NEEDPOST $i; if [ -f /root/v11_out/kf/$i.png ]; then echo NEEDPOST $i; rm -f /root/v11_out/kf/$i.png; fi; rm -rf /root/v11_out/real/$i /root/v11_out/real/$i.mp4; done; echo SWAPPED'
$o = & ssh.exe @Opt -p $Port $SshHost $cmd
$need = @($o | Where-Object { $_ -match '^NEEDPOST ' } | ForEach-Object { ($_ -split ' ')[1] })
if ($need) { Add-Content "$R\build\logs\post_final_tasks.txt" -Value ($need -join ',') -Encoding ascii }
L ("替换 {0} 个镜头（{1}）；已做过关键帧、需全片后补跑 {2} 个；{3}" -f $ids.Count, $TasksFile, $need.Count, ($o | Select-Object -Last 1))