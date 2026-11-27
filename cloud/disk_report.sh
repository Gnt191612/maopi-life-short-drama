#!/bin/bash
# 云端磁盘清理前的清单（只看不删，2026-11-27）：列出大目录、大模型文件，分成「建议删除 / 必须保留 / 待确认」，写到 /root/disk_report.txt
# 删除由用户确认清单后另行执行（永久删除不可恢复）
R=/root/disk_report.txt; : > $R
say() { echo "$@" | tee -a $R; }
say "== 整体"; df -h /root | tee -a $R
say; say "== /root 下各目录（GB）"; du -x -s --block-size=1G /root/* /root/.[!.]* 2>/dev/null | sort -rn | head -30 | tee -a $R
say; say "== ComfyUI/models 各子目录（GB）"; du -s --block-size=1G /root/ComfyUI/models/* 2>/dev/null | sort -rn | tee -a $R
say; say "== 大于 2GB 的模型文件"; find -L /root/ComfyUI/models -type f -size +2G -printf '%s\t%p\n' 2>/dev/null | sort -rn | awk -F'\t' '{printf "%6.1f GB  %s\n", $1/1e9, $2}' | tee -a $R
say; say "== 我们的中间产物（结果都已取回本地）"
for d in /root/v11_out/old_* /root/v11_out/vtmp /root/v11_out/ftmp /root/v11_out/v_*.gif /root/v11_result_*.tgz /root/v11_upload/*.zip /root/v11cloud /root/ComfyUI/output /root/ComfyUI/temp; do
  [ -e "$d" ] && du -s --block-size=1M $d 2>/dev/null; done | sort -rn | awk '{printf "%8.1f GB  %s\n", $1/1024, $2}' | tee -a $R
say; say "== 必须保留：/root/v11_out/kf（写实首帧，新方案直接复用）、/root/v11_upload/scripts、Krea2 二转三与 Qwen 人物替换用到的模型"
say "== 当前工作流引用的模型（用到的就不能删）"
grep -ho '"[^"]*\.\(safetensors\|gguf\|pth\|pt\|ckpt\)"' /root/ComfyUI/user/default/workflows/*.json 2>/dev/null | sort | uniq -c | sort -rn | head -60 | tee -a $R
echo "清单写在 $R"
