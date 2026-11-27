#!/bin/bash
# 口型同步（写实化实例上运行，2026-11-27）：LatentSync 1.6（字节开源，Apache-2.0），按镜头配音轨 voice.wav 重画嘴部，说话时张嘴、不说话时闭嘴
#   bash lipsync.sh setup                 # 装到 /root/latentsync（独立 venv，不动 ComfyUI 的环境），约 5～10 分钟，模型约 5 GB
#   bash lipsync.sh run <cloud_pack> id1 id2 ...   # 输入 /root/v11_out/fun/<id>.mp4 + <pack>/<id>/voice.wav → /root/v11_out/lips/<id>.mp4
# 顺序：video_fun.py（动作控制视频）→ 这里对口型 → 取回本地 face_unify 统一五官（inswapper 换脸保留嘴型动作）
set -e
LS=/root/latentsync; HF=${HF_ENDPOINT:-https://hf-mirror.com}
if [ "$1" = setup ]; then
  [ -d $LS/.git ] || git clone --depth 1 https://github.com/bytedance/LatentSync.git $LS
  cd $LS
  PY=$(for P in /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python /root/miniconda3/bin/python /opt/conda/bin/python /usr/local/bin/python3 /usr/bin/python3; do [ -x "$P" ] && $P -m pip --version >/dev/null 2>&1 && { echo $P; break; }; done)   # 新镜像没有 pip 命令：找一个带 pip 的 Python（11-27）
  $PY -m pip install -q uv
  [ -d venv ] || $PY -m uv venv -p 3.10 venv   # 官方要求 Python 3.10；uv 会自己下载这个版本   # 官方要求 Python 3.10（setup_env.sh）
  . venv/bin/activate
  $PY -m uv pip install -p venv/bin/python -r requirements.txt huggingface_hub
  HF_ENDPOINT=$HF venv/bin/python -c "from huggingface_hub import hf_hub_download as d; [d('ByteDance/LatentSync-1.6', f, local_dir='checkpoints') for f in ('whisper/tiny.pt', 'latentsync_unet.pt')]"
  ls -la checkpoints checkpoints/whisper
  echo LIPSYNC SETUP DONE; exit 0
fi
if [ "$1" = run ]; then
  PACK=$2; shift 2; mkdir -p /root/v11_out/lips
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
