#!/usr/bin/env bash
# 云端：重建角色 → 投影标准照成脸部贴图 → 渲染定妆照底图（Cycles）供检查。用法：bash identity_bake.sh <角色id ...>
cd /root/v11
export BLENDER_USER_RESOURCES=/root/v11/.tools/blender_user V11_CAST_DIR=/root/v11/assets/cast_next V11_MH_COMMUNITY=/root/v11_assets/mh_community V11_NO_LINEUP=1
B=/opt/v11blender/blender
for c in "$@"; do
  find assets/cast_next -maxdepth 1 -name "$c.blend*" -type l -delete
  $B -b --factory-startup -P blender/build_cast.py -- $c > build/logs/idb_build_$c.log 2>&1
  grep -h "CAST OK" build/logs/idb_build_$c.log
  $B -b assets/cast_next/$c.blend -P blender/face_project.py -- $c > build/logs/idb_proj_$c.log 2>&1
  grep -h -E "IDENTITY OK|Error|Traceback" build/logs/idb_proj_$c.log | head -5
done
bash cloud/lookdev_cast.sh "$@" | tail -2
