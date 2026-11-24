# -*- coding: utf-8 -*-
"""动作审查：每个镜头均匀取 5 帧排成一行（一个片段一张图 build/review/motion_<seg>.jpg），看动作是否连贯、有没有长时间定住。
$env:V11_PREVIEW='1'; python blender/tests/motion_strip.py <seg> [...]"""
import os, sys, json, glob
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
for seg in sys.argv[1:]:
    rd = os.path.join(config.RENDERS, seg); n = len(glob.glob(os.path.join(rd, 'beauty_*.png')))
    cuts = json.load(open(os.path.join(config.SHOTS, seg + '_cuts.json'), encoding='utf-8'))
    bd = [c[0] for c in cuts] + [n + 1]; rows = []
    for k, c in enumerate(cuts):
        f0, f1 = c[0], min(bd[k + 1] - 1, n)
        if f1 - f0 < 8 or c[1].endswith('_phone'): continue
        fs = [round(f0 + (f1 - f0) * i / 4) for i in range(5)]; ims = []
        for f in fs:
            im = cv2.imread(os.path.join(rd, 'beauty_%04d.png' % f))
            im = cv2.resize(im, (288, 162)) if im is not None else np.zeros((162, 288, 3), np.uint8)
            cv2.putText(im, '%d' % f, (4, 14), 0, 0.42, (0, 255, 255), 1); ims.append(im)
        rows.append(np.hstack(ims))
    if rows: cv2.imwrite(os.path.join(config.ROOT, 'build', 'review', 'motion_%s.jpg' % seg), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80]); print('MOTION', seg, len(rows))
