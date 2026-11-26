# 下一轮开机一条命令（2026-11-25 夜准备）：实例开机后运行
#   powershell -ExecutionPolicy Bypass -File cloud\next_round.ps1 [-SshHost root@xxx -Port 12345]
# 1) 取回云端磁盘上已做好、还没取回的 8 个镜头（合并批次里的锚点版）→ build\cloud_out\pulled_next\real（待审查）
# 2) 用双参考编辑（edit_ref.py，图2=人物库标准照）改陈瑶 2 个镜头、林母 1 个镜头的关键帧和锚点图，再生成视频
# 3) 取回这 3 个镜头 → 同目录；之后由人审查，合格的复制进 final_all\real，跑 face_unify.py、make_final.ps1
# 全程在云端排队执行，本地只上传脚本和取结果；跑完记得关机
param([string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
$dst = Join-Path $R 'build\cloud_out\pulled_next\real'; New-Item -ItemType Directory -Force $dst | Out-Null
$fetch8 = 's03_03_0001 s06_01_0178 s06_01_0446 s07_00_0469 s07_01_0023 s07_04_0033 s07_05_0001 s08_01_0226' -split ' '
foreach ($t in $fetch8) { & scp.exe @O -P $Port "${SshHost}:/root/v11_out/real/$t.mp4" "$dst\" 2>$null }
Write-Host ("取回 {0} 个待审查镜头 → {1}" -f (Get-ChildItem $dst -Filter *.mp4).Count, $dst)
# 上传脚本和人物库标准照（图2）
& scp.exe @O -P $Port cloud\edit_ref.py cloud\comfy_run.py "${SshHost}:/root/v11_upload/scripts/"
& scp.exe @O -P $Port dist\cloud_pack\refs\canon_chen.jpg dist\cloud_pack\refs\canon_mom.jpg "${SshHost}:/root/ComfyUI/input/"
& python cloud\slim_pack.py s03_02_0001,s02_01_0852,s02_01_1021 dist\slim_next.zip
& scp.exe @O -P $Port dist\slim_next.zip "${SshHost}:/root/v11_upload/cloud_pack.zip"
$sh = @'
OUT=/root/v11_out; S=/root/v11_upload/scripts; INP=/root/ComfyUI/input
touch /root/v11_upload/cloud_pack.zip
cd $OUT/kf && for f in orig_*.png; do cp -f $f ${f#orig_}; done           # 陈瑶：恢复编辑前的原始关键帧
rm -f $OUT/kf/s03_02_0001.png $OUT/kf/s03_02_0001@*.png                    # 林母：上次被拼图覆盖，重新生成
export V11_KEYS_MAX=20000 V11_VIDEO_MAX=60000
bash $S/session_realism.sh keys s03_02_0001 > $OUT/session_next_keys.log 2>&1
cd $S
edit() { id=$1; ref=$2; inst=$3
  for f in $OUT/kf/$id.png $OUT/kf/$id@*.png; do
    [ -f "$f" ] || continue; b=$(basename $f .png); cp -n $f $OUT/kf/orig_$b.png; cp $f $INP/edit_$b.png
    r=$(python3 edit_ref.py edit_$b.png $ref ref_$b "$inst" 11 | grep SAVED | awk '{print $2}')
    [ -n "$r" ] && cp $r $f && echo "EDITED $f"
  done; rm -rf $OUT/real/$id $OUT/real/$id.mp4; }
edit s03_02_0001 canon_mom.jpg "把图1中女士的发型改成图2这位女士的发型（黑色微卷波浪短发）；图1中她的五官、表情、服装、手机、姿势、背景、光线和构图全部保持不变"
CH="把图1中戴眼镜的男生改成图2这个人的样子：高瘦、鹅蛋脸、浅金色圆框眼镜、黑色中分刘海短发、白衬衫黑长裤；图1中另一个穿深灰色卫衣的男生、两人的位置、姿势、背景、光线和构图全部保持不变"
edit s02_01_0852 canon_chen.jpg "$CH"; edit s02_01_1021 canon_chen.jpg "$CH"
bash $S/session_realism.sh video s03_02_0001 s02_01_0852 s02_01_1021 > $OUT/session_next_video.log 2>&1
touch $OUT/DONE_NEXT
'@
$p = Join-Path $env:TEMP 'next_round.sh'; [IO.File]::WriteAllText($p, $sh.Replace("`r`n", "`n"))
& scp.exe @O -P $Port $p "${SshHost}:/root/next_round.sh"
& ssh.exe @O -p $Port $SshHost 'nohup bash /root/next_round.sh > /root/next_round.log 2>&1 & echo QUEUED'
# 等完成再取回（每分钟查一次，最多 90 分钟）
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep 60
    $r = & ssh.exe @O -p $Port $SshHost 'ls /root/v11_out/DONE_NEXT 2>/dev/null'
    if ($r -match 'DONE_NEXT') { break }
}
foreach ($t in 's03_02_0001', 's02_01_0852', 's02_01_1021') { & scp.exe @O -P $Port "${SshHost}:/root/v11_out/real/$t.mp4" "$dst\" 2>$null }
& scp.exe @O -P $Port "${SshHost}:/root/v11_out/kf/s02_01_0852.png" "${SshHost}:/root/v11_out/kf/s03_02_0001.png" "$dst\" 2>$null
& python cloud\pull_frames.py (Get-ChildItem $dst -Filter *.mp4).FullName | Out-Null
Write-Host "完成：$dst 里是待审查的镜头和改过的关键帧；审查合格后运行：powershell -File cloud\apply_results.ps1 -From build\cloud_out\pulled_next\real（可加 -Only 只替换合格的）。记得去控制台关机。"
