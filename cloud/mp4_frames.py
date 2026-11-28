# -*- coding: utf-8 -*-
"""本地：云端写实视频 real/<任务id>.mp4 → real/<任务id>/frame_####.png（帧号 = 任务 id 末尾的起始帧，与白模一致）。
逐帧 PNG 不从云端下载（太大，下载期间实例在计费）。用法：python cloud/mp4_frames.py <real 目录>
帧数按 task.json 的 n 补齐：视频比镜头短时用最后一帧重复补上、长了就裁掉（11-28 踩坑 96：11-28 之前生成的视频每个结尾少 1～2 帧，
缺的帧号合成时会露出白模或报错）。"""
import os, sys, glob, json, shutil
import cv2
PACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'cloud_pack')
for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.mp4'))):
    d = p[:-4]; tid = os.path.basename(d); os.makedirs(d, exist_ok=True); f0 = int(tid[-4:])
    tj = os.path.join(PACK, tid, 'task.json'); want = json.load(open(tj, encoding='utf-8'))['n'] if os.path.exists(tj) else None
    c = cv2.VideoCapture(p); i = 0
    while want is None or i < want:
        ok, im = c.read()
        if not ok: break
        cv2.imwrite(os.path.join(d, 'frame_%04d.png' % (f0 + i)), im); i += 1
    got = i
    while want is not None and 0 < i < want:   # 补齐：重复最后一帧
        shutil.copy(os.path.join(d, 'frame_%04d.png' % (f0 + got - 1)), os.path.join(d, 'frame_%04d.png' % (f0 + i))); i += 1
    print(tid, got, '帧' + ('（补齐到 %d）' % want if want and got < want else ''), flush=True)
