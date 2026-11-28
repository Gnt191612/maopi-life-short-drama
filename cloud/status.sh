#!/bin/bash
# 云端一览（11-28）：时间、显卡、ComfyUI 队列、视频/首帧进程和日志尾巴、磁盘。本地：ssh ... 'bash /root/v11_upload/scripts/status.sh'
OUT=/root/v11_out
date +%T
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
curl -s localhost:8188/queue | python3 -c 'import json,sys;d=json.load(sys.stdin);print("队列 运行", len(d["queue_running"]), "等待", len(d["queue_pending"]))'
ps aux | grep -E '[v]ideo_h3|[k]eyframes.py|[f]ull_video|[l]ipsync' | awk '{print $2, $12, $13, $14, $NF}'
echo "--- 视频 20 步"; tail -2 $OUT/full_video_full.log
echo "--- 视频 Pika"; tail -2 $OUT/full_video_pika.log
echo "--- 最近完成/失败"; for L in $OUT/full_video_full.log $OUT/full_video_pika.log; do tail -300 $L | grep -a -E '^[0-9:]+ .*(完成|失败|不够)' | cut -c1-160; done | sort | tail -${1:-4}
echo "--- 尾帧"; tail -2 $OUT/kf_end.log 2>/dev/null; echo "尾帧 $(ls $OUT/kf | grep -c @end) 张"
echo "--- 视频 $(ls $OUT/fun/*.mp4 2>/dev/null | wc -l) 个"; df -h /root | tail -1 | awk '{print "磁盘剩余", $4}'
