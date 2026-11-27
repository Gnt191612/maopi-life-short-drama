# 新方案试跑（本地一条命令，2026-11-27）：Wan2.2 Fun Control 白模动作控制 + LatentSync 口型同步，3 个代表镜头
#   powershell -ExecutionPolicy Bypass -File cloud\trial_fun.ps1 -Step report   # 开机后先跑：磁盘清单（只看不删）→ build\review\disk_report.txt
#   powershell -ExecutionPolicy Bypass -File cloud\trial_fun.ps1 -Step trial    # 装模型、重做 0577 首帧、生成 3 个镜头、对口型、取回、做新旧对比
# 镜头：s01_01_0577（宿舍全景多人+走动）、s02_01_1021（图书馆两人互动）、s06_01_0626（陈瑶说话特写，对口型）
# 结果：build\cloud_out\trial_fun\（新视频）+ build\review\trial_compare\<镜头>.mp4（左旧右新，带配音）
param([ValidateSet('report', 'trial', 'compare')][string]$Step = 'trial', [string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493,
      [string]$Res = '1024x576')
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
$ids = 's01_01_0577 s02_01_1021 s06_01_0626'
$dst = Join-Path $R 'build\cloud_out\trial_fun'; New-Item -ItemType Directory -Force $dst | Out-Null
function Up($files, $to) { & scp.exe @O -P $Port @files "${SshHost}:$to" }

if ($Step -eq 'report') {
    Up @('cloud\disk_report.sh') '/root/disk_report.sh'
    & ssh.exe @O -p $Port $SshHost 'bash /root/disk_report.sh > /dev/null 2>&1; cat /root/disk_report.txt' | Out-File -Encoding utf8 build\review\disk_report.txt
    Get-Content build\review\disk_report.txt -Encoding utf8
    exit
}
if ($Step -eq 'trial') {
    & python -c "import sys,json; sys.path.insert(0,'cloud'); import looks; json.dump(dict(look=looks.LOOK, look_en=looks.LOOK_EN, name=looks.NAME), open('cloud/looks_gen.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"
    & python cloud\shot_audio.py s06_01_0626 | Out-Null
    & python cloud\slim_pack.py ($ids -replace ' ', ',') dist\slim_trial.zip --no-anchors
    Up @('cloud\video_fun.py', 'cloud\lipsync.sh', 'cloud\setup_fun.sh', 'cloud\keyframes.py', 'cloud\comfy_run.py', 'cloud\looks.py', 'cloud\looks_gen.json', 'cloud\shard.py') '/root/v11_upload/scripts/'
    Up @('dist\slim_trial.zip') '/root/v11_upload/cloud_pack.zip'
    $sh = @'
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; IDS="__IDS__"; rm -f $OUT/DONE_TRIAL
rm -rf /root/v11cloud; mkdir -p /root/v11cloud; python3 -c "import zipfile; zipfile.ZipFile('/root/v11_upload/cloud_pack.zip').extractall('/root/v11cloud')"
bash $S/setup_fun.sh > $OUT/trial_setup.log 2>&1 || { echo SETUP_FAIL > $OUT/DONE_TRIAL; exit; }
( bash $S/lipsync.sh setup > $OUT/trial_lipsetup.log 2>&1 ) &                     # 口型环境和视频生成同时装
i=s01_01_0577; rm -f $OUT/kf/$i.png $OUT/kf/$i@*.png $OUT/kfbase_$i*.png $OUT/kfswap_$i*.png   # 首帧原来是白模质感，按 kf_hint + 重绘力度 2 重做
cd $S && python3 keyframes.py $PACK $i > $OUT/trial_keys.log 2>&1
python3 video_fun.py $PACK --only ${IDS// /,} --res __RES__ > $OUT/trial_fun.log 2>&1
python3 video_fun.py $PACK --only s06_01_0626 --res 832x480 --out /root/v11_out/fun_480 > $OUT/trial_fun480.log 2>&1   # 同一镜头低一档分辨率，给用户选清晰度/花费
wait
bash $S/lipsync.sh run $PACK s06_01_0626 > $OUT/trial_lips.log 2>&1
touch $OUT/DONE_TRIAL
'@
    $p = Join-Path $env:TEMP 'trial.sh'; [IO.File]::WriteAllText($p, $sh.Replace('__IDS__', $ids).Replace('__RES__', $Res).Replace("`r`n", "`n"))
    Up @($p) '/root/trial.sh'
    & ssh.exe @O -p $Port $SshHost 'nohup bash /root/trial.sh > /root/trial.log 2>&1 & echo QUEUED'
    # 等完成（每 2 分钟查一次，最多 3 小时），日志尾巴打出来方便看进度
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalHours -lt 3) {
        Start-Sleep 120
        $j = Start-Job { param($O, $H, $P) & ssh.exe @O -p $P $H 'ls /root/v11_out/DONE_TRIAL 2>/dev/null; cat /root/v11_out/DONE_TRIAL 2>/dev/null; tail -n 1 /root/v11_out/fun_progress.log 2>/dev/null' } -ArgumentList (, $O), $SshHost, $Port
        if (Wait-Job $j -Timeout 60) { $r = (Receive-Job $j) -join ' | ' } else { Stop-Job $j; $r = '（ssh 超时）' }; Remove-Job $j -Force
        Write-Host ("{0:HH:mm} {1}" -f (Get-Date), $r)
        if ($r -match 'SETUP_FAIL') { Write-Host '模型安装失败，看 trial_setup.log'; break }
        if ($r -match 'DONE_TRIAL') { break }
    }
    foreach ($t in ($ids -split ' ')) { & scp.exe @O -P $Port "${SshHost}:/root/v11_out/fun/$t.mp4" "$dst\" 2>$null }
    & scp.exe @O -P $Port "${SshHost}:/root/v11_out/lips/s06_01_0626.mp4" "$dst\s06_01_0626_lips.mp4" 2>$null
    & scp.exe @O -P $Port "${SshHost}:/root/v11_out/fun_480/s06_01_0626.mp4" "$dst\s06_01_0626_480.mp4" 2>$null
    & ssh.exe @O -p $Port $SshHost 'grep -h 完成 /root/v11_out/fun_progress.log' | Out-File -Encoding utf8 "$dst\speed.txt"   # 每个镜头用时，算全片花费
    & scp.exe @O -P $Port "${SshHost}:/root/v11_out/trial_*.log" "$dst\" 2>$null
    Get-ChildItem $dst | Select Name, Length | Format-Table -AutoSize
}
# 新旧对比：先给新版做和旧版一样的本地人脸统一（否则不公平），再左旧右新并排，带这一镜头的配音，方便看口型
$cmp = Join-Path $R 'build\review\trial_compare'; New-Item -ItemType Directory -Force $cmp | Out-Null
$FF = & python -c "import config;print(config.FFMPEG)"
$work = Join-Path $dst 'work'; Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force "$work\real", "$work\heads" | Out-Null
foreach ($t in ($ids -split ' ')) {
    $new = if (Test-Path "$dst\${t}_lips.mp4") { "$dst\${t}_lips.mp4" } else { "$dst\$t.mp4" }
    if (-not (Test-Path $new)) { continue }
    $j = Get-Content "dist\cloud_pack\$t\task.json" -Raw -Encoding utf8 | ConvertFrom-Json
    New-Item -ItemType Directory -Force "$work\real\$t" | Out-Null
    & $FF -v error -y -i $new -start_number $j.frames[0] "$work\real\$t\frame_%04d.png"
    if (Test-Path "build\cloud_out\final_all\heads\$t.json") { Copy-Item "build\cloud_out\final_all\heads\$t.json" "$work\heads\" }
}
$env:PYTHONIOENCODING = 'utf-8'; & python cloud\face_unify.py $work
foreach ($t in ($ids -split ' ')) {
    $old = "build\cloud_out\final_all\real\$t.mp4"; $new = "$work\real\$t.mp4"
    if (-not (Test-Path $new) -or -not (Test-Path $old)) { Write-Host "缺 $t 的新或旧视频"; continue }
    $voice = "dist\cloud_pack\$t\voice.wav"
    $vf = "[0:v]scale=960:540,setsar=1,drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='旧（图生视频）':x=20:y=20:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.5[a];[1:v]scale=960:540,setsar=1,drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='新（白模动作控制）':x=20:y=20:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.5[b];[a][b]hstack"
    if (Test-Path $voice) { & $FF -v error -y -i $old -i $new -i $voice -filter_complex $vf -map 2:a -c:v libx264 -crf 18 -c:a aac -shortest "$cmp\$t.mp4" }
    else { & $FF -v error -y -i $old -i $new -filter_complex $vf -c:v libx264 -crf 18 "$cmp\$t.mp4" }
    Write-Host "对比视频：$cmp\$t.mp4"
}
if (Test-Path "$dst\s06_01_0626_480.mp4") {   # 分辨率对比：旧版 | 新 832×480 | 新 1024×576（都不带口型，只比画质）
    $lab = { param($t) "scale=640:360,setsar=1,drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='$t':x=12:y=12:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5" }
    & $FF -v error -y -i build\cloud_out\final_all\real\s06_01_0626.mp4 -i "$dst\s06_01_0626_480.mp4" -i "$dst\s06_01_0626.mp4" -filter_complex "[0:v]$(& $lab '旧版')[a];[1:v]$(& $lab '新 832x480')[b];[2:v]$(& $lab '新 1024x576')[c];[a][b][c]hstack=3" -c:v libx264 -crf 18 "$cmp\s06_01_0626_分辨率对比.mp4"
    Write-Host "分辨率对比：$cmp\s06_01_0626_分辨率对比.mp4" }
if (Test-Path "$dst\speed.txt") { Get-Content "$dst\speed.txt" -Encoding utf8 }
Write-Host '== 音画同步客观检查（旧版 vs 新版，s06_01_0626）'
& python cloud\av_sync_check.py build\cloud_out\final_all s06_01_0626 2>$null | Select-Object -First 1
& python cloud\av_sync_check.py $work s06_01_0626 2>$null | Select-Object -First 1
Write-Host '试跑完成。看完对比视频再决定是否全片重做；记得关机（或等平台空闲 30 分钟自动关机）。'