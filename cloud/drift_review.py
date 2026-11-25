# -*- coding: utf-8 -*-
"""跑偏检查拼图（本地）：每个镜头一行 = 白模首帧 | 白模末帧 | 写实首帧 | 写实中间 | 写实末帧，人工看哪些镜头跑偏
（人物从坐变站、换了房间、多出人、动作和剧情不符），把任务 id 记进 build/logs/drift_tasks.txt，全片后用锚点模式重跑。
用法：python cloud/drift_review.py <写实视频目录> [任务id前缀 ...] → build/review/drift/drift_##.jpg（每张 8 行）"""
import os, sys, glob, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); OUT = os.path.join(ROOT, 'build', 'review', 'drift'); os.makedirs(OUT, exist_ok=True)
W, H = 300, 172

def frames(p, picks):
    cap = cv2.VideoCapture(p); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); res = []
    for k in picks(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(n - 1, k))); ok, im = cap.read()
        res.append(cv2.resize(im, (W, H)) if ok else np.zeros((H, W, 3), np.uint8))
    return res

def main():
    src = sys.argv[1]; pre = sys.argv[2:]
    rows = []
    for mp4 in sorted(glob.glob(os.path.join(src, '*.mp4'))):
        tid = os.path.basename(mp4)[:-4]
        if pre and not any(tid.startswith(p) for p in pre): continue
        bea = os.path.join(PACK, tid, 'beauty.mp4')
        g = frames(bea, lambda n: (0, n - 1)) if os.path.exists(bea) else [np.zeros((H, W, 3), np.uint8)] * 2
        r = frames(mp4, lambda n: (0, n // 2, n - 1))
        row = np.hstack(g + r); cv2.putText(row, tid, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2); rows.append(row)
    for i in range(0, len(rows), 8):
        cv2.imwrite(os.path.join(OUT, 'drift_%02d.jpg' % (i // 8)), np.vstack(rows[i:i + 8]), [cv2.IMWRITE_JPEG_QUALITY, 78])
    print('DRIFT SHEETS', len(rows), '个镜头', (len(rows) + 7) // 8, '张')

if __name__ == '__main__':
    main()
