#!/usr/bin/env bash
# 可选：安装配音模型（只有要修改台词、重新配音时才需要；成片配音已作为固定资产在 assets/audio/）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; T="$ROOT/.tools"; mkdir -p "$T"
ms() {  # ms <repo> <目标目录> <文件...>：从 ModelScope 下载模型文件
  local repo="$1" dst="$2"; shift 2
  for f in "$@"; do
    [ -f "$dst/$f" ] && continue; mkdir -p "$(dirname "$dst/$f")"
    curl -L -f --retry 10 -C - -o "$dst/$f" "https://www.modelscope.cn/models/$repo/resolve/master/$f"
  done
}
echo "[TTS 1/2] Spark-TTS（代码 Apache-2.0，模型 CC BY-NC-SA 4.0 仅限非商业）"
[ -d "$T/Spark-TTS" ] || git clone --depth 1 https://github.com/SparkAudio/Spark-TTS.git "$T/Spark-TTS"
ms SparkAudio/Spark-TTS-0.5B "$T/Spark-TTS/pretrained_models/Spark-TTS-0.5B" config.yaml BiCodec/config.yaml BiCodec/model.safetensors \
  LLM/added_tokens.json LLM/config.json LLM/merges.txt LLM/model.safetensors LLM/special_tokens_map.json LLM/tokenizer.json \
  LLM/tokenizer_config.json LLM/vocab.json wav2vec2-large-xlsr-53/config.json wav2vec2-large-xlsr-53/preprocessor_config.json \
  wav2vec2-large-xlsr-53/pytorch_model.bin
python3 -m venv "$T/sparkenv"
"$T/sparkenv/bin/pip" install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
"$T/sparkenv/bin/pip" install transformers==4.46.2 einx==0.3.0 einops omegaconf soundfile soxr safetensors
echo "[TTS 2/2] IndexTTS2（台词配音，B 站开源）"
[ -d "$T/index-tts" ] || git clone --depth 1 https://github.com/index-tts/index-tts.git "$T/index-tts"
( cd "$T/index-tts" && python3 -m pip install -q uv && python3 -m uv sync --python 3.11 \
  && python3 -m uv pip install --python .venv/bin/python pypinyin \
  && .venv/bin/hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints )
echo "重新配音：V11_SPARK_DIR=$T/Spark-TTS $T/sparkenv/bin/python voice_tools/voice_design.py"
echo "          $T/index-tts/.venv/bin/python voice_tools/voice_pick2.py"
echo "          $T/index-tts/.venv/bin/python voice_tools/tts11.py"
