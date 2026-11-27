#!/bin/bash
# 跑 MOSS-TTSD 对话配音（11-27）：先让 ComfyUI 释放显存（它跑完视频后一直占着 30 多 GB，MOSS 会 CUDA out of memory），再在 MOSS 自己的 venv 里跑
# 用法：bash run_moss.sh [对话目录，默认 /root/v11_upload/moss_trial] [输出目录，默认 /root/v11_out/moss]
D=${1:-/root/v11_upload/moss_trial}; O=${2:-/root/v11_out/moss}
curl -s -X POST http://127.0.0.1:8188/free -H 'Content-Type: application/json' -d '{"unload_models":true,"free_memory":true}' >/dev/null; sleep 5
nvidia-smi --query-gpu=memory.used --format=csv,noheader
cd $D && /root/moss/venv/bin/python /root/v11_upload/tts_moss.py dialog.json $O
