#!/usr/bin/env bash
# 云端人物重建（在仙宫云实例上运行，由本地 cloud/rebuild_remote.ps1 调用）：
# 每个角色一个 Blender 进程并行重建，再并行渲染全身检查图（outfit_check）与头部特写（side_heads）。
# 用法：bash rebuild_cast.sh [角色id ...]    （不带参数 = 全部 7 人）
cd /root/v11
export BLENDER_USER_RESOURCES=/root/v11/.tools/blender_user V11_CAST_DIR=/root/v11/assets/cast_next \
       V11_MH_COMMUNITY=/root/v11_assets/mh_community V11_NO_LINEUP=1
B=/root/v11/.tools/blender/blender; IDS=${@:-lin chen zhou wang mom classA classB}
mkdir -p $V11_CAST_DIR build/logs; rm -f build/logs/*.log; T0=$(date +%s)
for c in $IDS; do $B -b --factory-startup -P blender/build_cast.py -- $c > build/logs/build_$c.log 2>&1 & done; wait
grep -h -E 'CAST OK|Traceback|Error' build/logs/build_*.log | grep -v 'Error: Not freed' ; echo "BUILD $(( $(date +%s) - T0 ))s"
T1=$(date +%s)
for c in $IDS; do
  $B -b --factory-startup -P blender/tests/outfit_check.py -- $c > build/logs/outfit_$c.log 2>&1 &
  $B -b --factory-startup -P blender/tests/side_heads.py -- $c > build/logs/heads_$c.log 2>&1 &
done; wait
grep -h -E 'OUTFIT OK|SIDE OK|Traceback' build/logs/outfit_*.log build/logs/heads_*.log; echo "CHECKS $(( $(date +%s) - T1 ))s"
if [ "$EXPORT" = 1 ]; then   # 导出给人物审阅器（viewer/models/<id>.js）
  T2=$(date +%s)
  for c in $IDS; do $B -b --factory-startup -P blender/export_viewer.py -- $c > build/logs/export_$c.log 2>&1 & done; wait
  grep -h -E 'Traceback' build/logs/export_*.log; ls -la viewer/models; echo "EXPORT $(( $(date +%s) - T2 ))s"
fi
echo REBUILD DONE
