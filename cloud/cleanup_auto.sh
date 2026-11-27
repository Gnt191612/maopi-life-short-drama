#!/bin/bash
# 云端自动清理（写实化实例上运行，2026-11-27）：只清我们自己的中间产物，模型和镜像自带的东西一律不碰
# 为什么要有它：旧实例 4B5F 用了两周，系统盘堆到 1.12 TB（旧版视频 old_iv*、预览 GIF、结果压缩包、素材包、ComfyUI 输出/临时图、废弃模型），
#   控制台显示「开机速度异常」，连续 6 小时开不了机，最后只能销毁重建，最新的高清首帧也跟着丢了（踩坑记录 62）
# 规则：
#   1) 只删「已经取回本地」的结果：取回脚本每取回一个文件就在 /root/v11_out/.pulled 里记一行，这里只删记过的
#   2) 中间产物（每段视频、临时帧、预览 GIF、压缩包、上传的素材包、ComfyUI output/temp）全部可删
#   3) 写实首帧 kf/ 永远保留（下一轮直接复用，也是唯一不能重算省钱的东西）
#   bash cleanup_auto.sh            # 打印会删什么、能腾出多少
#   bash cleanup_auto.sh --yes      # 真删
O=/root/v11_out; ACT=${1:-}
del() { for p in "$@"; do [ -e "$p" ] || continue; s=$(du -s --block-size=1M "$p" 2>/dev/null | cut -f1); T=$((T + s))
  if [ "$ACT" = "--yes" ]; then rm -rf -- "$p"; echo "已删 ${s}M  $p"; else echo "可删 ${s}M  $p"; fi; done; }
T=0
del $O/vtmp $O/ftmp $O/htmp $O/old_* $O/v_*.gif $O/*.tgz /root/v11_result_*.tgz /root/hf_tmp
del /root/v11_upload/*.zip /root/v11cloud
del /root/ComfyUI/output/* /root/ComfyUI/temp/*
if [ -f $O/.pulled ]; then   # 已取回本地的成品
  while read -r f; do del "$O/$f"; done < $O/.pulled
fi
echo "合计 $((T / 1024)) G"; df -h /root | tail -1
