# 可选：安装配音模型（只有要修改台词、重新配音时才需要；成片所用的全部配音已作为固定资产在 assets/audio/）
# 由 setup_windows.ps1 -WithTTS 调用，也可单独运行。需要：git、Python 3.10、NVIDIA GPU（约 15 GB 磁盘）
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot; $T = Join-Path $Root '.tools'
$Proxy = if ($env:HTTPS_PROXY) { @('-x', $env:HTTPS_PROXY) } else { @() }
function Get-ModelScope($repo, $files, $dst) {   # 从 ModelScope（国内可直连）下载模型文件
    foreach ($f in $files) {
        $o = Join-Path $dst ($f -replace '/', '\'); if (Test-Path $o) { continue }
        New-Item -ItemType Directory -Force (Split-Path $o) | Out-Null
        & curl.exe -L -f --retry 10 -C - -o $o "https://www.modelscope.cn/models/$repo/resolve/master/$f"
        if ($LASTEXITCODE -ne 0) { throw "下载失败 $repo/$f" }
    }
}

Write-Host '[TTS 1/2] Spark-TTS（音色设计；代码 Apache-2.0，模型 CC BY-NC-SA 4.0 仅限非商业）'
if (-not (Test-Path "$T\Spark-TTS")) { git clone --depth 1 https://github.com/SparkAudio/Spark-TTS.git "$T\Spark-TTS" }
Get-ModelScope 'SparkAudio/Spark-TTS-0.5B' @('config.yaml', 'BiCodec/config.yaml', 'BiCodec/model.safetensors',
    'LLM/added_tokens.json', 'LLM/config.json', 'LLM/merges.txt', 'LLM/model.safetensors', 'LLM/special_tokens_map.json',
    'LLM/tokenizer.json', 'LLM/tokenizer_config.json', 'LLM/vocab.json', 'wav2vec2-large-xlsr-53/config.json',
    'wav2vec2-large-xlsr-53/preprocessor_config.json', 'wav2vec2-large-xlsr-53/pytorch_model.bin') "$T\Spark-TTS\pretrained_models\Spark-TTS-0.5B"
python -m venv "$T\sparkenv"
& "$T\sparkenv\Scripts\python.exe" -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
& "$T\sparkenv\Scripts\python.exe" -m pip install transformers==4.46.2 einx==0.3.0 einops omegaconf soundfile soxr safetensors

Write-Host '[TTS 2/2] IndexTTS2（台词配音，B 站开源；代码与模型许可见 THIRD_PARTY_LICENSES.md）'
if (-not (Test-Path "$T\index-tts")) { git clone --depth 1 https://github.com/index-tts/index-tts.git "$T\index-tts" }
Push-Location "$T\index-tts"
python -m pip install -q uv
python -m uv sync --python 3.11
python -m uv pip install --python .venv\Scripts\python.exe pypinyin
.venv\Scripts\hf.exe download IndexTeam/IndexTTS-2 --local-dir=checkpoints   # 约 5.9 GB；首次配音时还会自动下载约 3 GB 辅助模型
Pop-Location

Write-Host ''
Write-Host '配音模型安装完成。重新配音：'
Write-Host "  `$env:V11_SPARK_DIR='$T\Spark-TTS'; $T\sparkenv\Scripts\python.exe voice_tools\voice_design.py   （生成候选音色；第二轮参数见 voice_tools\README）"
Write-Host "  $T\index-tts\.venv\Scripts\python.exe voice_tools\voice_pick2.py   （自动挑选音色 -> voices_v2\pick.json）"
Write-Host "  $T\index-tts\.venv\Scripts\python.exe voice_tools\tts11.py         （按语气说明生成全部台词到 assets\audio）"
