#!/bin/bash
# 把 ComfyUI 环境还原成镜像原版（11-27 事故：setup_moss.sh 的 uv pip 误装进了 ComfyUI 环境，换掉了 torch/transformers/numpy 等 13 个包）
# 版本清单来自那次安装日志里的「- 旧版本」行；torch 2.8.0 走腾讯 PyPI 镜像（Linux 版自带 cu128），不走慢的 pytorch.org
PYC=/root/miniconda3/envs/comfyui/bin/python
export UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple UV_HTTP_TIMEOUT=300
$PYC -m uv pip install --python $PYC \
  torch==2.8.0 torchaudio==2.8.0 triton==3.4.0 nvidia-nccl-cu12==2.27.3 \
  transformers==4.51.3 tokenizers==0.21.1 huggingface-hub==0.36.2 hf-xet==1.5.2 safetensors==0.8.0 \
  numpy==2.3.2 scipy==1.18.0 pyyaml==6.0.2 typing-inspection==0.4.0
$PYC -m uv pip uninstall --python $PYC moss-tts nvidia-nvshmem-cu12 2>/dev/null
$PYC -c "import torch, transformers, numpy, cv2; print('还原后', torch.__version__, torch.version.cuda, transformers.__version__, numpy.__version__, cv2.__version__, torch.cuda.is_available())"
echo RESTORE DONE
