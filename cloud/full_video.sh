#!/bin/bash
# 全片视频阶段（11-27）：和首帧生成同时进行，只做「首帧已审过合格」的镜头（/root/v11_out/kf_ok.txt，本地审完一批推上来一批）
#   循环：20 步镜头一轮 → Pika 镜头一轮 → 没有新的可做就等 60 秒（首帧生成还在跑，显卡不空）→ 129 个都做完后口型同步 → DONE_FULL
#   要停：touch /root/v11_out/STOP_VIDEO
# 11-27 教训：上一版只看 DONE_KEYS 标记，失败的那次首帧运行也写了标记，视频提前开跑、还重启 ComfyUI 打断了首帧生成。现在不依赖标记，也不重启 ComfyUI。
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
rm -f $OUT/DONE_FULL; cd $S
TOTAL=$(ls -d $PACK/s*_*_* | wc -l)
while [ ! -f $OUT/STOP_VIDEO ]; do
  n0=$(ls $OUT/fun/*.mp4 2>/dev/null | wc -l)
  find /root/ComfyUI/output /root/ComfyUI/temp -type f -mmin +60 -delete 2>/dev/null   # 视频脚本已取走的逐帧中间图（11-28：积到 6G，系统盘只剩 14G）
  $PYC video_h3.py $PACK --res 1344x768 --out $OUT/fun --hybrid --subset full --approved $OUT/kf_ok.txt >> $OUT/full_video_full.log 2>&1
  $PYC video_h3.py $PACK --res 1344x768 --out $OUT/fun --hybrid --subset pika --approved $OUT/kf_ok.txt >> $OUT/full_video_pika.log 2>&1
  n1=$(ls $OUT/fun/*.mp4 2>/dev/null | wc -l)
  echo "$(date +%T) 视频 $n1/$TOTAL" >> $OUT/full_video_progress.log
  [ $n1 -ge $TOTAL ] && break
  [ $n1 -eq $n0 ] && sleep 60
done
curl -s -X POST http://127.0.0.1:8188/free -H 'Content-Type: application/json' -d '{"unload_models":true,"free_memory":true}' >/dev/null; sleep 5
bash $S/lipsync.sh run $PACK $(cat /root/v11_upload/voice_list.txt) > $OUT/full_lips.log 2>&1
echo "$(date +%T) 口型同步完成" >> $OUT/full_video_progress.log
touch $OUT/DONE_FULL
