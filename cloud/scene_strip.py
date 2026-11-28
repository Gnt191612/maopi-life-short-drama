# -*- coding: utf-8 -*-
"""整场戏一览（11-27 用户：「每段渲染出来之后连在一起看能不能看出来是同一场景同一时间需要仔细审查」）：
每个片段一张图，按镜头顺序排出全部写实首帧（目录里是 png）或视频中间帧（mp4），标出每个镜头相对本段中位数的亮度、冷暖偏差（偏差大标红）。
人工看：同一个房间吗（墙色、床/桌样式、窗和门的位置）、同一时间吗（天色、光线方向、冷暖）、人和衣着一致吗。相邻两镜的衔接另用 continuity_review.py。
用法：python cloud/scene_strip.py <首帧或视频目录> <输出目录>"""
import os, sys, json, glob
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
W, H, COLS = 384, 216, 5
def frame_of(p):
    if p.endswith('.png'): return cv2.imread(p)
    cap = cv2.VideoCapture(p); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2); ok, f = cap.read(); return f if ok else None
def stat(f):
    lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB).astype(np.float32); return lab[..., 0].mean() * 100 / 255, lab[..., 2].mean() - 128   # 亮度 0~100、冷暖（正=暖黄）
segs = {}
for p in sorted(glob.glob(os.path.join(src, 's*_*_*.png')) + glob.glob(os.path.join(src, 's*_*_*.mp4'))):
    tid = os.path.basename(p).rsplit('.', 1)[0]
    if '@' in tid or tid.endswith('_lips') or not os.path.exists(os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'task.json')): continue
    segs.setdefault(tid.rsplit('_', 1)[0], []).append((tid, p))
report = []
for seg, items in sorted(segs.items()):
    tiles = [(tid, f) for tid, p in items for f in [frame_of(p)] if f is not None]
    if not tiles: continue
    st = [stat(f) for _, f in tiles]; mL = float(np.median([s[0] for s in st])); mB = float(np.median([s[1] for s in st]))
    setn = json.load(open(os.path.join(ROOT, 'dist', 'cloud_pack', tiles[0][0], 'task.json'), encoding='utf-8')).get('set', '')
    rows = []
    for k in range(0, len(tiles), COLS):
        row = np.zeros((H + 26, W * COLS, 3), np.uint8)
        for j, (tid, f) in enumerate(tiles[k:k + COLS]): row[26:, j * W:(j + 1) * W] = cv2.resize(f, (W, H))
        pim = Image.fromarray(cv2.cvtColor(row, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pim)
        for j, (tid, f) in enumerate(tiles[k:k + COLS]):
            L, B = st[k + j]; bad = abs(L - mL) > 12 or abs(B - mB) > 5
            if bad: report.append('%s %s 亮度%+.0f 冷暖%+.0f' % (seg, tid, L - mL, B - mB))
            d.text((j * W + 4, 3), '%s  亮%+.0f 暖%+.0f' % (tid[-4:], L - mL, B - mB), font=FONT, fill=(255, 80, 80) if bad else (255, 230, 0))
        rows.append(cv2.cvtColor(np.asarray(pim), cv2.COLOR_RGB2BGR))
    head = Image.new('RGB', (W * COLS, 30)); ImageDraw.Draw(head).text((6, 4), '%s  %s  %d 个镜头（按顺序；红字 = 和本段中位数相比亮度差 >12 或冷暖差 >5）' % (seg, setn, len(tiles)), font=FONT, fill=(255, 255, 255))
    cv2.imwrite(os.path.join(out, 'scene_%s.jpg' % seg), np.vstack([cv2.cvtColor(np.asarray(head), cv2.COLOR_RGB2BGR)] + rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
print('整场戏一览 %d 张 → %s' % (len(segs), out)); print('\n'.join(report) if report else '没有明显的亮度/冷暖偏差')
