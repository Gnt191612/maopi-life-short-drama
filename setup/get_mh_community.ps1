# 下载 MakeHuman 社区服装包（角色分件服装用，约 500 MB，CC0 / CC-BY，署名见 THIRD_PARTY_LICENSES.md）
# 用法：powershell -ExecutionPolicy Bypass -File setup\get_mh_community.ps1 [-Dest <目录>] [-Proxy http://127.0.0.1:7897]
# 放在默认位置以外时，运行 Blender 前设置环境变量 V11_MH_COMMUNITY 指向该目录
param([string]$Dest = '', [string]$Proxy = '')
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Dest) { $Dest = Join-Path $Root '.tools\mh_community_clothes' }   # 默认在仓库内（config.py 的默认位置）；放别处要设 V11_MH_COMMUNITY
$ErrorActionPreference = 'Stop'
$packs = @(@('shirts01', 'shirts01_cc0.zip'), @('shirts02', 'shirts02_ccby.zip'), @('pants01', 'pants01_cc0.zip'),
           @('pants02', 'pants02_ccby.zip'), @('skirts02', 'skirts02_cc-by.zip'), @('shoes01', 'shoes01_cc0.zip'))
New-Item -ItemType Directory -Force (Join-Path $Dest '_downloads') | Out-Null
foreach ($pk in $packs) {
    $name = $pk[0]; $file = $pk[1]; $zip = Join-Path $Dest "_downloads\$file"
    if (Test-Path (Join-Path $Dest "$name\.done")) { Write-Host "已有 $name"; continue }
    $ok = $false
    for ($i = 1; $i -le 4 -and -not $ok; $i++) {
        foreach ($h in 'files.makehumancommunity.org', 'files2.makehumancommunity.org') {
            $a = @('-L', '-f', '--retry', '5', '--connect-timeout', '30', '-o', $zip, "https://$h/asset_packs/$name/$file")
            if ($Proxy) { $a = @('-x', $Proxy) + $a }
            & curl.exe @a
            if ($LASTEXITCODE -eq 0 -and (Get-Item $zip).Length -gt 1MB) { $ok = $true; break }
        }
        if (-not $ok) { Start-Sleep 15 }
    }
    if (-not $ok) { throw "下载失败：$name" }
    Expand-Archive -Force $zip (Join-Path $Dest $name); 'done' | Out-File (Join-Path $Dest "$name\.done")
    Write-Host "完成 $name"
}
# 发型包（林母波浪短发轮廓等，build_cast.py 的 HAIR_SHAPE 引用 .tools/mh_community/hair0x/…）
$HairDest = Join-Path $Root '.tools\mh_community'
foreach ($name in 'hair02', 'hair03') {
    if (Test-Path (Join-Path $HairDest "$name\.done")) { Write-Host "已有 $name"; continue }
    New-Item -ItemType Directory -Force (Join-Path $HairDest $name) | Out-Null
    $zip = Join-Path $Dest ("_downloads\{0}_ccby.zip" -f $name)
    $a = @('-L', '-f', '--retry', '5', '--connect-timeout', '30', '-o', $zip, ("https://files.makehumancommunity.org/asset_packs/{0}/{0}_ccby.zip" -f $name))
    if ($Proxy) { $a = @('-x', $Proxy) + $a }
    & curl.exe @a; if ($LASTEXITCODE -ne 0) { throw "下载失败：$name" }
    Expand-Archive -Force $zip (Join-Path $HairDest $name); 'done' | Out-File (Join-Path $HairDest "$name\.done")
    Write-Host "完成 $name"
}
Write-Host "服装包已就绪：$Dest；发型包：$HairDest"
