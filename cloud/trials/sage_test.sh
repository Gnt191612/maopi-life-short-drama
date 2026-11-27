#!/bin/bash
# SageAttention 测试（11-27 用户要求先试）：同一镜头、同一种子、同一提示词，只跑前 77 帧（约 3 秒），20 步各跑一次：不开 / 开 SageAttention，比速度和画质
OUT=/root/v11_out; S=/root/v11_upload/scripts; PACK=/root/v11cloud/cloud_pack; PYC=/root/miniconda3/envs/comfyui/bin/python
cd $S
V="$PYC video_h3.py $PACK --res 1344x768 --mode fl --only s06_01_0260 --frames 77 --force"
echo "== 不开 SageAttention $(date +%T)" > $OUT/sage_test.log
grep -a -o 'Using [a-z ]*attention' /tmp/comfyui.log | tail -1 >> $OUT/sage_test.log
$V --out $OUT/sage_off >> $OUT/sage_test.log 2>&1
grep -a -E '[0-9]+/20 \[' /tmp/comfyui.log | tr '\r' '\n' | grep -E '20/20' | tail -1 >> $OUT/sage_test.log
echo "== 重启 ComfyUI 加 --use-sage-attention $(date +%T)" >> $OUT/sage_test.log
bash $S/comfy_restart.sh --use-sage-attention >> $OUT/sage_test.log 2>&1
grep -a -o 'Using [a-z ]*attention' /tmp/comfyui.log | tail -1 >> $OUT/sage_test.log
$V --out $OUT/sage_on >> $OUT/sage_test.log 2>&1
tail -c 3000 /tmp/comfyui.log | tr '\r' '\n' | grep -E '20/20' | tail -1 >> $OUT/sage_test.log
echo SAGE_DONE >> $OUT/sage_test.log
