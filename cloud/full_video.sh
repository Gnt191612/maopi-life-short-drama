#!/bin/bash
# 全片视频阶段（11-27）：接在 full_fun.ps1 -KeysOnly 之后，首帧做完立刻接上（平台空闲 15 分钟自动关机，不能断档）
#   等 DONE_KEYS → 等首帧审查（KF_REVIEWED，最多等 12 分钟）→ SageAttention 重启 ComfyUI（测过画质不变、快约 23%）
#   → 混合方案先跑全部 20 步镜头、再跑全部 Pika 镜头（少切换模型）→ 释放显存 → 口型同步 → DONE_FULL
# 用法：nohup bash full_video.sh > /root/full_video.log 2>&1 &     （口型镜头清单 /root/v11_upload/voice_list.txt）
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
rm -f $OUT/DONE_FULL
while [ ! -f $OUT/DONE_KEYS ]; do sleep 20; done
for i in $(seq 1 36); do [ -f $OUT/KF_REVIEWED ] && break; sleep 20; done   # 首帧审查（本地取回逐张看），最多等 12 分钟
echo "$(date +%T) 开始视频" >> $OUT/full_video_progress.log
bash $S/comfy_restart.sh --use-sage-attention >> $OUT/full_video_progress.log 2>&1 || { echo COMFY_FAIL > $OUT/DONE_FULL; exit; }
cd $S
$PYC video_h3.py $PACK --res 1344x768 --out $OUT/fun --hybrid --subset full > $OUT/full_video_full.log 2>&1
echo "$(date +%T) 20 步镜头完成" >> $OUT/full_video_progress.log
$PYC video_h3.py $PACK --res 1344x768 --out $OUT/fun --hybrid --subset pika > $OUT/full_video_pika.log 2>&1
echo "$(date +%T) Pika 镜头完成" >> $OUT/full_video_progress.log
# 中途被重拍单个镜头时（删了 fun/<id>.mp4），这两行会补上；已有的跳过
$PYC video_h3.py $PACK --res 1344x768 --out $OUT/fun --hybrid > $OUT/full_video_rest.log 2>&1
curl -s -X POST http://127.0.0.1:8188/free -H 'Content-Type: application/json' -d '{"unload_models":true,"free_memory":true}' >/dev/null; sleep 5
bash $S/lipsync.sh run $PACK $(cat /root/v11_upload/voice_list.txt) > $OUT/full_lips.log 2>&1
echo "$(date +%T) 口型同步完成" >> $OUT/full_video_progress.log
touch $OUT/DONE_FULL
