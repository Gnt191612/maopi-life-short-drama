# 全片重做（新方案，2026-11-27 准备；试跑经用户确认合格后才用）：Wan2.2 Fun Control 白模动作控制 + LatentSync 口型同步
#   1) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step start -Res 832x480     # 上传全片素材，在云端排好整条流程（不用盯）
#   2) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step pull                    # 本地后台：每 10 分钟取回一批，马上替换进 final_fun、统一人脸，直到云端全部完成
#   3) powershell -ExecutionPolicy Bypass -File cloud\full_fun.ps1 -Step final                   # 备份旧成片 → 合成新成片 → 跑审查（跑偏拼图、角色对照、台词对齐）
# 云端流程：装模型（已有就跳过）→ 后台装口型环境 → 重做改过提示词的首帧 → 全片视频（已做好的跳过，断线/空闲关机后重跑接着做）→ 口型同步 49 个单人说话镜头 → DONE_FULL
# 结果目录 build\cloud_out\final_fun（先复制一份旧版 final_all 当兜底：哪个镜头新版没做出来，暂时用旧版顶上并在报告里列出）
param([ValidateSet('start', 'pull', 'final')][string]$Step = 'start', [string]$Res = '832x480',
      [string]$SshHost = 'root@4b5fw7589f8xzvy1.ssh.x-gpu.com', [int]$Port = 56493)
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
    & python cloud\shot_audio.py | Select-Object -First 1
    $all = (Get-ChildItem dist\cloud_pack -Directory | Where-Object { Test-Path "$($_.FullName)\task.json" } | ForEach-Object Name | Sort-Object) -join ','
    $have = Ssh1 'cd /root/v11_out/kf 2>/dev/null && ls *.png 2>/dev/null' 90   # 云端已有的写实首帧（不带 @ 的）
    $have = @($have | Where-Object { $_ -match '^s\d\d_\d\d_\d{4}\.png$' } | ForEach-Object { $_ -replace '\.png$', '' })
    $needFirst = @(($all -split ',') | Where-Object { ($have -notcontains $_) -or (($Rekey -split ' ') -contains $_) })
    Write-Host ("云端已有写实首帧 {0} 个；要新做首帧 {1} 个：{2}" -f $have.Count, $needFirst.Count, ($needFirst -join ' '))
    & python cloud\slim_pack.py $all dist\full_fun.zip --no-anchors --first ($needFirst -join ',')
    $voice = (Get-ChildItem dist\cloud_pack -Directory | Where-Object { Test-Path "$($_.FullName)\voice.wav" } | ForEach-Object Name | Sort-Object) -join ' '
    & scp.exe @O -P $Port cloud\video_fun.py cloud\lipsync.sh cloud\setup_fun.sh cloud\keyframes.py cloud\comfy_run.py cloud\looks.py cloud\looks_gen.json cloud\shard.py "${SshHost}:/root/v11_upload/scripts/"
    & scp.exe @O -P $Port dist\full_fun.zip "${SshHost}:/root/v11_upload/full_fun.zip"
    $sh = @'
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; rm -f $OUT/DONE_FULL
rm -rf /root/v11cloud; mkdir -p /root/v11cloud; python3 -c "import zipfile; zipfile.ZipFile('/root/v11_upload/full_fun.zip').extractall('/root/v11cloud')"
bash $S/setup_fun.sh > $OUT/full_setup.log 2>&1 || { echo SETUP_FAIL > $OUT/DONE_FULL; exit; }
( bash $S/lipsync.sh setup > $OUT/full_lipsetup.log 2>&1 ) &
for i in __REKEY__; do rm -f $OUT/kf/$i.png $OUT/kf/$i@*.png $OUT/kfbase_$i*.png $OUT/kfswap_$i*.png; done
cd $S && python3 keyframes.py $PACK > $OUT/full_keys.log 2>&1          # 已有首帧的跳过，只补缺的
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null   # 卸掉 Krea2/Qwen，给 Wan 腾显存
python3 video_fun.py $PACK --res __RES__ > $OUT/full_fun.log 2>&1
wait
curl -s -X POST -H "Content-Type: application/json" -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null   # 给口型同步腾显存
bash $S/lipsync.sh run $PACK __VOICE__ > $OUT/full_lips.log 2>&1
touch $OUT/DONE_FULL
'@
    $p = Join-Path $env:TEMP 'full_fun.sh'; [IO.File]::WriteAllText($p, $sh.Replace('__REKEY__', $Rekey).Replace('__RES__', $Res).Replace('__VOICE__', $voice).Replace("`r`n", "`n"))
    & scp.exe @O -P $Port $p "${SshHost}:/root/full_fun.sh"
    & ssh.exe @O -p $Port $SshHost 'nohup bash /root/full_fun.sh > /root/full_fun.log 2>&1 & echo QUEUED'
    Write-Host '已排队。接着运行 -Step pull（后台），它会一直取回到全部完成。'
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
            if (Wait-Job $j -Timeout 300) { $new += $id } else { Stop-Job $j; Remove-Item $loc -ErrorAction SilentlyContinue }; Remove-Job $j -Force
        }
        $new = $new | Sort-Object -Unique
        if ($new) {
            Write-Host ("{0:HH:mm} 取回 {1} 个：{2}" -f (Get-Date), $new.Count, ($new -join ' '))
            & powershell -NoProfile -ExecutionPolicy Bypass -File cloud\apply_results.ps1 -From $pulled -Only ($new -join ',') -NoFinal -Target final_fun *>> build\logs\full_apply.log
        }
        $done = ($ls -match 'DONE_FULL').Count -gt 0; $fail = ($ls -match 'SETUP_FAIL').Count -gt 0
        Write-Host ("{0:HH:mm} 已取回 {1} 个视频、{2} 个口型版；{3}" -f (Get-Date), (Get-ChildItem $pulled -Filter *.mp4 | Where-Object { $_.Name -notlike '*_lips.mp4' }).Count, (Get-ChildItem $pulled -Filter *_lips.mp4).Count, ($ls | Select-Object -Last 1))
        if ($fail) { Write-Host '云端模型安装失败，看 /root/v11_out/full_setup.log'; break }
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
