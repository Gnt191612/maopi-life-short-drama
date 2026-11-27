#!/bin/bash
# 接在 trial_pika.sh 之后：20 步（不加 Pika）+ 新提示词跑同样的连续三镜头，供和 Pika 版完整对比（用户 11-27 要求看完整片段再判断）
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
while [ ! -f $OUT/DONE_PIKA ]; do sleep 30; done
cd $S
$PYC video_h3.py $PACK --res 1344x768 --mode fl --only s06_01_0260,s06_01_0446,s06_01_0626 --out $OUT/s20_main > $OUT/s20_main.log 2>&1
echo OK > $OUT/DONE_20STEP
