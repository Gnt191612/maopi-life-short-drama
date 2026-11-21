#!/usr/bin/env bash
# 云端渲染白模片段（重建实例上运行）：正式画质（Cycles + 深度图），用于写实化输入；顺带合成带配音字幕的预演。
# 素材包 /root/film_assets.tgz 由本地上传（场景、配音、环境光、配乐、口型数据、字体、代码）。
# 用法：bash scene_render.sh s05_00,s05_01     （不带参数 = 全片）
set -e
cd /root/v11
[ -f /root/film_assets.tgz ] && tar -xzf /root/film_assets.tgz -C /root/v11 && rm /root/film_assets.tgz && sed -i 's/\r$//' cloud/*.sh
[ -x /opt/v11blender/blender ] || { rm -rf /opt/v11blender; cp -rL /root/v11/.tools/blender /opt/v11blender && chmod -R u+x /opt/v11blender/blender /opt/v11blender/*/python/bin; }
command -v ffmpeg >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null; }
python3 -c "import numpy" 2>/dev/null || pip install -q numpy
export BLENDER_USER_RESOURCES=/root/v11/.tools/blender_user V11_CAST_DIR=/root/v11/assets/cast_next V11_MH_COMMUNITY=/root/v11_assets/mh_community \
       V11_BLENDER=/opt/v11blender/blender V11_FFMPEG=$(command -v ffmpeg) V11_FFPROBE=$(command -v ffprobe) V11_RHUBARB=/bin/true V11_ONLY=${1:-} \
       V11_PREVIEW=${V11_PREVIEW:-1} V11_PREVIEW_RES=${V11_PREVIEW_RES:-960x540}   # 默认 EEVEE 960x540；要 Cycles 正式画质时传 V11_PREVIEW=0
T0=$(date +%s); python3 run_all.py > build/logs/scene_render.out 2>&1 || true
tail -5 build/logs/run_all.log; echo "SCENE $(( $(date +%s) - T0 ))s"; ls build/previs*/ 2>/dev/null
echo SCENE DONE
