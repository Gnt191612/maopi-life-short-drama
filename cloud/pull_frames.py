# -*- coding: utf-8 -*-
"""把指定的几个 real/<任务id>.mp4 拆成 real/<任务id>/frame_####.png（帧号 = 任务 id 末尾的起始帧）。pull_done.ps1 逐步取回时用。"""
import os, sys, cv2
for p in sys.argv[1:]:
    d = p[:-4]; os.makedirs(d, exist_ok=True); f0 = int(os.path.basename(d)[-4:])
    c = cv2.VideoCapture(p); i = 0
    while True:
        ok, im = c.read()
        if not ok: break
        cv2.imwrite(os.path.join(d, 'frame_%04d.png' % (f0 + i)), im); i += 1
    print(os.path.basename(d), i, '帧', flush=True)