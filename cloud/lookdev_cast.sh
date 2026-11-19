#!/usr/bin/env bash
# 云端渲染定妆照底图（在重建实例上运行）：每个角色一个 Blender 进程并行，Cycles + OptiX 显卡渲染
# 输出 build/lookdev/<cid>_<view>.png 与深度图，打包成 /root/v11_lookdev.tgz 供本地下载
# 用法：bash lookdev_cast.sh [角色id ...]
cd /root/v11
export BLENDER_USER_RESOURCES=/root/v11/.tools/blender_user V11_CAST_DIR=/root/v11/assets/cast_next V11_MH_COMMUNITY=/root/v11_assets/mh_community
IDS=${@:-lin chen zhou wang mom classA classB}
# 关机备份恢复后，大文件变成指向平台存储的链接（那里不能直接运行程序）：开机后先把 Blender 复制到本机目录
[ -x /opt/v11blender/blender ] || { rm -rf /opt/v11blender; cp -rL /root/v11/.tools/blender /opt/v11blender && chmod -R u+x /opt/v11blender/blender /opt/v11blender/*/python/bin; }
B=/opt/v11blender/blender
mkdir -p build/logs build/lookdev; T0=$(date +%s)
for c in $IDS; do $B -b --factory-startup -P blender/lookdev_renders.py -- $c > build/logs/lookdev_$c.log 2>&1 & done; wait
grep -h -E 'Traceback|Error:' build/logs/lookdev_*.log | grep -v 'Not freed'; ls build/lookdev | wc -l; echo "LOOKDEV $(( $(date +%s) - T0 ))s"
cd build/lookdev && tar -czf /root/v11_lookdev.tgz $(for c in $IDS; do echo ${c}_*.png; done) && echo LOOKDEV DONE
