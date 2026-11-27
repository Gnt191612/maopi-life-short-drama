#!/bin/bash
# 磁盘体检（每次开机后、每轮开跑前自动运行，2026-11-27）：系统盘超过阈值就先清理再继续，避免像 4B5F 那样堆到开不了机
#   bash disk_guard.sh [最少剩余G=80] [最多已用G=400]
MINFREE=${1:-80}; MAXUSED=${2:-400}; S=$(dirname "$0")
read USED FREE <<< $(df -BG --output=used,avail /root | tail -1 | tr -dc '0-9 \n')
echo "系统盘已用 ${USED}G、剩余 ${FREE}G（底线：剩余 ≥ ${MINFREE}G、已用 ≤ ${MAXUSED}G）"
if [ "$FREE" -lt "$MINFREE" ] || [ "$USED" -gt "$MAXUSED" ]; then
  echo "超过底线，自动清理中间产物"; bash $S/cleanup_auto.sh --yes | tail -3
  read USED FREE <<< $(df -BG --output=used,avail /root | tail -1 | tr -dc '0-9 \n')
  if [ "$FREE" -lt "$MINFREE" ]; then
    echo "DISK_LOW：清完中间产物仍只剩 ${FREE}G。最大的目录：" ; du -x -s --block-size=1G /root/* 2>/dev/null | sort -rn | head -8
    exit 2   # 调用方看到 2 就停下，把清单发给用户决定删哪些模型
  fi
fi
echo DISK_OK
