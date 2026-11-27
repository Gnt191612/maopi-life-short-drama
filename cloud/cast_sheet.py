# -*- coding: utf-8 -*-
"""角色形象对照图（本地）：每个镜头取 3 帧（首、中、尾），检测人脸 → 按本镜头出场角色认人（和标准照相似度）
→ 裁头肩（含发型、衣领），同一角色按镜头顺序排成一张图，标出镜头号和相似度；用来一眼检查全片里同一角色长相、发型、衣着是否一致。
2026-11-26：用户想确认已合格镜头里各角色形象有没有大的差异。
用法：python cloud/cast_sheet.py <合并结果目录（含 real/<任务id>/frame_####.png）> → build/review/cast/<角色>.jpg + cast.json"""
import os, sys, json, glob, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import torch  # noqa: F401  先加载 CUDA 库
from insightface.app import FaceAnalysis
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); OUT = os.path.join(ROOT, 'build', 'review', 'cast'); os.makedirs(OUT, exist_ok=True)
app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'], allowed_modules=['detection', 'recognition']); app.prepare(ctx_id=0, det_size=(640, 640))
NAME = dict(lin='林晓', chen='陈瑶', zhou='周明远', mom='林母', wang='王', classA='同学甲', classB='同学乙')

def canon():
    out = {}
    for p in glob.glob(os.path.join(PACK, 'refs', 'canon_*.jpg')):
        c = os.path.basename(p)[6:-4]; im = cv2.imread(p); im = cv2.copyMakeBorder(im, 300, 300, 300, 300, cv2.BORDER_CONSTANT, value=(128, 128, 128))
        fs = app.get(cv2.resize(im, None, fx=0.5, fy=0.5))
        if fs: out[c] = (max(fs, key=lambda f: f.bbox[2] - f.bbox[0]), cv2.imread(p))
    return out
REF = canon()
T = 150   # 每格边长

def crop(img, f):
    x0, y0, x1, y1 = f.bbox; w = x1 - x0; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + w * 0.35; s = w * 1.25
    a = img[max(0, int(cy - s)):int(cy + s), max(0, int(cx - s)):int(cx + s)]
    return cv2.resize(a, (T, T)) if a.size else np.zeros((T, T, 3), np.uint8)

real = os.path.join(sys.argv[1], 'real'); cells = {}; stats = {}
for tdir in sorted(d for d in glob.glob(os.path.join(real, '*')) if os.path.isdir(d) and not d.endswith('stale')):
    tid = os.path.basename(tdir).replace('_aligned', ''); tj = os.path.join(PACK, tid, 'task.json')
    if not os.path.exists(tj): continue
    chars = [c for c in json.load(open(tj, encoding='utf-8')).get('characters', []) if c in REF]
    fr = sorted(glob.glob(os.path.join(tdir, 'frame_*.png')))
    if not chars or not fr: continue
    for p in (fr[len(fr) // 5], fr[len(fr) // 2], fr[len(fr) * 4 // 5]):
        img = cv2.imread(p); fs = [f for f in app.get(img) if f.det_score > 0.6 and f.bbox[2] - f.bbox[0] > 30]
        pairs = sorted(((float(np.dot(f.normed_embedding, REF[c][0].normed_embedding)), i, c) for i, f in enumerate(fs) for c in chars), reverse=True)
        uf, uc = set(), set()
        for s, i, c in pairs:
            if i in uf or c in uc: continue
            uf.add(i); uc.add(c); cells.setdefault(c, []).append((tid, s, crop(img, fs[i]))); stats.setdefault(c, []).append((tid, round(s, 3)))
for c, lst in cells.items():
    cols = 12; rows = (len(lst) + 1 + cols - 1) // cols
    sheet = np.full((rows * (T + 18), cols * T, 3), 30, np.uint8)
    items = [('标准照', 1.0, cv2.resize(REF[c][1], (T, T)))] + lst
    for k, (tid, s, im) in enumerate(items):
        r, q = divmod(k, cols); y, x = r * (T + 18), q * T
        sheet[y:y + T, x:x + T] = im
        col = (0, 255, 255) if s >= 0.45 else (0, 165, 255) if s >= 0.30 else (0, 0, 255)
        cv2.putText(sheet, '%s %.2f' % (tid[:11] if tid != '标准照' else 'CANON', s), (x + 2, y + T + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.36, col, 1)
    cv2.imwrite(os.path.join(OUT, '%s.jpg' % c), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    v = [s for _, s in stats[c]]; print('%s(%s) 格数 %d 平均 %.2f 最低 %.2f 低于0.30: %s' % (NAME.get(c, c), c, len(v), np.mean(v), min(v),
          sorted({t for t, s in stats[c] if s < 0.30})), flush=True)
json.dump(stats, open(os.path.join(OUT, 'cast.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
