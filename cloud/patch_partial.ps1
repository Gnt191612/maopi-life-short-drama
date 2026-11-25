# 局部补拍模板：powershell -File cloud\patch_partial.ps1 -Segs s01_01,s03_01 -Beats s01_02,s03_01 -Tag v15 [-WaitFor 上一批日志]
#   -Beats 留空 = 整段重拍；结果：build\logs\patch_<Tag>.log / patch_<Tag>_tasks.txt（受影响的云端任务）
# 第二批局部补拍（11-24 夜关键帧检查发现的问题）：躺着举手机、挥手、通知特写、s01 床上手机 → 等第一批补拍结束后自动开始
param([string]$Segs = 's01_01,s02_01,s03_01,s04_00', [string]$Beats = 's01_02,s01_06,s01_11,s01_12,s01_13,s01_17,s02_02,s02_08c,s02_08d,s03_01,s03_02,s04_02,s04_06', [string]$Tag = 'v10', [string]$WaitFor = "$R\build\logs\patch_v9.log")
$ErrorActionPreference = 'Continue'
$R = Split-Path $PSScriptRoot -Parent   # 仓库根目录（原来写死 D:\v11）
Set-Location $R
$log = "$R\build\logs\patch_$Tag.log"
function L($m) { Add-Content $log -Encoding utf8 -Value ("{0:MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) }
if ($WaitFor) { L "等待 $WaitFor 完成"; while (-not (Select-String $WaitFor -Pattern '全部完成' -Quiet -ErrorAction SilentlyContinue)) { Start-Sleep 30 } }
$env:BLENDER_USER_RESOURCES = "$R\.tools\blender_user"; $env:PYTHONIOENCODING = 'utf-8'
$env:V11_MH_COMMUNITY = 'E:\v11_assets\mh_community'; $env:V11_NO_LINEUP = '1'; $env:V11_PREVIEW = '1'
L "补拍开始 $Segs | $Beats"
foreach ($s in ($Segs -split ',')) { Remove-Item "$R\build\shots\$s.blend", "$R\build\shots\$s`_timeline.json", "$R\build\shots\$s`_cuts.json" -Force -ErrorAction SilentlyContinue }
$env:V11_ONLY = $Segs; $env:V11_RENDER_BEATS = $Beats
$p = Start-Process python -ArgumentList 'run_all.py' -NoNewWindow -PassThru -RedirectStandardOutput "$R\build\logs\patch_$Tag`_render.log" -RedirectStandardError "$R\build\logs\patch_$Tag`_render.err" -WorkingDirectory $R
$p.PriorityClass = 'BelowNormal'; $p.WaitForExit(); L '补拍结束'
Remove-Item Env:V11_ONLY
$p = Start-Process "$R\.tools\blender\blender.exe" -ArgumentList (@('-b','--factory-startup','-P','blender\tests\clip_check.py','--') + ($Segs -split ',') + @('--step','48')) -NoNewWindow -PassThru -RedirectStandardOutput "$R\build\logs\patch_$Tag`_clip.log" -RedirectStandardError "$R\build\logs\patch_$Tag`_clip.err"
$p.PriorityClass = 'BelowNormal'; $p.WaitForExit(); L '穿模检查结束'
$p = Start-Process python -ArgumentList (@('cloud\pack_for_cloud.py','--pose','--update') + ($Segs -split ',')) -NoNewWindow -PassThru -RedirectStandardOutput "$R\build\logs\patch_$Tag`_pack.log" -RedirectStandardError "$R\build\logs\patch_$Tag`_pack.err" -WorkingDirectory $R
$p.PriorityClass = 'BelowNormal'; $p.WaitForExit(); L ("增量打包：{0}" -f ((Get-Content "$R\build\logs\patch_$Tag`_pack.log" -Tail 1 -Encoding utf8) -join ''))
$env:PB = $Beats; $env:PS_ = $Segs; $env:PT = $Tag
& python -c "import json,os; b=set(os.environ['PB'].split(',')); s=set(os.environ['PS_'].split(',')); man=json.load(open(r'dist\cloud_pack\manifest.json',encoding='utf-8'))['tasks']; out=[t for t in man if t.rsplit('_',1)[0] in s and b & set(json.load(open(os.path.join('dist','cloud_pack',t,'task.json'),encoding='utf-8'))['beats'])]; open(r'build\logs\patch_%s_tasks.txt'%os.environ['PT'],'w').write(','.join(out)); print(len(out), out)" *>> $log
L '全部完成'