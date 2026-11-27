#!/bin/bash
# 关键帧编辑后重跑（云端）：等上一批完成 → 用 edit_photo.py 逐张编辑这些镜头的关键帧和锚点图 → 覆盖 kf → 重新生成视频。
# 2026-11-25：林母发型、多人同框里陈瑶被画成第二个林晓，重跑多轮都改不掉，最后用这个办法改。
# 用法：nohup bash cloud_edit_queue.sh <等待的完成标记> <本批完成标记> <本批包 zip> "<编辑指令>" <镜头id ...> &
WAIT=$1; MINE=$2; ZIP=$3; INST=$4; shift 4; IDS="$*"
OUT=/root/v11_out; S=/root/v11_upload/scripts; INP=/root/ComfyUI/input
while [ ! -f $OUT/$WAIT ]; do sleep 15; done
cd $S
for id in $IDS; do
  for f in $OUT/kf/$id.png $OUT/kf/$id@*.png; do
    [ -f "$f" ] || continue
    b=$(basename $f .png); cp $f $INP/edit_$b.png
    r=$(python3 edit_photo.py edit_$b.png edited_$b "$INST" 11 | grep SAVED | awk '{print $2}')
    [ -n "$r" ] && cp $f $OUT/kf/orig_$b.png && cp $r $f && echo "EDITED $f"
  done
  rm -rf $OUT/real/$id $OUT/real/$id.mp4
done
mv -f $ZIP /root/v11_upload/cloud_pack.zip && touch /root/v11_upload/cloud_pack.zip
rm -f $OUT/DONE_all
export V11_KEYS_MAX=${V11_KEYS_MAX:-20000} V11_VIDEO_MAX=${V11_VIDEO_MAX:-60000}
bash $S/session_realism.sh all $IDS > $OUT/session_$MINE.log 2>&1
touch $OUT/$MINE