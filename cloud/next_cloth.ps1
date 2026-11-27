# 下次开机一条命令（2026-11-27 准备）：重做林晓穿成黑外套的两个镜头 s01_01_1016、s02_01_1116，以及渲染失败的 s01_01_0577（宿舍全景白模质感）、s05_01_0440（食堂方块凳）、s08_01_0288（陈瑶被画成中年女人）、s10_00_0787（多人、卡通树）
#   powershell -ExecutionPolicy Bypass -File cloud\next_cloth.ps1
# 上传最新脚本（keyframes.py 含 kf_hint/noswap、林晓体型描述）和素材包 → 云端排队做关键帧+视频 → 等完成标记 → 取回到 build\cloud_out\pulled_next\cloth
# 取回后：审查（衣服是深灰开襟卫衣、和前后镜头一致、体型偏胖）→ powershell -File cloud\apply_results.ps1 -From build\cloud_out\pulled_next\cloth → 记得关机
param([string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
$ids = 's01_01_1016 s02_01_1116 s01_01_0577 s05_01_0440 s08_01_0288 s10_00_0787'   # 衣服（2）+ 渲染失败（4，11-27 对齐审查）
& python -c "import sys,json; sys.path.insert(0,'cloud'); import looks; json.dump(dict(look=looks.LOOK, look_en=looks.LOOK_EN, name=looks.NAME), open('cloud/looks_gen.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"
& python cloud\slim_pack.py ($ids -replace ' ', ',') dist\slim_cloth.zip
& scp.exe @O -P $Port cloud\keyframes.py cloud\video_run.py cloud\comfy_run.py cloud\looks.py cloud\looks_gen.json "${SshHost}:/root/v11_upload/scripts/"
& scp.exe @O -P $Port dist\slim_cloth.zip "${SshHost}:/root/v11_upload/cloud_pack.zip"
$sh = @'
OUT=/root/v11_out; S=/root/v11_upload/scripts; IDS="__IDS__"
touch /root/v11_upload/cloud_pack.zip; rm -f $OUT/DONE_CLOTH
for i in $IDS; do rm -f $OUT/kf/$i.png $OUT/kf/$i@*.png $OUT/kfbase_$i*.png $OUT/kfswap_$i*.png; mkdir -p $OUT/old_cloth; mv -f $OUT/real/$i.mp4 $OUT/old_cloth/ 2>/dev/null; rm -rf $OUT/real/$i; done
export V11_KEYS_MAX=20000 V11_VIDEO_MAX=60000
bash $S/session_realism.sh keys $IDS > $OUT/session_cloth_keys.log 2>&1
bash $S/session_realism.sh video $IDS > $OUT/session_cloth_video.log 2>&1
touch $OUT/DONE_CLOTH
'@
$p = Join-Path $env:TEMP 'cloth.sh'; [IO.File]::WriteAllText($p, $sh.Replace('__IDS__', $ids).Replace("`r`n", "`n"))
& scp.exe @O -P $Port $p "${SshHost}:/root/cloth.sh"
& ssh.exe @O -p $Port $SshHost 'nohup bash /root/cloth.sh > /root/cloth.log 2>&1 & echo QUEUED'
& powershell -NoProfile -ExecutionPolicy Bypass -File cloud\wait_fetch.ps1 -Flag DONE_CLOTH -Ids ($ids -replace ' ', ',') -Dst build\cloud_out\pulled_next\cloth -Hours 4 -SshHost $SshHost -Port $Port
Write-Host '完成：审查 build\cloud_out\pulled_next\cloth 后运行 cloud\apply_results.ps1 -From build\cloud_out\pulled_next\cloth；记得去控制台关机。'
