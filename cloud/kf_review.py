# -*- coding: utf-8 -*-
"""写实首帧审查拼图（11-27，踩坑 71）：每个镜头一行「白模首帧 | 写实首帧」，下面写上该镜头应有的人数、谁看得见脸、场景光线，
人工逐张核对：人数对不对、有没有多出的人或脸、衣着（陈瑶无领带、林晓深灰卫衣）、光线时间（傍晚/夜里不能是白天）、朝向和姿势。
用法：python cloud/kf_review.py <写实首帧目录> [已审过的镜头清单.txt]  → <目录>/_review_##.jpg（每张 8 个镜头）
加 --end：审写实尾帧 <id>@end.png（踩坑 91），一行「白模尾帧 | 写实尾帧 | 写实首帧」，还要看尾帧和首帧是不是同一个房间、同样的人和衣着"""
import os, sys, json, glob
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import looks
END = '--end' in sys.argv; sys.argv = [a for a in sys.argv if a != '--end']
src = sys.argv[1]; PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
SKIP = set(open(sys.argv[2], encoding='utf-8').read().split()) if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else set()   # 已审过合格的镜头（每批只看新出的）
PREFIX = '_review_end_' if END else ('_review_new_' if SKIP else '_review_')
FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20) if os.path.exists('C:/Windows/Fonts/msyh.ttc') else ImageFont.load_default()
W, H = 480, 270
rows = []
for kp in sorted(glob.glob(os.path.join(src, 's*_*_*.png'))):
    tid = os.path.basename(kp)[:-4]
    if END:
        if not tid.endswith('@end') or tid in SKIP: continue
        tid = tid[:-4]
    elif '@' in tid or tid in SKIP: continue
    if not os.path.exists(os.path.join(PACK, tid, 'task.json')): continue
    t = json.load(open(os.path.join(PACK, tid, 'task.json'), encoding='utf-8'))
    grey = cv2.imread(os.path.join(PACK, tid, 'end.png' if END else 'first.png')); real = cv2.imread(kp)
    if grey is None or real is None: continue
    row = np.hstack([cv2.resize(grey, (W, H)), cv2.resize(real, (W, H))])
    if END:   # 第三张：写实首帧，对照是不是同一个房间、同样的人
        f0 = cv2.imread(os.path.join(src, tid + '.png')); row = np.hstack([row, cv2.resize(f0, (W, H)) if f0 is not None else np.zeros((H, W, 3), np.uint8)])
        ec = t.get('end_cast', t.get('characters', []))
        t = dict(t, characters=[c for c in t.get('characters', []) if c in ec], others=[c for c in ec if c not in t.get('characters', [])],
                 extras=t.get('end_extras', 0), face_visible=t.get('face_visible_end'))
    n = len(t.get('characters', [])) + len(t.get('others', [])) + int(t.get('extras', 0) or 0)
    who = '、'.join(looks.NAME.get(c, c) for c in t.get('characters', [])) or '无'
    fv = t.get('face_visible'); fvs = '看得见脸：' + ('、'.join(looks.NAME.get(c, c) for c in fv) if fv else '无') if fv is not None else ''
    im = Image.fromarray(cv2.cvtColor(row, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(im)
    txt = '%s  %s  主角:%s  共%d人  %s' % (tid, t.get('set', ''), who, n, fvs)
    d.rectangle([0, 0, 2 * W, 26], fill=(0, 0, 0)); d.text((6, 2), txt, font=FONT, fill=(255, 230, 0))
    rows.append(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
for k in range(0, len(rows), 8):
    cv2.imwrite(os.path.join(src, PREFIX + '%02d.jpg' % (k // 8 + 1)), np.vstack(rows[k:k + 8]), [cv2.IMWRITE_JPEG_QUALITY, 88])
print('审查拼图 %d 张（%d 个镜头）→ %s' % ((len(rows) + 7) // 8, len(rows), src))
