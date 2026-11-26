# 本地成片（云端 final 阶段结果下载后运行，不花钱）：
#   1) 写实视频拆回逐帧（帧号与白模一致）
#   2) 片头：竖屏高清 Claude 娘（intro_hd*.gif → 按真实时长换算）→ 重新合成片头
#   3) 正片：run_all --previs-only --real=（写实画面 + 配音 + 字幕 + 配乐，缺的帧用白模补）
#   4) 片头 + 正片 → build\final\毛坯人生，精装朋友圈_成片.mp4
# 用法：powershell -ExecutionPolicy Bypass -File cloud\make_final.ps1 -Result build\cloud_out\final_<时间> [-IntroPick 1]
param([Parameter(Mandatory = $true)][string[]]$Result, [int]$IntroPick = 1)
# 多实例并行时 -Result 传多个目录（逗号隔开），先合并成一个
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent; Push-Location $Root
try {
    $FF = & python -c "import config; print(config.FFMPEG)"
    if ($Result.Count -gt 1) {   # 多台实例的结果合并（real/ 与 kf/ 按镜头互不重叠；片头在第 1 台）
        $merged = Join-Path $Root ('build\cloud_out\final_merged_{0:MMdd_HHmm}' -f (Get-Date))
        New-Item -ItemType Directory -Force "$merged\real", "$merged\kf" | Out-Null
        foreach ($r in $Result) {
            $r = (Resolve-Path $r).Path
            if (Test-Path "$r\real") { Copy-Item "$r\real\*" "$merged\real" -Recurse -Force }
            if (Test-Path "$r\kf") { Copy-Item "$r\kf\*" "$merged\kf" -Force }
            Get-ChildItem $r -Filter 'intro_hd*.gif' | Copy-Item -Destination $merged -Force
        }
        Write-Host ("合并 {0} 台结果 → {1}（{2} 个镜头视频）" -f $Result.Count, $merged, (Get-ChildItem "$merged\real" -Filter *.mp4).Count)
        $Result = [string]$merged   # 参数是 string[]，直接赋值还是数组，后面 Copy-Item -Destination 会报错（11-25）
    } else { $Result = [string](Resolve-Path $Result[0]).Path }
    if (-not (Get-ChildItem $Result -Filter 'intro_hd*.gif' -ErrorAction SilentlyContinue)) { Get-ChildItem (Join-Path $Root 'build\cloud_out\intro_hd') -Filter 'intro_hd*.gif' | Copy-Item -Destination ([string]($Result -join "")) -Force; Write-Host '    云端没做片头：用本地已有的片头' }
    Write-Host '[1/4] 写实视频拆帧'
    & python cloud\mp4_frames.py "$Result\real"
    Write-Host '[2/4] 片头'
    $gif = Join-Path $Result ("intro_hd{0}.gif" -f $IntroPick)
    if (Test-Path $gif) {
        $mp4 = Join-Path $Result 'intro_hd.mp4'
        # 81 帧（16fps，5 秒）插帧后存 GIF，GIF 里记的帧率不对：按「总帧数 / 5 秒」重算
        $n = [int](& python -c "import cv2,sys; print(int(cv2.VideoCapture(sys.argv[1]).get(7)))" $gif)
        & $FF -v error -y -i $gif -vf ("setpts=N/({0}/5.0)/TB,fps=24" -f ($n - 1)) -c:v libx264 -crf 14 -pix_fmt yuv420p $mp4
        $env:V11_INTRO_GIRL = $mp4
    } else { Write-Host '    没有高清片头素材，沿用 intro_talk2' }
    Remove-Item build\intro\frames -Recurse -Force -ErrorAction SilentlyContinue
    & python blender\intro_compose.py
    Write-Host '[3/4] 正片（写实画面 + 配音字幕配乐）'
    $env:V11_PREVIEW = '1'      # 白模补位帧来自预览画质渲染目录（与打包时一致）
& python cloud\realign.py "$Result"   # 节奏调整过的片段按最新时间轴重对齐（第一次只建快照）
        & python run_all.py --previs-only "--real=$Result\real"
    Write-Host '[4/4] 片头 + 正片'
    $film = 'build\final\v11_previs_full.mp4'; $out = 'build\final\毛坯人生，精装朋友圈_成片.mp4'
    & $FF -v error -y -i build\intro\intro.mp4 -i $film -filter_complex "[0:v]scale=1920:1080,setsar=1,fps=24[v0];[1:v]scale=1920:1080,setsar=1,fps=24[v1];[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k $out
    Write-Host "成片：$out"
} finally { Pop-Location }
