# 可选：安装配音模型（只有要修改台词、重新配音时才需要；成片所用的 78 句配音已作为固定资产在 assets/audio/）
# 由 setup_windows.ps1 -WithTTS 调用，也可单独运行。需要：git、Python 3.10、NVIDIA GPU（约 10 GB 磁盘）
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

Write-Host '[TTS 2/2] CosyVoice2（台词配音，Apache-2.0）'
if (-not (Test-Path "$T\CosyVoice")) { git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git "$T\CosyVoice" }
python -m venv "$T\cosyenv"
& "$T\cosyenv\Scripts\python.exe" -m pip install -r "$T\CosyVoice\requirements.txt"
& "$T\cosyenv\Scripts\python.exe" -m pip install openai-whisper pypinyin
& "$T\cosyenv\Scripts\python.exe" -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir=r'$T\CosyVoice\pretrained_models\CosyVoice2-0.5B')"

Write-Host ''
Write-Host '配音模型安装完成。重新配音：'
Write-Host "  $T\sparkenv\Scripts\python.exe voice_tools\voice_design.py   （生成候选音色）"
Write-Host "  $T\cosyenv\Scripts\python.exe voice_tools\voice_pick.py      （自动挑选音色）"
Write-Host "  $T\cosyenv\Scripts\python.exe voice_tools\tts10.py           （生成全部台词到 assets\audio）"
