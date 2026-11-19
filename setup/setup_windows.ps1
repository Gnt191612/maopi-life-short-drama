# 《毛坯人生，精装朋友圈》白模管线 —— Windows 一键安装（在空白电脑上运行一次即可）
# 用法（PowerShell，在仓库根目录）：  powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1 [-WithTTS] [-WithRemotion]
# 需要：网络（可设 HTTPS_PROXY 环境变量走代理）、Python 3.10+、约 3 GB 磁盘（加 -WithTTS 再加约 10 GB）
param([switch]$WithTTS, [switch]$WithRemotion)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$T = Join-Path $Root '.tools'; New-Item -ItemType Directory -Force $T | Out-Null
$BV = '4.5.16'
$Proxy = if ($env:HTTPS_PROXY) { @('-x', $env:HTTPS_PROXY) } else { @() }

function Get-File($urls, $out) {
    if (Test-Path $out) { Write-Host "  已存在 $out"; return }
    foreach ($u in $urls) {
        Write-Host "  下载 $u"
        & curl.exe -L -f --retry 5 -A 'Mozilla/5.0' @Proxy -o "$out.part" $u
        if ($LASTEXITCODE -eq 0) { Move-Item -Force "$out.part" $out; return }
        Remove-Item "$out.part" -ErrorAction SilentlyContinue
    }
    throw "下载失败：$out（可设置 HTTPS_PROXY 后重试）"
}
$dl = Join-Path $T '_downloads'; New-Item -ItemType Directory -Force $dl | Out-Null

Write-Host '[0/7] 固定资产（角色、场景、配音）'
if (-not (Test-Path (Join-Path $Root 'assets\cast\lin.blend'))) {
    $url = Get-Content (Join-Path $Root 'setup\assets_release.txt') | Where-Object { $_ -match '^https?://' } | Select-Object -First 1
    if (-not $url) { throw '仓库中没有资产文件，且 setup\assets_release.txt 未填写资产包地址' }
    $az0 = Join-Path $dl 'assets.zip'; Get-File @($url) $az0
    Expand-Archive $az0 -DestinationPath (Join-Path $Root 'assets') -Force
}

Write-Host '[1/7] Blender' $BV 'LTS'
$bz = Join-Path $dl "blender-$BV-windows-x64.zip"
Get-File @("https://download.blender.org/release/Blender4.5/blender-$BV-windows-x64.zip",
           "https://mirrors.aliyun.com/blender/release/Blender4.5/blender-$BV-windows-x64.zip",
           "https://mirror.clarkson.edu/blender/release/Blender4.5/blender-$BV-windows-x64.zip") $bz
if (-not (Test-Path "$T\blender\blender.exe")) {
    Expand-Archive $bz -DestinationPath $T -Force; Move-Item -Force "$T\blender-$BV-windows-x64" "$T\blender"
}
$env:BLENDER_USER_RESOURCES = Join-Path $T 'blender_user'     # Blender 用户目录放进仓库，插件与素材随仓库走

Write-Host '[2/7] MPFB 2.0.18（MakeHuman 角色插件，GPL-3.0）'
$mz = Join-Path $dl 'add-on-mpfb-v2.0.18.zip'
Get-File @('https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip') $mz
& "$T\blender\blender.exe" -b --factory-startup --command extension install-file --repo user_default --enable $mz | Out-Null

Write-Host '[3/7] MakeHuman 系统素材（CC0：皮肤、发型、服装、眼睛）'
$az = Join-Path $dl 'makehuman_system_assets_cc0.zip'
Get-File @('https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip',
           'https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip') $az
$md = Join-Path $env:BLENDER_USER_RESOURCES 'extensions\.user\user_default\mpfb\data'
if (-not (Test-Path "$md\skins")) { New-Item -ItemType Directory -Force $md | Out-Null; Expand-Archive $az -DestinationPath $md -Force }

Write-Host '[4/7] Rhubarb Lip Sync 1.14.0（口型，MIT）'
$rz = Join-Path $dl 'Rhubarb-Lip-Sync-1.14.0-Windows.zip'
Get-File @('https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Windows.zip') $rz
if (-not (Test-Path "$T\rhubarb\rhubarb.exe")) { Expand-Archive $rz -DestinationPath $dl -Force; Move-Item -Force "$dl\Rhubarb-Lip-Sync-1.14.0-Windows" "$T\rhubarb" }

Write-Host '[5/7] ffmpeg'
$fz = Join-Path $dl 'ffmpeg-release-essentials.zip'
Get-File @('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
           'https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip') $fz
if (-not (Test-Path "$T\ffmpeg\ffmpeg.exe")) {
    Expand-Archive $fz -DestinationPath "$dl\ff" -Force; New-Item -ItemType Directory -Force "$T\ffmpeg" | Out-Null
    Get-ChildItem "$dl\ff" -Recurse -Include ffmpeg.exe, ffprobe.exe | Copy-Item -Destination "$T\ffmpeg"
}

Write-Host '[5b] 环境光 HDRI（Poly Haven CC0）与配乐古典录音（维基共享资源 CC0/公有领域）'
python (Join-Path $Root 'setup\get_hdri.py'); python (Join-Path $Root 'setup\get_music.py')
Write-Host '[6/7] 开源字体 Noto Sans SC（SIL OFL）'
New-Item -ItemType Directory -Force "$T\fonts" | Out-Null
Get-File @('https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf') "$T\fonts\NotoSansSC-Regular.ttf"
# 手机屏幕界面要用静态字重（Blender 读可变字体只会用最细的字重）：用 fontTools 从同一个字体实例化出常规/粗体
python -m pip install -q fonttools
foreach ($w in @(@(400, 'Regular'), @(700, 'Bold'))) { if (-not (Test-Path "$T\fonts\NotoSansSC-Static-$($w[1]).ttf")) { python -m fontTools.varLib.instancer "$T\fonts\NotoSansSC-Regular.ttf" "wght=$($w[0])" -o "$T\fonts\NotoSansSC-Static-$($w[1]).ttf" } }

Write-Host '[7/7] CMU 动作捕捉片段（CMU Graphics Lab，可自由使用、需署名）+ Python 依赖'
$mo = Join-Path $Root 'build\mocap'; New-Item -ItemType Directory -Force $mo | Out-Null
foreach ($c in (Get-Content (Join-Path $Root 'setup\mocap_clips.txt') | Where-Object { $_ -match '^\d' })) {
    $s = $c.Split('_')[0]; Get-File @("https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/0$s/$c.bvh") "$mo\$c.bvh"
}
python -m pip install --quiet -r (Join-Path $Root 'setup\requirements.txt')

Write-Host '[可选] 重新生成人物时才需要：MakeHuman 社区服装包  setup\get_mh_community.ps1'
if ($WithRemotion) { Write-Host '[可选] Remotion 合成工程'; Push-Location (Join-Path $Root 'remotion'); npm install --no-fund --no-audit; Pop-Location }
if ($WithTTS) { & (Join-Path $PSScriptRoot 'setup_tts_windows.ps1') }
Write-Host ''
Write-Host '安装完成。下一步：  python run_all.py      （白模全片：搭建 + 动画 + 渲染 + 预演视频）'
