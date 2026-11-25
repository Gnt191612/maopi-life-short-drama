#!/bin/bash
# 云端排队：把一批镜头排在云端当前任务后面，前一批一结束立刻开跑，不靠本地盯进度。
# 2026-11-25 教训：全片在云端 08:05 跑完，本地盯进度的 ssh 卡死没发现，补跑又要先在本地渲锚点、打包、上传，
# GPU 空等了 40 分钟，差点被平台「空闲 30 分钟自动关机」。队列放在云端，本地网络或进程出问题都不会让 GPU 闲着。
# 用法（云端）：nohup bash cloud_queue.sh <等待的完成标记> <本批完成标记> <本批包 zip> <镜头id ...> > /root/queue_<名>.log 2>&1 &
#   例：nohup bash cloud_queue.sh DONE_all DONE_b2 /root/v11_upload/next_b2.zip s05_01_0572 s06_01_0446 &
# 包用本地 cloud/slim_pack.py 打（只带 task.json、first.png、锚点帧、长相参考图，几十 MB，上传一两分钟）。
WAIT=$1; MINE=$2; ZIP=$3; shift 3; IDS="$*"
OUT=/root/v11_out; UP=/root/v11_upload
while [ ! -f $OUT/$WAIT ]; do sleep 15; done
mv -f $ZIP $UP/cloud_pack.zip && touch $UP/cloud_pack.zip      # session_realism.sh 发现包比解压目录新就重新解压
cd $OUT && for i in $IDS; do rm -rf kf/$i@*.png real/$i real/$i.mp4; done   # 主关键帧要不要重做由调用方决定（白模改过的要先删 kf/<id>.png）
rm -f $OUT/DONE_all
bash $UP/scripts/session_realism.sh all $IDS > $OUT/session_$MINE.log 2>&1
cp /root/v11_result_all.tgz /root/v11_result_$MINE.tgz
touch $OUT/$MINE
