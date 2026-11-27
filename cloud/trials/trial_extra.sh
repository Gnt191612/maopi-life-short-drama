#!/bin/bash
# 试片追加对照（11-27）：等 trial_h3.sh 跑完（DONE_TRIAL）立刻接着跑，显卡不空转
#   a) 新提示词（首帧模式不写场景，踩坑 65）重跑主版 0626 → h3_new/
#   b) 新提示词 + 深度控制加强到 0.6，跑有走位的 0260 → h3_d06/（验证构图是否跟住白模）
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
while [ ! -f $OUT/DONE_TRIAL ]; do sleep 30; done
cd $S
$PYC video_h3.py $PACK --only s06_01_0626 --res 1344x768 --mode fl --out $OUT/h3_new > $OUT/trial_extra_a.log 2>&1
$PYC video_h3.py $PACK --only s06_01_0260 --res 1344x768 --mode fl --depth 0.6 --out $OUT/h3_d06 > $OUT/trial_extra_b.log 2>&1
echo OK > $OUT/DONE_EXTRA
