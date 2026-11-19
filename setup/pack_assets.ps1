# 把固定资产（角色、场景、配音）打包成 zip，作为 GitHub Release 附件上传。
# 用法（仓库根目录）：  powershell -ExecutionPolicy Bypass -File setup\pack_assets.ps1 [-Version v1.0]
# 输出：dist\assets_<版本>.zip ；上传到 Release 后，把下载地址写进 setup\assets_release.txt
param([string]$Version = 'v1.0')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $Root 'dist'; New-Item -ItemType Directory -Force $dist | Out-Null
$zip = Join-Path $dist "assets_$Version.zip"
if (Test-Path $zip) { Remove-Item $zip }
$items = @('assets\cast', 'assets\sets', 'assets\audio', 'assets\music') | ForEach-Object { Join-Path $Root $_ }
foreach ($i in $items) { if (-not (Test-Path $i)) { throw "缺少 $i" } }
Get-ChildItem (Join-Path $Root 'assets') -Recurse -Filter *.blend1 | Remove-Item -Force   # Blender 自动备份文件不打包
Compress-Archive -Path $items -DestinationPath $zip -CompressionLevel Optimal
$h = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"{0}  {1}" -f $h, (Split-Path $zip -Leaf) | Out-File -Encoding ascii (Join-Path $dist "assets_$Version.sha256")
Write-Host ("已生成 {0}（{1:N0} MB），SHA256 {2}" -f $zip, ((Get-Item $zip).Length / 1MB), $h)
