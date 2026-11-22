#!/usr/bin/env bash
# 写实化实例上的总控（由本地 cloud/session.ps1 上传并后台启动；也可以手动跑）：
#   bash session_realism.sh <阶段> [任务id前缀 ...]
#   阶段：probe（摸清工作流和模型，几秒）| keys（每个镜头写实关键帧）| test（第一个镜头：关键帧 + 视频第一段）
#        | video（全部镜头视频，需要先填好 video_map.json）| all（keys + video）
# 每个阶段都有超时（防止卡住空烧钱）；结果打包到 /root/v11_result_<阶段>.tgz，完成后写 /root/v11_out/DONE_<阶段>
set -u
STAGE=${1:-probe}; shift || true; PRE="$*"
UP=/root/v11_upload; S=$UP/scripts; PACK=/root/v11cloud/cloud_pack; OUT=/root/v11_out
mkdir -p $OUT; rm -f $OUT/DONE_$STAGE
echo "[$(date +%T)] 阶段 $STAGE 开始"
sed -i 's/\r$//' $S/*.sh 2>/dev/null
# 素材包（镜头任务 + 标准长相照片）
if [ -f $UP/cloud_pack.zip ] && [ $UP/cloud_pack.zip -nt $PACK/manifest.json ] 2>/dev/null || [ ! -f $PACK/manifest.json ]; then
  [ -f $UP/cloud_pack.zip ] && { rm -rf /root/v11cloud; mkdir -p /root/v11cloud; python3 -c "import zipfile; zipfile.ZipFile('$UP/cloud_pack.zip').extractall('/root/v11cloud')"; echo "素材包已解压：$(ls $PACK | wc -l) 项"; }
fi
command -v ffmpeg >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null; }
# ComfyUI：镜像开机自启；没起来就自己启动（最多等 3 分钟）
up() { [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8188/system_stats)" = "200" ]; }
if ! up; then
  for i in $(seq 1 18); do up && break; sleep 10; done
  if ! up; then
    PY=$(ls -d /root/ComfyUI/venv/bin/python /root/ComfyUI/.venv/bin/python 2>/dev/null | head -1); PY=${PY:-python3}
    echo "ComfyUI 未运行，自行启动（$PY）"; (cd /root/ComfyUI && nohup $PY main.py --listen 127.0.0.1 --port 8188 > $OUT/comfy.log 2>&1 &)
    for i in $(seq 1 30); do up && break; sleep 10; done
  fi
fi
up && echo "ComfyUI 正常" || { echo "ComfyUI 启动失败，见 $OUT/comfy.log"; touch $OUT/DONE_$STAGE; exit 1; }
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
cd $S
case $STAGE in
  probe) timeout 300 python3 probe_comfy.py ;;
  keys)  timeout ${V11_KEYS_MAX:-3600} python3 keyframes.py $PACK $PRE ;;
  test)  FIRST=$(python3 -c "import json; print(json.load(open('$PACK/manifest.json'))['tasks'][0])")
         timeout 900 python3 keyframes.py $PACK ${PRE:-$FIRST}
         timeout 1800 python3 video_run.py $PACK --test --only ${PRE:-$FIRST} ;;
  video) timeout ${V11_VIDEO_MAX:-7200} python3 video_run.py $PACK ${PRE:+--only ${PRE// /,}} ;;
  all)   timeout ${V11_KEYS_MAX:-3600} python3 keyframes.py $PACK $PRE
         timeout ${V11_VIDEO_MAX:-7200} python3 video_run.py $PACK ${PRE:+--only ${PRE// /,}} ;;
  *) echo "未知阶段 $STAGE" ;;
esac
RC=$?; [ $RC = 124 ] && echo "!! 超时被中止（防止空烧钱）"
cd $OUT && tar -czf /root/v11_result_$STAGE.tgz --exclude=vtmp --exclude='real/*/frame_*' probe.* kf real video_progress.log comfy.log 2>/dev/null   # 逐帧 PNG 不传（本地从 mp4 还原，省下载时间）
echo "[$(date +%T)] 阶段 $STAGE 结束 rc=$RC，结果 /root/v11_result_$STAGE.tgz ($(du -h /root/v11_result_$STAGE.tgz | cut -f1))"
touch $OUT/DONE_$STAGE
