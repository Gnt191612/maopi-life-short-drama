#!/bin/bash
# 按镜像原来的启动方式重启 ComfyUI，可加额外参数（11-27：SageAttention 测试用 --use-sage-attention）
# 用法：bash comfy_restart.sh [额外参数...]   例：bash comfy_restart.sh --use-sage-attention
screen -S comfyui -X quit 2>/dev/null; pkill -f 'python main.py --enable-cors-header' 2>/dev/null; sleep 5
screen -d -m -L -Logfile /tmp/comfyui.log -S comfyui bash -l -c "source /root/miniconda3/etc/profile.d/conda.sh; conda activate comfyui; cd /root/ComfyUI; LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 python main.py --enable-cors-header --listen 0.0.0.0 $*"
for i in $(seq 1 120); do curl -s -o /dev/null http://127.0.0.1:8188/system_stats && { echo "ComfyUI 已启动（$i×5 秒）参数：$*"; exit 0; }; sleep 5; done
echo "ComfyUI 10 分钟没起来，看 /tmp/comfyui.log"; exit 1
