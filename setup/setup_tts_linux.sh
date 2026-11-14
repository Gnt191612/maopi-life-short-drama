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
echo "[TTS 2/2] CosyVoice2（Apache-2.0）"
[ -d "$T/CosyVoice" ] || git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git "$T/CosyVoice"
python3 -m venv "$T/cosyenv"
"$T/cosyenv/bin/pip" install -r "$T/CosyVoice/requirements.txt" openai-whisper pypinyin
"$T/cosyenv/bin/python" -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='$T/CosyVoice/pretrained_models/CosyVoice2-0.5B')"
echo "配音模型安装完成。"
