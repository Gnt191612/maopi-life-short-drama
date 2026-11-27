# 全片重做（现行方案，2026-11-27；试跑经用户确认合格后才用）：默认 MiniMax H3 + Fun ControlNet 白模动作控制（-Engine fun 可换备选 Wan2.2 Fun Control）+ LatentSync 口型同步
#   1) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step start -Res 832x480     # 上传全片素材，在云端排好整条流程（不用盯）
#   2) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step pull                    # 本地后台：每 10 分钟取回一批，马上替换进 final_fun、统一人脸，直到云端全部完成
#   3) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step final                   # 备份旧成片 → 合成新成片 → 跑审查（跑偏拼图、角色对照、台词对齐）
# 云端流程：装模型（已有就跳过）→ 后台装口型环境 → 重做改过提示词的首帧 → 全片视频（已做好的跳过，断线/空闲关机后重跑接着做）→ 口型同步 49 个单人说话镜头 → DONE_FULL
# 结果目录 build\cloud_out\final_fun（先复制一份旧版 final_all 当兜底：哪个镜头新版没做出来，暂时用旧版顶上并在报告里列出）
param([ValidateSet('start', 'keys', 'pull', 'final')][string]$Step = 'start', [string]$Res = '1344x768', [ValidateSet('h3', 'fun')][string]$Engine = 'h3', [string]$H3Args = '--hybrid',   # 11-27 用户定：混合方案（运镜镜头 20 步、手持/固定镜头 Pika 6 步）
      [switch]$KeysOnly, [switch]$Sage,   # KeysOnly：只做首帧（取回审查合格后再不带它跑视频，首帧已有的跳过）；Sage：视频前用 --use-sage-attention 重启 ComfyUI（测试确认画质不变后才用）   # Engine：h3 = MiniMax H3（11-27 选定，默认），fun = Wan2.2 Fun Control（备选）；H3Args 例如 '--turbo' 按试跑结论加
      [string]$SshHost = 'root@tdtjxa8cdyzuands.ssh.x-gpu.com', [int]$Port = 49855)
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent; Set-Location $R; $env:PYTHONIOENCODING = 'utf-8'
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$O = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
$Rekey = 's01_01_0577 s05_01_0440 s08_01_0288 s10_00_0787 s01_01_1016 s02_01_1116'   # 首帧要按新提示词重做的镜头（白模质感、人物错、衣服错）
$pulled = Join-Path $R 'build\cloud_out\pulled_fun'; New-Item -ItemType Directory -Force $pulled | Out-Null
function Ssh1($cmd, $sec = 60) {   # 带硬超时的 ssh（11-25 教训：ssh 卡死会让本地监视停摆）
    $j = Start-Job { param($O, $H, $P, $c) & ssh.exe @O -p $P $H $c } -ArgumentList (, $O), $SshHost, $Port, $cmd
    if (Wait-Job $j -Timeout $sec) { $r = Receive-Job $j } else { Stop-Job $j; $r = $null }; Remove-Job $j -Force; return $r
}

if ($Step -eq 'start') {
    $free = (Get-PSDrive D).Free / 1GB
    if ($free -lt 25) { Write-Host ("D 盘只剩 {0:N0} GB，全片新素材约需 23 GB，先清理再开始" -f $free); exit 1 }
    & python -c "import sys,json; sys.path.insert(0,'cloud'); import looks; json.dump(dict(look=looks.LOOK, look_en=looks.LOOK_EN, name=looks.NAME), open('cloud/looks_gen.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"
    # ---- 开跑前提示词审查（11-27 起强制，踩坑 72～76）：不是 0 条就不上传 ----
    & python cloud\apply_shot_prompts.py | Write-Host
    & python cloud\visible_cast.py --write | Select-Object -Last 1 | Write-Host
    & python cloud\shot_audio.py | Select-Object -Last 1 | Write-Host
    & python cloud\export_prompts.py | Write-Host
    $aud = & python cloud\audit_prompts.py; Write-Host $aud
    if ($aud -notmatch '有提示的镜头 0 个') { Write-Host '提示词审查没过，先按 build\review\prompts\审查报告.md 改完再上云（不要带着已知问题花钱）'; exit 1 }
    $all = (Get-ChildItem dist\cloud_pack -Directory | Where-Object { Test-Path "$($_.FullName)\task.json" } | ForEach-Object Name | Sort-Object) -join ','
    $have = Ssh1 'cd /root/v11_out/kf 2>/dev/null && ls *.png 2>/dev/null' 90   # 云端已有的写实首帧（不带 @ 的）
    $have = @($have | Where-Object { $_ -match '^s\d\d_\d\d_\d{4}\.png$' } | ForEach-Object { $_ -replace '\.png$', '' })
    $needFirst = @(($all -split ',') | Where-Object { ($have -notcontains $_) -or (($Rekey -split ' ') -contains $_) })
    Write-Host ("云端已有写实首帧 {0} 个；要新做首帧 {1} 个：{2}" -f $have.Count, $needFirst.Count, ($needFirst -join ' '))
    & python cloud\slim_pack.py $all dist\full_fun.zip --no-anchors --pose --first ($needFirst -join ',')
    $voice = (Get-ChildItem dist\cloud_pack -Directory | Where-Object { Test-Path "$($_.FullName)\voice.wav" } | ForEach-Object Name | Sort-Object) -join ' '
    Ssh1 'mkdir -p /root/v11_upload/scripts /root/v11_out/kf /root/ComfyUI/input; pkill -f trial_h3.sh; pkill -f full_fun.sh; echo dirs' 60 | Out-Null   # 新实例没有这些目录（11-27 新建 TDTJ 时第一次上传失败）
    & scp.exe @O -P $Port cloud\video_fun.py cloud\video_h3.py cloud\h3_prompt.py cloud\disk_guard.sh cloud\cleanup_auto.sh cloud\lipsync.sh cloud\setup_fun.sh cloud\setup_h3.sh cloud\keyframes.py cloud\lighting.py cloud\comfy_run.py cloud\comfy_restart.sh cloud\looks.py cloud\looks_gen.json cloud\shard.py "${SshHost}:/root/v11_upload/scripts/"
    & scp.exe @O -P $Port dist\full_fun.zip "${SshHost}:/root/v11_upload/full_fun.zip"
    $sh = @'
PYC=$(ls /root/miniconda3/envs/comfyui/bin/python 2>/dev/null || command -v python3)   # ComfyUI 环境的 Python（有 cv2/PIL/numpy；系统 python3 没有）
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; rm -f $OUT/DONE_FULL
sed -i 's/\r$//' $S/*.sh /root/v11_upload/*.sh 2>/dev/null   # Windows 写的脚本是 CRLF，bash 读不了（11-27）
for f in $S/*.sh /root/v11_upload/*.sh; do [ -f $f ] && { bash -n $f || { echo "SYNTAX_FAIL $f" > $OUT/DONE_FULL; exit; }; }; done
bash $S/disk_guard.sh > $OUT/full_disk.log 2>&1 || { echo DISK_LOW > $OUT/DONE_FULL; exit; }   # 踩坑记录 62；必须在解压之前跑：它的自动清理会删上传的 zip（11-27 重跑时解压失败）
rm -rf /root/v11cloud; mkdir -p /root/v11cloud; python3 -c "import zipfile; zipfile.ZipFile('/root/v11_upload/full_fun.zip').extractall('/root/v11cloud')"; cp -f $PACK/refs/*.jpg /root/ComfyUI/input/ 2>/dev/null
bash $S/setup___ENGINE__.sh > $OUT/full_setup.log 2>&1 || { echo SETUP_FAIL > $OUT/DONE_FULL; exit; }
( bash $S/lipsync.sh setup > $OUT/full_lipsetup.log 2>&1 ) &
for i in __REKEY__; do rm -f $OUT/kf/$i.png $OUT/kf/$i@*.png $OUT/kfbase_$i*.png $OUT/kfswap_$i*.png; done
cd $S && $PYC keyframes.py $PACK > $OUT/full_keys.log 2>&1          # 已有首帧的跳过，只补缺的
if [ __KEYSONLY__ = 1 ]; then touch $OUT/DONE_KEYS; exit; fi   # 只做首帧：取回本地逐张审查（踩坑 71），合格后再跑视频
if [ __SAGE__ = 1 ]; then bash $S/comfy_restart.sh --use-sage-attention > $OUT/full_comfy.log 2>&1 || { echo COMFY_FAIL > $OUT/DONE_FULL; exit; }; fi
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null   # 卸掉 Krea2/Qwen，给 Wan 腾显存
if [ __ENGINE__ = h3 ]; then $PYC video_h3.py $PACK --res __RES__ --out $OUT/fun __H3ARGS__ > $OUT/full_fun.log 2>&1; else $PYC video_fun.py $PACK --res __RES__ > $OUT/full_fun.log 2>&1; fi   # 两种引擎都输出到 fun/，后面取回和口型同步不用改
wait
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null   # 给口型同步腾显存
bash $S/lipsync.sh run $PACK __VOICE__ > $OUT/full_lips.log 2>&1
touch $OUT/DONE_FULL
'@
    $p = Join-Path $env:TEMP 'full_fun.sh'; [IO.File]::WriteAllText($p, $sh.Replace('__REKEY__', $Rekey).Replace('__RES__', $Res).Replace('__ENGINE__', $Engine).Replace('__H3ARGS__', $H3Args).Replace('__VOICE__', $voice).Replace('__KEYSONLY__', [string][int][bool]$KeysOnly).Replace('__SAGE__', [string][int][bool]$Sage).Replace('__KEYSONLY__', [string][int][bool]$KeysOnly).Replace('__SAGE__', [string][int][bool]$Sage).Replace("`r`n", "`n"))
    & scp.exe @O -P $Port $p "${SshHost}:/root/full_fun.sh"
    & ssh.exe @O -p $Port $SshHost 'nohup bash /root/full_fun.sh > /root/full_fun.log 2>&1 & echo QUEUED'
    Write-Host '已排队。接着运行 -Step pull（后台），它会一直取回到全部完成。'
    exit
}

if ($Step -eq 'keys') {   # 取回全部写实首帧做审查（-KeysOnly 跑完后）：build\cloud_out\kf_review\ + 拼图，人工逐张对照白模首帧（人数、朝向、衣着、光线、有没有多出的人/脸）
    $dst = Join-Path $R 'build\cloud_out\kf_review'; New-Item -ItemType Directory -Force $dst | Out-Null
    Write-Host ((Ssh1 'ls /root/v11_out/DONE_KEYS 2>/dev/null; ls /root/v11_out/kf/*.png 2>/dev/null | wc -l' 60) -join ' ')
    & scp.exe @O -P $Port "${SshHost}:/root/v11_out/kf/*.png" $dst
    & python cloud\kf_review.py $dst
    exit
}
if ($Step -eq 'pull') {
    if (-not (Test-Path build\cloud_out\final_fun\real)) {   # 新结果目录：复制旧版当兜底（片头、头部位置、时间轴快照也一并带上）
        & robocopy build\cloud_out\final_all build\cloud_out\final_fun /E /NFL /NDL /NJH /NJS /NP | Out-Null
        Get-ChildItem build\cloud_out\final_fun\real -Recurse -Filter .unified | Remove-Item -Force   # 新镜头要重新统一人脸
    }
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalHours -lt 16) {
        $ls = Ssh1 'cd /root/v11_out; ls fun/*.mp4 lips/*.mp4 2>/dev/null; ls DONE_FULL 2>/dev/null; cat DONE_FULL 2>/dev/null; tail -n 1 fun_progress.log 2>/dev/null' 90
        if ($null -eq $ls) { Write-Host ("{0:HH:mm} ssh 无响应，10 分钟后重试" -f (Get-Date)); Start-Sleep 600; continue }
        $new = @()
        foreach ($l in $ls) {
            if ($l -match '^fun/(.+)\.mp4$') { $id = $Matches[1]; $loc = "$pulled\$id.mp4" }
            elseif ($l -match '^lips/(.+)\.mp4$') { $id = $Matches[1]; $loc = "$pulled\${id}_lips.mp4" }
            else { continue }
            if (Test-Path $loc) { continue }
            $j = Start-Job { param($O, $H, $P, $src, $dst) & scp.exe @O -P $P "${H}:/root/v11_out/$src" $dst } -ArgumentList (, $O), $SshHost, $Port, $l, $loc
            if (Wait-Job $j -Timeout 300) { $new += $id; Ssh1 "echo $l >> /root/v11_out/.pulled" 30 | Out-Null }
            if ($l -like 'fun/*') { New-Item -ItemType Directory -Force build\cloud_out\kf_sync | Out-Null; & scp.exe @O -P $Port "${SshHost}:/root/v11_out/kf/$id.png" build\cloud_out\kf_sync\ 2>$null }   # 写实首帧同步回本地（踩坑记录 62）   # 记下已取回，清理时只删这些 else { Stop-Job $j; Remove-Item $loc -ErrorAction SilentlyContinue }; Remove-Job $j -Force
        }
        $new = $new | Sort-Object -Unique
        if ($new) {
            Write-Host ("{0:HH:mm} 取回 {1} 个：{2}" -f (Get-Date), $new.Count, ($new -join ' '))
            & powershell -NoProfile -ExecutionPolicy Bypass -File cloud\apply_results.ps1 -From $pulled -Only ($new -join ',') -NoFinal -Target final_fun *>> build\logs\full_apply.log
        }
        $done = ($ls -match 'DONE_FULL').Count -gt 0; $fail = ($ls -match 'SETUP_FAIL').Count -gt 0
        Write-Host ("{0:HH:mm} 已取回 {1} 个视频、{2} 个口型版；{3}" -f (Get-Date), (Get-ChildItem $pulled -Filter *.mp4 | Where-Object { $_.Name -notlike '*_lips.mp4' }).Count, (Get-ChildItem $pulled -Filter *_lips.mp4).Count, ($ls | Select-Object -Last 1))
        if ($fail) { Write-Host '云端模型安装失败，看 /root/v11_out/full_setup.log'; break }
        if (($ls -match 'DISK_LOW').Count) { Write-Host '云端磁盘不够，看 /root/v11_out/full_disk.log，把清单发给用户决定'; break }
        if ($new.Count -ge 10) { Ssh1 'bash /root/v11_upload/scripts/cleanup_auto.sh --yes | tail -1' 300 | Write-Host }   # 边取回边清，云端不堆积
        if ($done -and -not $new) { Write-Host '云端全部完成、本地全部取回。可以关机，然后运行 -Step final'; break }
        Start-Sleep 600
    }
    exit
}

if ($Step -eq 'final') {
    $old = 'build\final\毛坯人生，精装朋友圈_成片.mp4'; $bak = 'build\final\毛坯人生，精装朋友圈_成片_旧版图生视频.mp4'
    if ((Test-Path $old) -and -not (Test-Path $bak)) { Copy-Item $old $bak; Write-Host "旧成片备份：$bak" }
    $miss = Get-ChildItem dist\cloud_pack -Directory | Where-Object { (Test-Path "$($_.FullName)\task.json") -and -not (Test-Path "$pulled\$($_.Name).mp4") } | ForEach-Object Name
    if ($miss) { Write-Host ("注意：{0} 个镜头没有新版，暂用旧版：{1}" -f $miss.Count, ($miss -join ' ')) }
    & powershell -NoProfile -ExecutionPolicy Bypass -File cloud\make_final.ps1 -Result (Join-Path $R 'build\cloud_out\final_fun')
    & python cloud\drift_review.py build\cloud_out\final_fun\real | Select-Object -Last 1
    & python cloud\cast_sheet.py build\cloud_out\final_fun | Select-String '\(' | ForEach-Object Line
    & python cloud\dialog_audit.py | Select-Object -First 3
    Write-Host '== 音画同步验收（49 个单人说话镜头；旧版只有 2 个合格）'; & python cloud\av_sync_check.py build\cloud_out\final_fun 2>$null | Select-Object -Last 1
    Write-Host '新成片：build\final\毛坯人生，精装朋友圈_成片.mp4；审查图在 build\review\drift、cast、dialog'
}
