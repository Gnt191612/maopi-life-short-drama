# 快速审片（本地）：只搭建片段（不渲全部帧）→ 每个镜头渲开头、中间两帧 → 拼成总览图 build\review\<片段>.jpg
# 用法：powershell -ExecutionPolicy Bypass -File blender\tests\shot_review.ps1 s06_01,s07_01
param([Parameter(Mandatory = $true)][string]$Segs)
$ErrorActionPreference = 'Continue'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent; Push-Location $Root
$BL = Join-Path $Root '.tools\blender\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $Root '.tools\blender_user'; $env:PYTHONIOENCODING = 'utf-8'; $env:V11_PREVIEW = '1'
$env:V11_SYSPY = (Get-Command python).Source
Remove-Item Env:V11_CAST_DIR -ErrorAction SilentlyContinue
$Logs = Join-Path $Root 'build\logs'; New-Item -ItemType Directory -Force $Logs | Out-Null
function Low([string[]]$a, [string]$log) {
    $p = Start-Process -FilePath $BL -ArgumentList $a -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WorkingDirectory $Root
    $p.PriorityClass = 'BelowNormal'; $p.WaitForExit()
}
foreach ($s in ($Segs -split ',')) {
    Remove-Item (Join-Path $Root "build\review\$s") -Recurse -Force -ErrorAction SilentlyContinue
    Low @('-b', '--factory-startup', '-P', 'blender\shoot_segment.py', '--', $s, '--norender') "$Logs\review_build_$s.log"
    Select-String "$Logs\review_build_$s.log" -Pattern 'SEGMENT BUILT|CAM FALLBACK|EST CLEAR|Traceback|Error' | ForEach-Object { '  ' + $_.Line.Substring(0, [Math]::Min(150, $_.Line.Length)) }
    if (-not (Select-String "$Logs\review_build_$s.log" -Pattern 'SEGMENT BUILT' -Quiet)) { "  BUILD FAILED $s（不渲染，避免拿旧文件出图）："; Get-Content "$Logs\review_build_$s.log.err" -Tail 6 | ForEach-Object { '    ' + $_ }; continue }
    Low @('-b', "build\shots\$s.blend", '--factory-startup', '-P', 'blender\tests\shot_review.py', '--', $s) "$Logs\review_render_$s.log"
    & python -c "import cv2,glob,numpy as np,sys,os; s=sys.argv[1]; fs=sorted(glob.glob(os.path.join('build','review',s,'*_a.png'))); t=[]
for f in fs:
    a=cv2.resize(cv2.imread(f),(400,225)); b=cv2.resize(cv2.imread(f.replace('_a.png','_b.png')),(400,225)); r=np.hstack([a,b]); cv2.putText(r,os.path.basename(f)[:4],(5,20),0,0.6,(0,255,255),2); t.append(r)
t+= [np.zeros_like(t[0])]*(len(t)%2)
cv2.imwrite(os.path.join('build','review',s+'.jpg'),np.vstack([np.hstack(t[i:i+2]) for i in range(0,len(t),2)]),[cv2.IMWRITE_JPEG_QUALITY,85]); print('SHEET',s,len(fs))" $s
}
Pop-Location
