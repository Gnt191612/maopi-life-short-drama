# -*- coding: utf-8 -*-
"""镜头衔接检查拼图（本地）：同一片段里相邻两个镜头，一行 = 上一镜头写实末帧 | 下一镜头写实首帧 | 两者对应的白模（末帧 | 首帧）。
人工看衔接：鞋/衣服/吃喝的东西前后状态、人在现实时间内能不能走到那里、光线时间背景是否一致（2026-11-25 用户要求）。
结尾和下一镜头对不上的，把上一镜头记进 build/logs/drift_tasks.txt → 全片后用锚点模式重跑（结尾落回白模，自然接上下一镜头）。
用法：python cloud/continuity_review.py <写实视频目录> → build/review/continuity/cont_##.jpg（每张 8 行）"""
import os, sys, glob, json, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); OUT = os.path.join(ROOT, 'build', 'review', 'continuity'); os.makedirs(OUT, exist_ok=True)
W, H = 360, 206

def frame(p, last):
    cap = cv2.VideoCapture(p); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n - 1) if last else 0); ok, im = cap.read()
    return cv2.resize(im, (W, H)) if ok else np.zeros((H, W, 3), np.uint8)

def main():
    src = sys.argv[1]
    tasks = json.load(open(os.path.join(PACK, 'manifest.json'), encoding='utf-8'))['tasks']
    rows = []
    for a, b in zip(tasks, tasks[1:]):
        if a.rsplit('_', 1)[0] != b.rsplit('_', 1)[0]: continue   # 跨片段（换场）不查
        pa, pb = os.path.join(src, a + '.mp4'), os.path.join(src, b + '.mp4')
        if not (os.path.exists(pa) and os.path.exists(pb)): continue
        ga, gb = os.path.join(PACK, a, 'beauty.mp4'), os.path.join(PACK, b, 'beauty.mp4')
        row = np.hstack([frame(pa, True), frame(pb, False), frame(ga, True) if os.path.exists(ga) else np.zeros((H, W, 3), np.uint8),
                         frame(gb, False) if os.path.exists(gb) else np.zeros((H, W, 3), np.uint8)])
        cv2.line(row, (W, 0), (W, H), (0, 255, 255), 2)
        cv2.putText(row, '%s > %s' % (a, b[-4:]), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2); rows.append(row)
    for i in range(0, len(rows), 8):
        cv2.imwrite(os.path.join(OUT, 'cont_%02d.jpg' % (i // 8)), np.vstack(rows[i:i + 8]), [cv2.IMWRITE_JPEG_QUALITY, 78])
    print('CONT SHEETS', len(rows), '对', (len(rows) + 7) // 8, '张')

if __name__ == '__main__':
    main()
