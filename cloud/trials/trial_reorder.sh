#!/bin/bash
# 调整试片队列（11-27 用户要先看两方案对比）：等当前这一条跑完 → 20 步三镜头 → 原生语音 → MOSS → 口型
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
CUR=$1
while kill -0 $CUR 2>/dev/null; do sleep 15; done
cd $S
$PYC video_h3.py $PACK --res 1344x768 --mode fl --only s06_01_0260,s06_01_0446,s06_01_0626 --out $OUT/s20_main > $OUT/s20_main.log 2>&1
echo OK > $OUT/DONE_20STEP
$PYC video_h3.py $PACK --res 1344x768 --mode fl --pika --only s06_01_0626 --speech --out $OUT/pk_speech > $OUT/pk_speech.log 2>&1
( cd /root/v11_upload/moss_trial && . /root/moss/venv/bin/activate && python /root/v11_upload/tts_moss.py dialog.json $OUT/moss > $OUT/trial_moss.log 2>&1; deactivate )
mkdir -p $OUT/fun && cp -f $OUT/pk_main/s06_01_0626.mp4 $OUT/fun/ && bash $S/lipsync.sh run $PACK s06_01_0626 > $OUT/trial_lips.log 2>&1
echo OK > $OUT/DONE_PIKA
