# -*- coding: utf-8 -*-
"""全片重拍后的审片拼图：从 build/renders/<片段>/beauty_*.png 按 _cuts.json 每个镜头取开头、中间两帧 → build/review/full_<片段>.jpg
python blender/tests/sheet_from_renders.py [片段 ...]（不给就做全部已拍完的）"""
import os, sys, json, glob
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
segs = sys.argv[1:] or sorted(os.path.basename(p)[:-10] for p in glob.glob(os.path.join(config.SHOTS, '*_cuts.json')))
out_d = os.path.join(config.ROOT, 'build', 'review'); os.makedirs(out_d, exist_ok=True)
for s in segs:
    cp = os.path.join(config.SHOTS, s + '_cuts.json'); rd = os.path.join(config.RENDERS, s)
    n = len(glob.glob(os.path.join(rd, 'beauty_*.png')))
    if not os.path.exists(cp) or n == 0: continue
    cuts = json.load(open(cp, encoding='utf-8')); bounds = [c[0] for c in cuts] + [n + 1]
    tiles = []
    for k, c in enumerate(cuts):
        f0, f1 = c[0], min(bounds[k + 1] - 1, n)
        row = []
        for f in (f0, (f0 + f1) // 2):
            p = os.path.join(rd, 'beauty_%04d.png' % f); im = cv2.imread(p) if os.path.exists(p) else None
            row.append(cv2.resize(im, (400, 225)) if im is not None else np.zeros((225, 400, 3), np.uint8))
        r = np.hstack(row); cv2.putText(r, '%04d %s' % (f0, c[2] if len(c) > 2 else ''), (5, 20), 0, 0.55, (0, 255, 255), 2); tiles.append(r)
    if len(tiles) % 2: tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(os.path.join(out_d, 'full_%s.jpg' % s), np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print('SHEET', s, len(cuts))
