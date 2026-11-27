# MiniMax H3 方案试跑（本地一条命令，2026-11-27 用户确认选型）：H3 + Fun ControlNet Union（白模姿态 0.7 + 深度 0.3）+ 口型同步
#   powershell -ExecutionPolicy Bypass -File cloud\trial_h3.ps1 -Step report   # 开机后先跑：磁盘清单 + H3 在镜像里的情况（只看不删）
#   powershell -ExecutionPolicy Bypass -File cloud\trial_h3.ps1 -Step trial    # 装缺的模型 → 重做 0577 首帧 → H3 生成 3 个镜头 + 2 个对照版 → 口型 → 取回 → 对比
# 镜头：s01_01_0577（宿舍全景多人走动）、s02_01_1021（图书馆两人互动）、s06_01_0626（陈瑶说话特写）
# 对照版（都是 s06_01_0626）：turbo 4 步（看快 5 倍画质掉多少，决定全片用哪档）、带参考配音（看 H3 能不能自己对上口型，能的话省掉 LatentSync）
# 结果：build\cloud_out\trial_h3\ ；对比视频 build\review\trial_compare\ （左旧右新，带配音）；每镜头用时 speed.txt（算全片花费）
param([ValidateSet('report', 'trial', 'compare')][string]$Step = 'trial', [string]$SshHost = 'root@tdtjxa8cdyzuands.ssh.x-gpu.com', [int]$Port = 49855,
      [string]$Res = '1344x768')
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R; $env:PYTHONIOENCODING = 'utf-8'
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
$ids = 's06_01_0260 s06_01_0446 s06_01_0626'   # 第二幕宿舍连续 3 个镜头（陈瑶和林晓三句来回对话 B10/B11/B12），拼起来看衔接
$dst = Join-Path $R 'build\cloud_out\trial_h3'; New-Item -ItemType Directory -Force $dst | Out-Null
function Ssh1($cmd, $sec = 90) {
    $j = Start-Job { param($O, $H, $P, $c) & ssh.exe @O -p $P $H $c } -ArgumentList (, $O), $SshHost, $Port, $cmd
    if (Wait-Job $j -Timeout $sec) { $r = Receive-Job $j } else { Stop-Job $j; $r = $null }; Remove-Job $j -Force; return $r
}
function Get1($src, $to) { & scp.exe @O -P $Port "${SshHost}:$src" $to 2>$null }

if ($Step -eq 'report') {
    & scp.exe @O -P $Port cloud\disk_report.sh cloud\probe_h3.sh "${SshHost}:/root/"
    Ssh1 'bash /root/disk_report.sh >/dev/null 2>&1; bash /root/probe_h3.sh >/dev/null 2>&1; echo ok' 600 | Out-Null
    Get1 '/root/disk_report.txt' 'build\review\disk_report.txt'; Get1 '/root/h3_probe.txt' 'build\review\h3_probe.txt'
    Get-Content build\review\disk_report.txt, build\review\h3_probe.txt -Encoding utf8
    exit
}
$cmp0 = Join-Path $R 'build\review\trial_compare'; New-Item -ItemType Directory -Force $cmp0 | Out-Null
if ($Step -eq 'trial') {
    & python -c "import sys,json; sys.path.insert(0,'cloud'); import looks; json.dump(dict(look=looks.LOOK, look_en=looks.LOOK_EN, name=looks.NAME), open('cloud/looks_gen.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"
    & python cloud\shot_audio.py s06_01_0260 s06_01_0446 s06_01_0626 | Out-Null
    & python cloud\slim_pack.py ($ids -replace ' ', ',') dist\slim_trial_h3.zip --no-anchors --pose
    Ssh1 'mkdir -p /root/v11_upload/scripts /root/v11_out/kf /root/ComfyUI/input; pkill -f trial_h3.sh; pkill -f full_fun.sh; echo dirs' 60 | Out-Null   # 新实例没有这些目录（11-27 新建 TDTJ 时第一次上传失败）
    & scp.exe @O -P $Port cloud\video_h3.py cloud\h3_prompt.py cloud\disk_guard.sh cloud\cleanup_auto.sh cloud\setup_h3.sh cloud\lipsync.sh cloud\keyframes.py cloud\comfy_run.py cloud\looks.py cloud\looks_gen.json cloud\shard.py "${SshHost}:/root/v11_upload/scripts/"
    & scp.exe @O -P $Port dist\slim_trial_h3.zip "${SshHost}:/root/v11_upload/cloud_pack.zip"
    & scp.exe @O -P $Port -r dist\moss_trial cloud\tts_moss.py cloud\setup_moss.sh "${SshHost}:/root/v11_upload/"   # MOSS-TTSD 对话配音对比（用户 11-27 同意）
    $sh = @'
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; rm -f $OUT/DONE_TRIAL
rm -rf /root/v11cloud; mkdir -p /root/v11cloud; python3 -c "import zipfile; zipfile.ZipFile('/root/v11_upload/cloud_pack.zip').extractall('/root/v11cloud')"
cp -f $PACK/refs/*.jpg /root/ComfyUI/input/ 2>/dev/null
bash $S/disk_guard.sh > $OUT/trial_disk.log 2>&1 || { echo DISK_LOW > $OUT/DONE_TRIAL; exit; }   # 磁盘体检：不够就先清中间产物，仍不够就停下等用户（踩坑记录 62）
bash $S/setup_h3.sh > $OUT/trial_setup.log 2>&1 || { echo SETUP_FAIL > $OUT/DONE_TRIAL; exit; }
( bash $S/lipsync.sh setup > $OUT/trial_lipsetup.log 2>&1; bash /root/v11_upload/setup_moss.sh > $OUT/trial_mosssetup.log 2>&1 ) &   # 口型、对话配音环境和视频生成同时装
cd $S && python3 keyframes.py $PACK ${IDS} > $OUT/trial_keys.log 2>&1   # 新实例没有首帧：按现在的提示词重做（已有的跳过）
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null
python3 video_h3.py $PACK --only ${IDS// /,} --res __RES__ --mode fl --out $OUT/h3 > $OUT/trial_h3.log 2>&1 || echo "H3 主版失败" >> $OUT/trial_h3.log   # 主版：首帧模式 20 步
V="python3 video_h3.py $PACK --only s06_01_0626 --res __RES__"   # 对照版都用陈瑶说话特写，便于并排比较
$V --mode fl --pika      --out $OUT/h3_pika   > $OUT/trial_h3_pika.log 2>&1     # + Pika H3 Flex 真实感 LoRA
$V --mode fl --prec bf16 --out $OUT/h3_bf16   > $OUT/trial_h3_bf16.log 2>&1     # 全精度 bf16（看比 int8 好多少，效果优先）
$V --mode ref            --out $OUT/h3_ref    > $OUT/trial_h3_ref.log 2>&1      # 参考图模式（首帧 + 陈瑶标准照只当参考）
$V --mode fl --turbo     --out $OUT/h3_turbo  > $OUT/trial_h3_turbo.log 2>&1    # 4 步加速（看画质掉多少，决定全片用哪档）
$V --mode fl --speech    --out $OUT/h3_speech > $OUT/trial_h3_speech.log 2>&1   # H3 自己说台词（原生语音 + 口型）
$V --mode ref --ref-audio --out $OUT/h3_audio > $OUT/trial_h3_audio.log 2>&1    # 参考配音（看能否自己对上口型）wait
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null
( cd /root/v11_upload/moss_trial && . /root/moss/venv/bin/activate && python /root/v11_upload/tts_moss.py dialog.json $OUT/moss > $OUT/trial_moss.log 2>&1; deactivate )   # 视频做完、显存空出来再跑对话配音
mkdir -p $OUT/fun && cp -f $OUT/h3/s06_01_0626.mp4 $OUT/fun/ 2>/dev/null; bash $S/lipsync.sh run $PACK s06_01_0626 > $OUT/trial_lips.log 2>&1
echo OK > $OUT/DONE_TRIAL
'@
    $p = Join-Path $env:TEMP 'trial_h3.sh'; [IO.File]::WriteAllText($p, $sh.Replace('__IDS__', $ids).Replace('__RES__', $Res).Replace("`r`n", "`n"))
    & scp.exe @O -P $Port $p "${SshHost}:/root/trial_h3.sh"
    Ssh1 'nohup bash /root/trial_h3.sh > /root/trial_h3.log 2>&1 & echo QUEUED' | Write-Host
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalHours -lt 4) {
        Start-Sleep 120
        $r = (Ssh1 'cat /root/v11_out/DONE_TRIAL 2>/dev/null; tail -n 1 /root/v11_out/h3_progress.log 2>/dev/null; tail -n 1 /root/v11_out/trial_setup.log 2>/dev/null') -join ' | '
        Write-Host ("{0:HH:mm} {1}" -f (Get-Date), $r)
        if ($r -match 'SETUP_FAIL|DISK_LOW|^OK') { break }
    }
    foreach ($t in ($ids -split ' ')) { Get1 "/root/v11_out/h3/$t.mp4" "$dst\" }
    Get1 '/root/v11_out/lips/s06_01_0626.mp4' "$dst\s06_01_0626_lips.mp4"
    Get1 '/root/v11_out/h3_turbo/s06_01_0626.mp4' "$dst\s06_01_0626_turbo.mp4"; Get1 '/root/v11_out/h3_pika/s06_01_0626.mp4' "$dst\s06_01_0626_pika.mp4"; Get1 '/root/v11_out/h3_bf16/s06_01_0626.mp4' "$dst\s06_01_0626_bf16.mp4"; Get1 '/root/v11_out/h3_ref/s06_01_0626.mp4' "$dst\s06_01_0626_ref.mp4"
    Get1 '/root/v11_out/h3_audio/s06_01_0626.mp4' "$dst\s06_01_0626_refaudio.mp4"
    Get1 '/root/v11_out/h3_speech/s06_01_0626.mp4' "$dst\s06_01_0626_speech_v.mp4"; Get1 '/root/v11_out/h3_speech/s06_01_0626.speech.*' "$dst\"
    $sp = Get-ChildItem $dst -Filter 's06_01_0626.speech.*' | Select-Object -First 1   # 原生语音版：画面配 H3 自己的声音
    if ($sp -and (Test-Path "$dst\s06_01_0626_speech_v.mp4")) { $FF0 = & python -c "import config;print(config.FFMPEG)"; & $FF0 -v error -y -i "$dst\s06_01_0626_speech_v.mp4" -i $sp.FullName -map 0:v -map 1:a -c:v copy -c:a aac -shortest "$cmp0\s06_01_0626_H3原生语音.mp4"; & $FF0 -v error -y -i $sp.FullName -ar 16000 -ac 1 "$dst\s06_01_0626_h3voice.wav" }
    Get1 '/root/v11_out/kf/s01_01_0577.png' "$dst\kf_s01_01_0577.png"
    New-Item -ItemType Directory -Force build\cloud_out\kf_sync | Out-Null; foreach ($t in ($ids -split ' ')) { Get1 "/root/v11_out/kf/$t.png" 'build\cloud_out\kf_sync\' }   # 写实首帧同步回本地
    foreach($k in 0,1,2){ Get1 "/root/v11_out/moss/s06_dialog_$k.wav" "$dst\moss_s06_dialog_$k.wav" }; Get1 '/root/v11_out/moss/s06_dialog.json' "$dst\moss_s06_dialog.json"
    if (Test-Path "$dst\moss_s06_dialog_0.wav") { Copy-Item dist\moss_trial\current_s06_dialog.wav "$cmp0\配音对比_现在的IndexTTS2.wav"; foreach($k in 0,1,2){ if(Test-Path "$dst\moss_s06_dialog_$k.wav"){ Copy-Item "$dst\moss_s06_dialog_$k.wav" "$cmp0\配音对比_MOSS-TTSD对话_第$($k+1)版.wav" } }; Write-Host "配音对比（第二幕宿舍陈瑶和林晓三句对话）：$cmp0\配音对比_*.wav" }
    (Ssh1 'grep -h 完成 /root/v11_out/h3_progress.log') | Out-File -Encoding utf8 "$dst\speed.txt"
    & scp.exe @O -P $Port "${SshHost}:/root/v11_out/trial_*.log" "$dst\" 2>$null
    # 取回后马上清云端中间产物（结果已在本地；写实首帧 kf/ 保留）
    Ssh1 'cd /root/v11_out && ls h3*/*.mp4 lips/*.mp4 moss/*.wav 2>/dev/null >> .pulled; bash /root/v11_upload/scripts/cleanup_auto.sh --yes | tail -2' 300 | Write-Host
    Get-ChildItem $dst | Select-Object Name, Length | Format-Table -AutoSize
}
# 对比：新版先做和旧版一样的本地人脸统一（公平），再左旧右新并排，带配音
$cmp = Join-Path $R 'build\review\trial_compare'; New-Item -ItemType Directory -Force $cmp | Out-Null
$FF = & python -c "import config;print(config.FFMPEG)"
$work = Join-Path $dst 'work'; Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force "$work\real", "$work\heads" | Out-Null
$vers = @{}; foreach ($t in ($ids -split ' ')) { $vers[$t] = if (Test-Path "$dst\${t}_lips.mp4") { "$dst\${t}_lips.mp4" } else { "$dst\$t.mp4" } }
$vers['s06_01_0626_turbo'] = "$dst\s06_01_0626_turbo.mp4"; $vers['s06_01_0626_pika'] = "$dst\s06_01_0626_pika.mp4"; $vers['s06_01_0626_bf16'] = "$dst\s06_01_0626_bf16.mp4"; $vers['s06_01_0626_ref'] = "$dst\s06_01_0626_ref.mp4"; $vers['s06_01_0626_refaudio'] = "$dst\s06_01_0626_refaudio.mp4"
foreach ($k in $vers.Keys) {
    if (-not (Test-Path $vers[$k])) { continue }
    $t = $k.Substring(0, 11); $j = Get-Content "dist\cloud_pack\$t\task.json" -Raw -Encoding utf8 | ConvertFrom-Json
    $d = "$work\real\$k"; New-Item -ItemType Directory -Force $d | Out-Null
    & $FF -v error -y -i $vers[$k] -start_number $j.frames[0] "$d\frame_%04d.png"
    if ($k -ne $t) { Copy-Item "dist\cloud_pack\$t" "dist\cloud_pack\$k" -Recurse -Force -ErrorAction SilentlyContinue }   # 对照版借用同一镜头的任务信息
    if (Test-Path "build\cloud_out\final_all\heads\$t.json") { Copy-Item "build\cloud_out\final_all\heads\$t.json" "$work\heads\$k.json" }
}
& python cloud\face_unify.py $work
$lab = { param($s) "scale=960:540,setsar=1,drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='$s':x=20:y=20:fontsize=30:fontcolor=white:box=1:boxcolor=black@0.5" }
foreach ($k in $vers.Keys) {
    $t = $k.Substring(0, 11); $old = "build\cloud_out\final_all\real\$t.mp4"; $new = "$work\real\$k.mp4"
    if (-not (Test-Path $new)) { Write-Host "缺 $k"; continue }
    $name = @{ $t = '新：H3 动作控制'; 's06_01_0626_turbo' = '新：H3 turbo 4步'; 's06_01_0626_pika' = '新：H3+Pika 真实感'; 's06_01_0626_bf16' = '新：H3 全精度 bf16'; 's06_01_0626_ref' = '新：H3 参考图模式'; 's06_01_0626_refaudio' = '新：H3 参考配音' }[$k]
    if (-not $name) { $name = '新：H3' }
    $vf = "[0:v]$(& $lab '旧：图生视频')[a];[1:v]$(& $lab $name)[b];[a][b]hstack"
    $voice = "dist\cloud_pack\$t\voice.wav"
    if (Test-Path $voice) { & $FF -v error -y -i $old -i $new -i $voice -filter_complex $vf -map 2:a -c:v libx264 -crf 18 -c:a aac -shortest "$cmp\$k.mp4" }
    else { & $FF -v error -y -i $old -i $new -filter_complex $vf -c:v libx264 -crf 18 "$cmp\$k.mp4" }
    Write-Host "对比视频：$cmp\$k.mp4"
}
Get-ChildItem dist\cloud_pack -Directory -Filter 's06_01_0626_*' | Remove-Item -Recurse -Force
if (Test-Path "$dst\speed.txt") { Write-Host '== 每镜头用时'; Get-Content "$dst\speed.txt" -Encoding utf8 }
Write-Host '== 音画同步（旧版 / H3+口型 / H3 参考配音）'
& python cloud\av_sync_check.py build\cloud_out\final_all s06_01_0626 2>$null | Select-Object -First 1
& python cloud\av_sync_check.py $work s06_01_0626 s06_01_0626_refaudio s06_01_0626_turbo s06_01_0626_pika s06_01_0626_ref 2>$null | Select-Object -First 3
if (Test-Path "$cmp0\s06_01_0626_H3原生语音.mp4") { Write-Host "H3 原生语音版（声音和口型都是 H3 生成的）：$cmp0\s06_01_0626_H3原生语音.mp4" }
# 连续 3 个镜头拼成一段（主版 H3 + 白模控制，带这三句的原配音），看镜头之间衔接
$seq = @('s06_01_0260','s06_01_0446','s06_01_0626') | ForEach-Object { "$work\real\$_.mp4" } | Where-Object { Test-Path $_ }
if ($seq.Count -eq 3) {
    $lst = Join-Path $work 'seq.txt'; ($seq | ForEach-Object { "file '$($_ -replace '\\','/')'" }) | Set-Content $lst -Encoding ascii
    & $FF -v error -y -f concat -safe 0 -i $lst -c:v libx264 -crf 18 "$work\seq_v.mp4"
    $seg = Get-Content dist\cloud_pack\s06_01_0260\task.json -Raw -Encoding utf8 | ConvertFrom-Json
    $t0 = ($seg.frames[0] - 1) / 24.0; $dur = (626 + 164 - $seg.frames[0]) / 24.0
    & $FF -v error -y -ss ([math]::Round($t0 + 6.5, 3)) -t $dur -i "build\final\毛坯人生，精装朋友圈_成片_旧版图生视频.mp4" -vn -ac 2 "$work\seq_a.wav" 2>$null
    if (-not (Test-Path "$work\seq_a.wav")) { & $FF -v error -y -ss ([math]::Round($t0 + 6.5, 3)) -t $dur -i "build\final\毛坯人生，精装朋友圈_成片.mp4" -vn -ac 2 "$work\seq_a.wav" }
    & $FF -v error -y -i "$work\seq_v.mp4" -i "$work\seq_a.wav" -map 0:v -map 1:a -c:v copy -c:a aac -shortest "$cmp\连续三镜头_H3新方案.mp4"
    & $FF -v error -y -ss ([math]::Round($t0 + 6.5, 3)) -t $dur -i "build\final\毛坯人生，精装朋友圈_成片.mp4" -c:v libx264 -crf 18 -c:a aac "$cmp\连续三镜头_旧版.mp4"
    Write-Host "连续三镜头：$cmp\连续三镜头_H3新方案.mp4（对照 连续三镜头_旧版.mp4）" }
Write-Host '试跑完成：看完对比视频再决定是否全片重做；记得关机（或等平台空闲 30 分钟自动关机）。'
