#!/bin/bash
# 【备选】H3 效果不行时才用；现行方案见 docs/模型选型.md。
# 装 Wan2.2 Fun Control 14B（写实化实例上运行，2026-11-27）：先在 ComfyUI/models 里找，已有就跳过，没有才从 Hugging Face（国内走 hf-mirror）下载
# 来源：Comfy-Org 官方重新打包的仓库（ComfyUI 官方教程 docs.comfy.org/tutorials/video/wan/wan2-2-fun-control 用的同一批文件）
#   diffusion_models  wan2.2_fun_control_high_noise_14B_fp8_scaled.safetensors  约 14.3 GB
#   diffusion_models  wan2.2_fun_control_low_noise_14B_fp8_scaled.safetensors   约 14.3 GB
#   loras             wan2.2_i2v_lightx2v_4steps_lora_v1_{high,low}_noise.safetensors  各约 1.2 GB
#   text_encoders     umt5_xxl_fp8_e4m3fn_scaled.safetensors  约 6.7 GB（镜像里多半已有）
#   vae               wan_2.1_vae.safetensors                 约 0.25 GB（镜像里多半已有）
#   RIFE 插帧（ComfyUI-Frame-Interpolation）镜像自带工作流在用，一般已装
set -e
M=/root/ComfyUI/models; HF=${HF_ENDPOINT:-https://hf-mirror.com}
pip show huggingface_hub >/dev/null 2>&1 || pip install -q huggingface_hub
get() {   # get <子目录> <仓库> <仓库内路径>
  local sub=$1 repo=$2 path=$3 f=$(basename $3)
  local have=$(find -L $M -name "$f" -size +1M 2>/dev/null | head -1)
  if [ -n "$have" ]; then echo "已有 $f  ($have)"; return; fi
  echo "下载 $f ..."; mkdir -p $M/$sub /root/hf_tmp
  HF_ENDPOINT=$HF huggingface-cli download $repo $path --local-dir /root/hf_tmp
  mv -f /root/hf_tmp/$path $M/$sub/$f && echo "装好 $M/$sub/$f"
}
R22=Comfy-Org/Wan_2.2_ComfyUI_Repackaged; R21=Comfy-Org/Wan_2.1_ComfyUI_repackaged
get diffusion_models $R22 split_files/diffusion_models/wan2.2_fun_control_high_noise_14B_fp8_scaled.safetensors
get diffusion_models $R22 split_files/diffusion_models/wan2.2_fun_control_low_noise_14B_fp8_scaled.safetensors
get loras $R22 split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
get loras $R22 split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors
get text_encoders $R21 split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
get vae $R22 split_files/vae/wan_2.1_vae.safetensors
rm -rf /root/hf_tmp
# 让 ComfyUI 重新扫描模型列表（新文件要出现在下拉框里，video_fun.py 才能核对通过）
curl -s -X POST http://127.0.0.1:8188/api/refresh >/dev/null 2>&1 || true
df -h /root | tail -1
echo FUN SETUP DONE
