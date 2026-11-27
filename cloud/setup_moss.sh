#!/bin/bash
# 装 MOSS-TTSD v1.0（写实化实例上运行，2026-11-27）：独立 venv，不动 ComfyUI 的环境；模型约 16 GB
# 官方要求：Python 3.12、Transformers 5.0.0、pyproject 固定 torch==2.9.1+cu128（需要显卡驱动 >= 570，即 CUDA 12.8）
# 预判：镜像驱动可能更老 → 按驱动支持的 CUDA 版本选 torch 下载源；系统没有 Python 3.12 → 用 uv 自动下载
set -e
export PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple UV_HTTP_TIMEOUT=300   # 云端访问 pypi.org / pytorch.org 只有 0.3～1.6 MB/s，腾讯镜像约 7 MB/s（11-27 实测）；PyPI 上的 Linux torch 自带 CUDA，不必走 pytorch.org
HF=${HF_ENDPOINT:-https://hf-mirror.com}; R=/root/moss; mkdir -p $R /root/models; cd $R
[ -d MOSS-TTS/.git ] || git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS.git
CU=$(nvidia-smi | grep -o 'CUDA Version: [0-9.]*' | grep -o '[0-9.]*$' || true); [ -n "$CU" ] || CU=12.8; echo "驱动支持 CUDA $CU"   # 有的镜像 nvidia-smi 不显示 CUDA 版本，grep 失败 + set -e 会让脚本无声退出（11-27 踩坑）
IDX=cu128; python3 -c "import sys; sys.exit(0 if tuple(map(int,'$CU'.split('.')))>=(12,8) else 1)" || IDX=cu124
PY=$(for P in /root/miniconda3/envs/comfyui/bin/python /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 /usr/bin/python3; do [ -x "$P" ] && $P -m pip --version >/dev/null 2>&1 && { echo $P; break; }; done; true)   # 新镜像没有 pip 命令：找一个带 pip 的 Python（11-27）
[ -n "$PY" ] || { echo 'PY 为空：找不到带 pip 的 Python'; exit 1; }
$PY -m pip install -q uv
[ -x venv/bin/python ] || $PY -m uv venv --python-preference only-managed -p 3.12 venv   # 官方要求 Python 3.12；用 uv 自带的完整 Python（系统 Python 缺头文件，见踩坑记录）
. venv/bin/activate
PIP_INSTALL="$PY -m uv pip install --python $R/venv/bin/python"   # 必须显式 --python：用 ComfyUI 的 Python 跑 uv 时，uv 会装进 ComfyUI 环境（11-27 事故：torch/transformers/numpy 被换，见 restore_comfy_env.sh）
# pyproject 固定 torch==2.9.1+cu128（pytorch.org 才有这个标签）：改成 PyPI 上同版本的 torch 2.9.1（Linux 默认就是 cu128 版）
printf "torch==2.9.1\ntorchaudio==2.9.1\n" > /root/moss/overrides.txt
$PIP_INSTALL --override /root/moss/overrides.txt -e "MOSS-TTS[torch-runtime]" || $PIP_INSTALL --override /root/moss/overrides.txt -e MOSS-TTS
$PIP_INSTALL huggingface_hub
$PIP_INSTALL modelscope
[ -f /root/models/MOSS-TTSD-v1.0/config.json ] || python -c "from modelscope import snapshot_download as s; s('openmoss/MOSS-TTSD-v1.0', local_dir='/root/models/MOSS-TTSD-v1.0')" \
  || HF_ENDPOINT=$HF python -c "from huggingface_hub import snapshot_download as s; s('OpenMOSS-Team/MOSS-TTSD-v1.0', local_dir='/root/models/MOSS-TTSD-v1.0')"   # ModelScope 优先（官方 README 列了 openmoss/MOSS-TTSD-v1.0）
python -c "import transformers, torch; print('transformers', transformers.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"
du -sh /root/models/MOSS-TTSD-v1.0
echo MOSS SETUP DONE
