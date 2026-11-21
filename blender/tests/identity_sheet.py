# -*- coding: utf-8 -*-
"""把 identity_compare.py 的渲染图和定妆照拼成一张对比图（普通 Python + OpenCV）。
python blender/tests/identity_sheet.py <cid> <渲染目录> <输出.png> [标题]"""
import os, sys
import numpy as np, cv2
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
cid, d, out = sys.argv[1:4]; title = sys.argv[4] if len(sys.argv) > 4 else ''
H = 560
def fit(im):
    s = H / im.shape[0]; return cv2.resize(im, (int(im.shape[1] * s), H), interpolation=cv2.INTER_AREA)
def label(im, t):
    im = im.copy(); cv2.rectangle(im, (0, 0), (im.shape[1], 34), (30, 30, 30), -1); cv2.putText(im, t, (10, 24), 0, 0.75, (255, 255, 255), 2); return im
photo = cv2.imread(os.path.join(ROOT, 'assets', 'identity', cid + '.png'))
ph = photo.shape; crop = photo[int(ph[0] * 0.05):int(ph[0] * 0.62), int(ph[1] * 0.08):int(ph[1] * 0.92)]
r = lambda tag, v: cv2.imread(os.path.join(d, '%s_%s_%s.png' % (cid, tag, v)))
row1 = [label(fit(crop), 'photo'), label(fit(r('skin', 'front')), 'skin front'), label(fit(r('clay', 'front')), 'clay front')]
row2 = [label(fit(r('skin', '34')), 'skin 3/4'), label(fit(r('clay', '34')), 'clay 3/4'), label(fit(r('clay', 'side')), 'clay side')]
def hcat(row):
    return np.hstack([np.pad(x, ((0, 0), (0, 6), (0, 0)), constant_values=255) for x in row])
a, b = hcat(row1), hcat(row2); w = max(a.shape[1], b.shape[1])
a = np.pad(a, ((0, 6), (0, w - a.shape[1]), (0, 0)), constant_values=255); b = np.pad(b, ((0, 0), (0, w - b.shape[1]), (0, 0)), constant_values=255)
sheet = np.vstack([a, b])
if title: sheet = np.vstack([label(np.full((40, w, 3), 255, np.uint8), title), sheet])
cv2.imwrite(out, sheet); print('SHEET OK', out, sheet.shape)
