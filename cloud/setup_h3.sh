#!/bin/bash
# 装 MiniMax H3 + Fun ControlNet Union（写实化实例上运行，2026-11-27）：镜像里已有的跳过，缺的从 Comfy-Org/MiniMax-H3（国内走 hf-mirror）下载
# 仓库文件清单 11-27 已核对（大小）：
#   diffusion_models  minimax_h3_fl2va_pruned_int8_convrot   20.97 GB  首帧模式（默认）
#   diffusion_models  minimax_h3_ref2va_pruned_int8_convrot  20.97 GB  参考图模式（对照）
#   model_patches     minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot  4.53 GB（2.0 需 ComfyUI 0.38+，否则用 1.0：2.30 GB）
#   text_encoders     qwen3vl_32b_minimax_h3_nvfp4_awq        15.69 GB（4090 上 nvfp4 走软件模拟，每段只编码一次，慢一点无妨）
#   vae               minimax_h3_video_vae_int8_convrot 2.81 GB、minimax_h3_audio_vae_fp32 0.61 GB
#   loras             fl2v_turbo_4step_768p / ref2v_turbo_4step（各 1.96 GB）、pika_h3_flex_fl2va_v1 / ref2va_v1（各 1.96 GB，Pika 真实感后训练）
# 全缺时约 75 GB；/root 剩余空间不够就先按 disk_report 清理（要用户确认）
set -e
M=/root/ComfyUI/models; HF=${HF_ENDPOINT:-https://hf-mirror.com}; REPO=Comfy-Org/MiniMax-H3
# 新镜像没有 pip / huggingface-cli 命令（11-27 TDTJ）：用 ComfyUI 自己的 Python 下载
PY=$(for P in /root/miniconda3/envs/comfyui/bin/python /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 /usr/bin/python3; do [ -x "$P" ] && $P -c 'import torch' 2>/dev/null && { echo $P; break; }; done; true)
[ -n "$PY" ] || { echo "找不到装了 torch 的 Python（ComfyUI 环境），停下"; exit 1; }
echo "用 Python：$PY"
get() {   # get <子目录> <文件名>：本地任意位置已有就跳过；优先 ModelScope（11-27 实测 27 MB/s），hf-mirror 只有约 0.4 MB/s 作后备
  local sub=$1 f=$2
  local have=$(find -L $M -name "$f" -size +1M 2>/dev/null | head -1)
  if [ -n "$have" ]; then echo "已有 $f  ($have)"; return; fi
  local free=$(df -BG --output=avail /root | tail -1 | tr -dc 0-9)
  [ "$free" -ge 35 ] || { echo "空间不够下载 $f（剩 ${free}G），停下"; return 1; }
  echo "下载 $f ..."; mkdir -p $M/$sub; local t0=$(date +%s)
  wget -q -c -O $M/$sub/$f.part "https://modelscope.cn/models/Comfy-Org/MiniMax-H3/resolve/master/$sub/$f" \
    || wget -q -c -O $M/$sub/$f.part "$HF/$REPO/resolve/main/$sub/$f" || { echo "下载失败 $f"; rm -f $M/$sub/$f.part; return 1; }
  mv -f $M/$sub/$f.part $M/$sub/$f && echo "装好 $M/$sub/$f（$(( $(date +%s) - t0 )) 秒）"
}
FREE=$(df -BG --output=avail /root | tail -1 | tr -dc 0-9); echo "/root 剩余 ${FREE}G"
[ "$FREE" -ge 30 ] || { echo "磁盘剩余不足 30G，先按 disk_report 清理（需用户确认）"; exit 1; }
V=$(cd /root/ComfyUI && python3 -c "import comfyui_version as v; print(v.__version__)" 2>/dev/null || echo 0)
echo "ComfyUI 版本 $V"
get diffusion_models minimax_h3_fl2va_pruned_int8_convrot.safetensors
get diffusion_models minimax_h3_ref2va_pruned_int8_convrot.safetensors
[ "${H3_BF16:-0}" = 1 ] && ( get diffusion_models minimax_h3_fl2va_pruned_bf16.safetensors && touch /root/v11_out/BF16_READY ) > /root/v11_out/bf16_dl.log 2>&1 &   # 40GB 放后台下，不挡住主版试跑   # 镜像自带完整 bf16（66GB，48G 卡要卸载到内存）；pruned bf16 40GB 输出等效、更省显存   # 40.2 GB：试跑对比全精度效果（效果优先，用户 11-27）
CPY=$PY; : $(for P in /root/miniconda3/envs/comfyui/bin/python /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 python3; do [ -x "$P" ] || command -v $P >/dev/null || continue; $P -c 'import torch' 2>/dev/null && { echo $P; break; }; done; true)
echo "ComfyUI 的 Python：$CPY"
$CPY -c "import torch; v=torch.version.cuda or '0'; print('torch', torch.__version__, 'cuda', v); import sys; sys.exit(0 if tuple(map(int, v.split('.')[:2]))>=(13,0) else 1)" \
  || { echo 'torch 不是 cu130：int8_convrot 可能走慢一点的路径（镜像作者的工作流在同样环境下就用 int8）'; [ "${H3_FP8:-0}" = 1 ] && get diffusion_models minimax_h3_fl2va_pruned_fp8_scaled.safetensors || true; }
python3 -c "import sys; v=[int(x) for x in '$V'.split('.')[:2]]+[0,0]; sys.exit(0 if v[:2]>=[0,38] else 1)" \
  && get model_patches minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot.safetensors \
  || echo "ComfyUI < 0.38，用 ControlNet Union 1.0"
get model_patches minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors
ls $M/text_encoders 2>/dev/null | grep -qi 'h3' || get text_encoders qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
ls $M/vae | grep -qi 'h3.*video' || get vae minimax_h3_video_vae_int8_convrot.safetensors
ls $M/vae | grep -qi 'h3.*audio' || get vae minimax_h3_audio_vae_fp32.safetensors
for f in minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16 minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16 pika_h3_flex_fl2va_v1_bf16 pika_h3_flex_ref2va_v1_bf16; do
  get loras $f.safetensors || echo "LoRA $f 下载失败（对照版会跳过）"
done
rm -rf /root/hf_tmp
curl -s -X POST http://127.0.0.1:8188/api/refresh >/dev/null 2>&1 || true
df -h /root | tail -1
echo H3 SETUP DONE
