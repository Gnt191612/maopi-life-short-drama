# -*- coding: utf-8 -*-
"""本地：云端写实视频 real/<任务id>.mp4 → real/<任务id>/frame_####.png（帧号 = 任务 id 末尾的起始帧，与白模一致）。
逐帧 PNG 不从云端下载（太大，下载期间实例在计费）。用法：python cloud/mp4_frames.py <real 目录>"""
import os, sys, glob
import cv2
for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.mp4'))):
    d = p[:-4]; os.makedirs(d, exist_ok=True); f0 = int(os.path.basename(d)[-4:])
    c = cv2.VideoCapture(p); i = 0
    while True:
        ok, im = c.read()
        if not ok: break
        cv2.imwrite(os.path.join(d, 'frame_%04d.png' % (f0 + i)), im); i += 1
    print(os.path.basename(d), i, '帧', flush=True)
