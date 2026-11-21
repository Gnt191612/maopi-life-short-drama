#!/usr/bin/env bash
# 云端用 Blender 打开一个角色文件跑脚本（调试/检查用）：bash bl_run.sh <角色id> <脚本.py> [过滤关键词]
cd /root/v11
export BLENDER_USER_RESOURCES=/root/v11/.tools/blender_user V11_CAST_DIR=/root/v11/assets/cast_next V11_MH_COMMUNITY=/root/v11_assets/mh_community
/opt/v11blender/blender -b assets/cast_next/$1.blend --python $2 -- $1 2>&1 | grep -E "${3:-.}" | head -120
