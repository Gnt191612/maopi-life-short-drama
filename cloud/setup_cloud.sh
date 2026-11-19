#!/usr/bin/env bash
# 仙宫云（或任何 Linux + NVIDIA GPU 云主机）一键准备写实化环境。
# 用法：bash setup_cloud.sh [14B|1.3B]      默认 14B（效果好）；1.3B 用于便宜快速的试跑
# 镜像建议：PyTorch 2.x + CUDA 12.x 的官方镜像（自带 python3 / pip / git）。模型走国内镜像，不需要代理。
set -euo pipefail
MODEL="${1:-14B}"
WORK="${V11_CLOUD_DIR:-$HOME/v11cloud}"; mkdir -p "$WORK"; cd "$WORK"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"      # 国内镜像
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

echo "[1/3] Python 环境"
python3 -m venv venv && source venv/bin/activate
python -m pip install -U pip
python -c "import torch" 2>/dev/null || pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install "diffusers>=0.34" "transformers>=4.51" accelerate ftfy imageio imageio-ffmpeg opencv-python-headless sentencepiece "huggingface_hub[cli]"

echo "[2/3] 下载模型 Wan2.1-VACE-${MODEL}（diffusers 格式）"
huggingface-cli download "Wan-AI/Wan2.1-VACE-${MODEL}-diffusers" --local-dir "models/Wan2.1-VACE-${MODEL}-diffusers"

echo "[3/3] 自检"
python - <<'EOF'
import torch; print('GPU:', torch.cuda.get_device_name(0), '%.0f GB' % (torch.cuda.get_device_properties(0).total_memory / 1e9))
import diffusers; print('diffusers', diffusers.__version__); from diffusers import WanVACEPipeline; print('WanVACEPipeline OK')
EOF
echo "环境就绪。把 cloud_pack.zip 传到 $WORK 并解压，然后：source venv/bin/activate && python realism.py --model ${MODEL}"
