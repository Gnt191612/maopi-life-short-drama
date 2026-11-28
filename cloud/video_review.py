# -*- coding: utf-8 -*-
"""全片视频审查拼图（11-27）：每个还没审过的镜头一行 =「白模首帧 | 视频 5 帧」，上面标镜头、场景、方法、台词数，
人工逐行看：场景/背景有没有中途换、人有没有多/少/变样、衣着、动作是否跟白模、光线时间。
用法：python cloud/video_review.py <取回目录> <已审清单.txt> → <取回目录>/_vreview_##.jpg（每张 6 个镜头）"""
import os, sys, json, glob, subprocess
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import config, looks
src, okf = sys.argv[1], sys.argv[2]
OK = set(open(okf, encoding='utf-8').read().split()) if os.path.exists(okf) else set()
FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
W, H = 320, 180
rows = []
for v in sorted(glob.glob(os.path.join(src, 's*_*_*.mp4'))):
    tid = os.path.basename(v)[:-4]
    if tid in OK or tid.endswith('_lips'): continue
    t = json.load(open(os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'task.json'), encoding='utf-8'))
    cap = cv2.VideoCapture(v); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fr = []
    for i in np.linspace(0, max(n - 1, 0), 5).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, f = cap.read()
        fr.append(cv2.resize(f, (W, H)) if ok else np.zeros((H, W, 3), np.uint8))
    g = cv2.imread(os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'first.png')); g = cv2.resize(g, (W, H)) if g is not None else np.zeros((H, W, 3), np.uint8)
    row = np.hstack([g] + fr)
    lines = os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'lines.json'); nl = len(json.load(open(lines, encoding='utf-8'))) if os.path.exists(lines) else 0
    pika = t.get('move', 'static') in ('hand', 'static', 'push') or t.get('cam_motion', 99) < 15   # 和 video_h3.pika_for 一致
    txt = '%s  %s  %s  %s  主角:%s  台词%d句  | 左=白模首帧' % (tid, t.get('set', ''), t.get('move'), 'Pika' if pika else '20步', '、'.join(looks.NAME.get(c, c) for c in t.get('characters', [])) or '无', nl)
    im = Image.fromarray(cv2.cvtColor(row, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(im); d.rectangle([0, 0, row.shape[1], 24], fill=(0, 0, 0)); d.text((6, 2), txt, font=FONT, fill=(255, 230, 0))
    rows.append(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
for k in range(0, len(rows), 6):
    cv2.imwrite(os.path.join(src, '_vreview_%02d.jpg' % (k // 6 + 1)), np.vstack(rows[k:k + 6]), [cv2.IMWRITE_JPEG_QUALITY, 85])
print('视频审查拼图 %d 张（%d 个镜头）' % ((len(rows) + 5) // 6, len(rows)))
