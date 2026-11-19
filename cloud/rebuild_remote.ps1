# 在仙宫云上重建人物（本地运行）：同步代码 → 云端并行重建 7 人 + 检查图 → 下载 .blend 与检查图到本地
# 用法：powershell -ExecutionPolicy Bypass -File cloud\rebuild_remote.ps1 -SshHost root@xxx.ssh.x-gpu.com -Port 12345 [角色id ...]
#       实例需先开机；连接地址在仙宫云控制台「SSH」里看（每台实例不同）。-NoBlend 只下载检查图
param([Parameter(Mandatory = $true)][string]$SshHost, [Parameter(Mandatory = $true)][int]$Port, [switch]$NoBlend, [switch]$Export,
      [Parameter(ValueFromRemainingArguments = $true)][string[]]$Ids)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Key = Join-Path $env:USERPROFILE '.ssh\xiangongyun_ed25519'
$Opt = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new')
$Tmp = Join-Path $env:TEMP 'v11_code.tgz'
Push-Location $Root
try {
    Write-Host '[1/3] 同步代码'
    & tar.exe -czf $Tmp --exclude=__pycache__ config.py blender story cloud
    & scp.exe @Opt -P $Port $Tmp "${SshHost}:/root/v11_code.tgz"
    & ssh.exe @Opt -p $Port $SshHost "tar -xzf /root/v11_code.tgz -C /root/v11 && sed -i 's/\r$//' /root/v11/cloud/*.sh"
    Write-Host '[2/3] 云端重建（并行）'
    $ex = if ($Export) { 'EXPORT=1 ' } else { '' }
    & ssh.exe @Opt -p $Port $SshHost "${ex}bash /root/v11/cloud/rebuild_cast.sh $($Ids -join ' ')"
    Write-Host '[3/3] 下载结果'
    $sel = if ($Ids) { $Ids } else { @('lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB') }
    New-Item -ItemType Directory -Force build\renders\outfit_check, build\renders\side_heads, assets\cast_next | Out-Null
    & ssh.exe @Opt -p $Port $SshHost "cd /root/v11/build/renders && tar -czf /root/v11_checks.tgz outfit_check side_heads"
    & scp.exe @Opt -P $Port "${SshHost}:/root/v11_checks.tgz" $Tmp; & tar.exe -xzf $Tmp -C build\renders
    if (-not $NoBlend) { foreach ($c in $sel) { & scp.exe @Opt -P $Port "${SshHost}:/root/v11/assets/cast_next/$c.blend" assets\cast_next\ } }
    if ($Export) {   # 只下载 GLB（比 base64 的 .js 小 1/4），本地再包成审阅器格式
        New-Item -ItemType Directory -Force build\viewer_tmp | Out-Null
        $glbs = foreach ($c in $sel) { & scp.exe @Opt -P $Port "${SshHost}:/root/v11/build/viewer_tmp/$c.glb" build\viewer_tmp\; "build\viewer_tmp\$c.glb" }
        & python viewer\glb_to_js.py @glbs
    }
    & python blender\tests\heads_sheet.py @sel
} finally { Pop-Location; Remove-Item $Tmp -ErrorAction SilentlyContinue }
Write-Host '完成。检查图在 build\renders\outfit_check 与 side_heads；加 -Export 时审阅器模型已更新（双击 viewer\启动人物审阅.bat，开着的按 F5）'
