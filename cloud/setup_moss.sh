#!/bin/bash
# 装 MOSS-TTSD v1.0（写实化实例上运行，2026-11-27）：独立 venv，不动 ComfyUI 的环境；模型约 16 GB
# 官方要求：Python 3.12、Transformers 5.0.0、pyproject 固定 torch==2.9.1+cu128（需要显卡驱动 >= 570，即 CUDA 12.8）
# 预判：镜像驱动可能更老 → 按驱动支持的 CUDA 版本选 torch 下载源；系统没有 Python 3.12 → 用 uv 自动下载
set -e
HF=${HF_ENDPOINT:-https://hf-mirror.com}; R=/root/moss; mkdir -p $R /root/models; cd $R
[ -d MOSS-TTS/.git ] || git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS.git
CU=$(nvidia-smi | grep -o 'CUDA Version: [0-9.]*' | grep -o '[0-9.]*$'); echo "驱动支持 CUDA $CU"
IDX=cu128; python3 -c "import sys; sys.exit(0 if tuple(map(int,'$CU'.split('.')))>=(12,8) else 1)" || IDX=cu124
PY=$(for P in /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 /usr/bin/python3; do [ -x "$P" ] && $P -m pip --version >/dev/null 2>&1 && { echo $P; break; }; done)   # 新镜像没有 pip 命令：找一个带 pip 的 Python（11-27）
$PY -m pip install -q uv
[ -d venv ] || $PY -m uv venv -p 3.12 venv   # 官方要求 Python 3.12
. venv/bin/activate
PIP="$PY -m uv pip"
if [ $IDX = cu128 ]; then
  $PIP install --extra-index-url https://download.pytorch.org/whl/cu128 -e "MOSS-TTS[torch-runtime]"
else
  echo "驱动太旧，改装 cu124 的 torch（不用 pyproject 里固定的 2.9.1+cu128）"
  $PIP install --index-url https://download.pytorch.org/whl/cu124 torch torchaudio
  $PIP install "transformers==5.0.0" accelerate soundfile librosa einops safetensors
  $PIP install --no-deps -e MOSS-TTS
fi
$PIP install huggingface_hub
[ -f /root/models/MOSS-TTSD-v1.0/config.json ] || HF_ENDPOINT=$HF python -c "from huggingface_hub import snapshot_download as s; s('OpenMOSS-Team/MOSS-TTSD-v1.0', local_dir='/root/models/MOSS-TTSD-v1.0')"
python -c "import transformers, torch; print('transformers', transformers.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"
du -sh /root/models/MOSS-TTSD-v1.0
echo MOSS SETUP DONE
