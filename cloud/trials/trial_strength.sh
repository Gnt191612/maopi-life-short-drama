#!/bin/bash
# 控制强度测试（11-27）：Pika 版 0260 用官方默认强度 pose 1.0 + depth 1.0，看构图/朝向是否跟住白模；排在 20 步三镜头之后
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
while [ ! -f $OUT/DONE_20STEP ]; do sleep 30; done
cd $S
$PYC video_h3.py $PACK --res 1344x768 --mode fl --pika --pose 1.0 --depth 1.0 --only s06_01_0260 --out $OUT/pk_s10 > $OUT/pk_s10.log 2>&1
echo OK > $OUT/DONE_S10
