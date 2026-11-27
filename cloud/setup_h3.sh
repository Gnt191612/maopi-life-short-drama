#!/bin/bash
# 装 MiniMax H3 + Fun ControlNet Union（写实化实例上运行，2026-11-27）：镜像里已有的跳过，缺的从 Comfy-Org/MiniMax-H3（国内走 hf-mirror）下载
# 文件名来自 ComfyUI 官方模板 video_minimax_h3_fun_controlnet_union.json（cloud/wf_templates 里有原件）
set -e
M=/root/ComfyUI/models; HF=${HF_ENDPOINT:-https://hf-mirror.com}; REPO=Comfy-Org/MiniMax-H3
pip show huggingface_hub >/dev/null 2>&1 || pip install -q huggingface_hub
python3 - <<'PY' > /root/h3_repo_files.txt || true
import os
from huggingface_hub import list_repo_files
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
for f in list_repo_files('Comfy-Org/MiniMax-H3'): print(f)
PY
get() {   # get <子目录> <文件名>：本地任意位置已有就跳过；否则在仓库文件列表里找到路径再下载
  local sub=$1 f=$2
  local have=$(find -L $M -name "$f" -size +1M 2>/dev/null | head -1)
  if [ -n "$have" ]; then echo "已有 $f  ($have)"; return; fi
  local path=$(grep -m1 "/$f\$\|^$f\$" /root/h3_repo_files.txt)
  [ -n "$path" ] || { echo "仓库里找不到 $f"; return 1; }
  echo "下载 $f ..."; mkdir -p $M/$sub /root/hf_tmp
  HF_ENDPOINT=$HF huggingface-cli download $REPO "$path" --local-dir /root/hf_tmp
  mv -f "/root/hf_tmp/$path" $M/$sub/$f && echo "装好 $M/$sub/$f"
}
# 镜像里如果已有其它精度的同名模型（比如 bf16 / fp8 版），video_h3.py 会按关键词自己挑，这里只补缺
ls $M/diffusion_models | grep -qi 'h3.*ref2v\|ref2v.*h3' || get diffusion_models minimax_h3_ref2va_pruned_int8_convrot.safetensors
get model_patches minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors
ls $M/text_encoders | grep -qi 'h3' || get text_encoders qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
ls $M/vae | grep -qi 'h3.*video' || get vae minimax_h3_video_vae_int8_convrot.safetensors
ls $M/vae | grep -qi 'h3.*audio' || get vae minimax_h3_audio_vae_fp32.safetensors
get loras minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors || true
rm -rf /root/hf_tmp
curl -s -X POST http://127.0.0.1:8188/api/refresh >/dev/null 2>&1 || true
df -h /root | tail -1
echo H3 SETUP DONE
