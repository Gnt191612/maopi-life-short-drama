#!/bin/bash
# Pika 方案验证（11-27，用户看过对比后认定 Pika 版质感更好）：停掉 20 步对照队列，只验证 Pika + 新提示词
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
pkill -f trial_extra.sh; pkill -f trial_h3.sh; pkill -f video_h3.py; sleep 2
curl -s -X POST http://127.0.0.1:8188/queue -H 'Content-Type: application/json' -d '{"clear":true}' >/dev/null
curl -s -X POST http://127.0.0.1:8188/interrupt >/dev/null; sleep 5
rm -f $OUT/DONE_PIKA
cd $S
V="$PYC video_h3.py $PACK --res 1344x768 --mode fl --pika"
$V --only s06_01_0260,s06_01_0446,s06_01_0626 --out $OUT/pk_main > $OUT/pk_main.log 2>&1        # 1) 连续三镜头，新提示词
$V --only s06_01_0260 --depth 0.6 --out $OUT/pk_d06 > $OUT/pk_d06.log 2>&1                         # 2) 深度加强，看构图是否跟住白模
$V --only s06_01_0626 --speech --out $OUT/pk_speech > $OUT/pk_speech.log 2>&1                      # 3) H3 原生语音
# 4) MOSS-TTSD 对话配音（环境没装好就跳过并记下）
if [ -x /root/moss/venv/bin/python ]; then
  ( cd /root/v11_upload/moss_trial && . /root/moss/venv/bin/activate && python /root/v11_upload/tts_moss.py dialog.json $OUT/moss > $OUT/trial_moss.log 2>&1; deactivate )
else echo "MOSS 环境不在，跳过" > $OUT/trial_moss.log; fi
# 5) 口型同步：对 Pika 新版 0626
mkdir -p $OUT/fun && cp -f $OUT/pk_main/s06_01_0626.mp4 $OUT/fun/ && bash $S/lipsync.sh run $PACK s06_01_0626 > $OUT/trial_lips.log 2>&1
echo OK > $OUT/DONE_PIKA
