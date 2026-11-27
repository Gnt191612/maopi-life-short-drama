#!/bin/bash
# 云端磁盘清理（写实化实例上运行，2026-11-27）：只删用户确认过的清单，永久删除不可恢复
#   bash cleanup_disk.sh /root/cleanup_list.txt          # 清单每行一个路径；先打印要删的内容和大小
#   bash cleanup_disk.sh /root/cleanup_list.txt --yes    # 真删
# 保护名单（不管清单里写什么都不删）：写实首帧 kf/、上传的脚本、Krea2 二转三和 Qwen 人物替换在用的模型、H3 相关模型、ComfyUI 程序本身
set -e
L=$1; [ -f "$L" ] || { echo "用法：bash cleanup_disk.sh <清单> [--yes]"; exit 1; }
PROTECT='/root/v11_out/kf|/root/v11_upload/scripts|minimax_h3|pika_h3|krea2|Krea2|qwen|Qwen|umt5|/root/ComfyUI/custom_nodes|/root/ComfyUI/comfy|/root/ComfyUI/main.py'
total=0
while read -r p; do
  [ -z "$p" ] && continue; [ "${p:0:1}" = "#" ] && continue
  if echo "$p" | grep -Eq "$PROTECT"; then echo "跳过（保护名单）$p"; continue; fi
  [ -e "$p" ] || { echo "不存在 $p"; continue; }
  s=$(du -s --block-size=1G "$p" 2>/dev/null | cut -f1); total=$((total + s))
  if [ "$2" = "--yes" ]; then rm -rf -- "$p" && echo "已删 ${s}G  $p"; else echo "将删 ${s}G  $p"; fi
done < "$L"
echo "合计 ${total}G"; df -h /root | tail -1
