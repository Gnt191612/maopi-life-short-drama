#!/bin/bash
# 口型同步（写实化实例上运行，2026-11-27）：LatentSync 1.6（字节开源，Apache-2.0），按镜头配音轨 voice.wav 重画嘴部，说话时张嘴、不说话时闭嘴
#   bash lipsync.sh setup                 # 装到 /root/latentsync（独立 venv，不动 ComfyUI 的环境），约 5～10 分钟，模型约 5 GB
#   bash lipsync.sh run <cloud_pack> id1 id2 ...   # 输入 /root/v11_out/fun/<id>.mp4 + <pack>/<id>/voice.wav → /root/v11_out/lips/<id>.mp4
# 顺序：video_fun.py（动作控制视频）→ 这里对口型 → 取回本地 face_unify 统一五官（inswapper 换脸保留嘴型动作）
set -e
export PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple UV_HTTP_TIMEOUT=300   # 云端访问 pypi.org / pytorch.org 只有 0.3～1.6 MB/s，腾讯镜像约 7 MB/s（11-27 实测）；PyPI 上的 Linux torch 自带 CUDA，不必走 pytorch.org
LS=/root/latentsync; HF=${HF_ENDPOINT:-https://hf-mirror.com}
if [ "$1" = setup ]; then
  [ -d $LS/.git ] || git clone --depth 1 https://github.com/bytedance/LatentSync.git $LS
  cd $LS
  PY=$(for P in /root/miniconda3/envs/comfyui/bin/python /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 /usr/bin/python3; do [ -x "$P" ] && $P -m pip --version >/dev/null 2>&1 && { echo $P; break; }; done; true)   # 新镜像没有 pip 命令：找一个带 pip 的 Python（11-27）
  [ -n "$PY" ] || { echo 'PY 为空：找不到带 pip 的 Python'; exit 1; }
  $PY -m pip install -q uv
  [ -x venv/bin/python ] && venv/bin/python -c 'import sysconfig,os,sys; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_paths()["include"],"Python.h")) else 1)' || { rm -rf venv; $PY -m uv venv --python-preference only-managed -p 3.10 venv; }   # 官方要求 3.10；必须用 uv 自带的独立版（系统 python3.10 没有 Python.h，insightface 编译失败，11-27）   # 官方要求 Python 3.10（setup_env.sh）
  . venv/bin/activate
  grep -v 'download.pytorch.org' requirements.txt > requirements.mirror.txt   # pytorch.org 只有 0.3 MB/s；PyPI 上的 torch 2.5.1 Linux 版自带 CUDA
  $PY -m uv pip install -p venv/bin/python -r requirements.mirror.txt huggingface_hub
  for f in whisper/tiny.pt latentsync_unet.pt; do mkdir -p checkpoints/$(dirname $f); [ -s checkpoints/$f ] && continue   # ModelScope 快（hf-mirror 约 0.4 MB/s，11-27 实测）
    wget -q -c -O checkpoints/$f "https://modelscope.cn/models/ByteDance/LatentSync-1.6/resolve/master/$f" || wget -q -c -O checkpoints/$f "$HF/ByteDance/LatentSync-1.6/resolve/main/$f"; done
  # VAE：推理脚本默认从 HuggingFace 拉 stabilityai/sd-vae-ft-mse，云端 HF 和 hf-mirror 都下到一半断（11-27 两次 IncompleteRead）→ ModelScope 续传下载到本地，推理时改读本地目录
  mkdir -p checkpoints/sd-vae-ft-mse
  for f in config.json diffusion_pytorch_model.safetensors; do [ -s checkpoints/sd-vae-ft-mse/$f ] && continue
    wget -q -c -O checkpoints/sd-vae-ft-mse/$f "https://modelscope.cn/models/AI-ModelScope/sd-vae-ft-mse/resolve/master/$f"; done
  grep -rl '"stabilityai/sd-vae-ft-mse"' scripts latentsync 2>/dev/null | xargs -r sed -i 's#"stabilityai/sd-vae-ft-mse"#"checkpoints/sd-vae-ft-mse"#g'
  ls -la checkpoints checkpoints/whisper checkpoints/sd-vae-ft-mse
  echo LIPSYNC SETUP DONE; exit 0
fi
if [ "$1" = run ]; then
  PACK=$2; shift 2; mkdir -p /root/v11_out/lips
  # ComfyUI 跑完视频后一直占着 30 多 GB 显存不放，口型同步/MOSS 会显存不足（11-27 MOSS 报 CUDA out of memory）：先让它卸载模型
  curl -s -X POST http://127.0.0.1:8188/free -H 'Content-Type: application/json' -d '{"unload_models":true,"free_memory":true}' >/dev/null; sleep 5
  cd $LS; . venv/bin/activate
  CFG=configs/unet/stage2_512.yaml; [ -f $CFG ] || CFG=configs/unet/stage2.yaml
  for id in "$@"; do
    v=/root/v11_out/fun/$id.mp4; a=$PACK/$id/voice.wav; o=/root/v11_out/lips/$id.mp4
    [ -f $v ] && [ -f $a ] || { echo "跳过 $id（缺视频或配音轨）"; continue; }
    t0=$(date +%s)
    python -m scripts.inference --unet_config_path $CFG --inference_ckpt_path checkpoints/latentsync_unet.pt \
      --inference_steps 20 --guidance_scale 1.5 --enable_deepcache --video_path $v --audio_path $a --video_out_path $o.tmp.mp4 \
      || { echo "口型失败 $id"; continue; }
    # LatentSync 输出带配音的 25fps 视频：换回 24fps、去掉声音、帧数和原视频一致（帧号要和白模时间轴对齐）
    n=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 $v)
    ffmpeg -v error -y -i $o.tmp.mp4 -vf fps=24 -frames:v $n -an -c:v libx264 -crf 14 -pix_fmt yuv420p $o && rm -f $o.tmp.mp4
    echo "口型完成 $id $(( $(date +%s) - t0 )) 秒"
  done
  echo LIPSYNC DONE; exit 0
fi
echo "用法：bash lipsync.sh setup | run <pack> id ..."
