#!/bin/bash
# 装 MOSS-TTSD v1.0（写实化实例上运行，2026-11-27）：独立 venv（官方要求 Python 3.12 + Transformers 5.0.0，不动 ComfyUI 的环境），模型约 16 GB
set -e
HF=${HF_ENDPOINT:-https://hf-mirror.com}; R=/root/moss; mkdir -p $R /root/models
cd $R
[ -d MOSS-TTS/.git ] || git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS.git
PY=$(command -v python3.12 || command -v python3)
[ -d venv ] || $PY -m venv venv
. venv/bin/activate
pip install -q -U pip
pip install -q --extra-index-url https://download.pytorch.org/whl/cu128 -e "MOSS-TTS[torch-runtime]" || pip install -q torch torchaudio "transformers>=5.0.0" accelerate soundfile
pip install -q huggingface_hub
[ -f /root/models/MOSS-TTSD-v1.0/config.json ] || HF_ENDPOINT=$HF huggingface-cli download OpenMOSS-Team/MOSS-TTSD-v1.0 --local-dir /root/models/MOSS-TTSD-v1.0
python -c "import transformers, torch; print('transformers', transformers.__version__, 'torch', torch.__version__, torch.cuda.is_available())"
du -sh /root/models/MOSS-TTSD-v1.0
echo MOSS SETUP DONE
