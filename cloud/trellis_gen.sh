#!/bin/bash
# TRELLIS.2 实例上：停掉自带网页程序（腾出显存），按镜像的环境变量运行 trellis_gen.py。用法：bash trellis_gen.sh <输入图> <输出.glb> [种子] [分辨率]
pkill -f "app\.py" 2>/dev/null; sleep 3
source /root/miniconda3/etc/profile.d/conda.sh; conda activate py310
export HF_ENDPOINT=https://hf-mirror.com HUGGINGFACE_HUB_CACHE=/root/TRELLIS.2/models HF_HOME=/root/TRELLIS.2/models OPENCV_IO_ENABLE_OPENEXR=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ATTN_BACKEND=flash_attn_3 FLEX_GEMM_AUTOTUNE_CACHE_PATH=/root/TRELLIS.2/autotune_cache.json
python /root/cloud/trellis_gen.py "$@" 2>&1 | grep -v -E "it/s|s/it" | tail -15
