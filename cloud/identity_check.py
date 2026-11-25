# -*- coding: utf-8 -*-
"""人脸一致性检查（本地，InsightFace buffalo_l）：每个写实视频每 0.5 秒取一帧，检测所有人脸，
和人物库标准照（dist/cloud_pack/refs/canon_<cid>.jpg）比相似度，找出：
  - 长得不像本镜头任何出场角色的脸（视频后半段换了脸、冒出陌生人）
  - 性别和角色不符的脸（男主被画成女生）
  - 同一帧里脸比出场角色多（同一个人出现两次、多出路人）
2026-11-25：用户指出 s01_12、s02_03 里的林晓前后脸型头型差别大、认不出是同一个人，目测漏掉了，改成工具打分。
用法：python cloud/identity_check.py <real 目录> [<real 目录> ...] [--min-face 48] [--thr 0.30]
输出：build/review/identity.json + 控制台按问题严重程度排序"""
import os, sys, json, glob, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
def opt(k, d): return type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
MIN_FACE = opt('--min-face', 48); THR = opt('--thr', 0.30)
sys.path.insert(0, os.path.join(ROOT, 'cloud')); import looks
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider']); app.prepare(ctx_id=-1, det_size=(640, 640))
GENDER = {c: (0 if '女' in looks.LOOK[c].split('，')[0] or '母亲' in looks.LOOK[c] else 1) for c in looks.LOOK}   # insightface：1=男 0=女
REF = {}
for c in looks.LOOK:
    for p in (os.path.join(PACK, 'refs', 'canon_%s.jpg' % c), os.path.join(PACK, 'refs', 'canonface_%s.jpg' % c)):
        if os.path.exists(p):
            im = cv2.imread(p); fs = []
            for pad in (0, 0.35, 0.8):   # 脸占满整张图（裁脸图）或太大时检测不到：四周补边再试
                b = int(max(im.shape[:2]) * pad); im_ = cv2.copyMakeBorder(im, b, b, b, b, cv2.BORDER_CONSTANT, value=(128, 128, 128)) if b else im
                fs = app.get(cv2.resize(im_, None, fx=900 / max(im_.shape[:2]), fy=900 / max(im_.shape[:2])))
                if fs: break
            if fs: REF[c] = max(fs, key=lambda f: (f.bbox[2] - f.bbox[0])).normed_embedding; break
print('标准照', sorted(REF), flush=True)

def check(mp4, tid):
    tj = os.path.join(PACK, tid, 'task.json')
    chars = json.load(open(tj, encoding='utf-8')).get('characters', []) if os.path.exists(tj) else []
    cap = cv2.VideoCapture(mp4); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); res = []
    for k in range(0, n, 12):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, im = cap.read()
        if not ok: break
        im2 = cv2.resize(im, None, fx=2, fy=2) if im.shape[1] < 1000 else im   # 832×480 放大一倍，小脸也能检出
        faces = [f for f in app.get(im2) if f.bbox[2] - f.bbox[0] >= MIN_FACE and f.det_score > 0.6]
        fr = []
        for f in faces:
            yaw = abs(float(f.pose[1])) if getattr(f, 'pose', None) is not None else 0
            if yaw > 40: continue   # 侧脸相似度天然偏低，不参与打分
            sims = {c: float(np.dot(f.normed_embedding, e)) for c, e in REF.items()}
            best = max(sims, key=sims.get)
            own = max((sims[c] for c in chars if c in sims), default=-1)
            fr.append(dict(best=best, sim=round(sims[best], 3), own=round(own, 3), g=int(f.gender), w=int(f.bbox[2] - f.bbox[0])))
        res.append((k, fr))
    issues = []
    for k, fr in res:
        for f in fr:
            if chars and f['own'] < THR: issues.append(('陌生脸/换脸', k, f))
            elif chars:
                c = max(chars, key=lambda c: float(np.dot(REF[c], REF[c])) if c in REF else 0) if len(chars) == 1 else None
                if c and c in GENDER and f['g'] != GENDER[c] and f['own'] < 0.45: issues.append(('性别不符', k, f))
        if chars and len(fr) > len(chars): issues.append(('人脸多于角色', k, dict(n=len(fr), chars=len(chars))))
    owns = [f['own'] for _, fr in res for f in fr if chars]
    return dict(id=tid, chars=chars, frames=len(res), faces=len(owns), min_own=round(min(owns), 3) if owns else None,
                mean_own=round(float(np.mean(owns)), 3) if owns else None, issues=len(issues), detail=issues[:6])

out = []
for d in args:
    for mp4 in sorted(glob.glob(os.path.join(d, '*.mp4'))):
        tid = os.path.basename(mp4)[:-4]
        try: r = check(mp4, tid)
        except Exception as e: r = dict(id=tid, error=str(e))
        r['dir'] = d; out.append(r)
        print(tid, 'faces', r.get('faces'), 'min', r.get('min_own'), 'mean', r.get('mean_own'), 'issues', r.get('issues'), flush=True)
json.dump(out, open(os.path.join(ROOT, 'build', 'review', 'identity.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
bad = sorted([r for r in out if r.get('issues')], key=lambda r: -r['issues'])
print('\n=== 有问题的镜头（按问题帧数排序）===')
for r in bad: print(r['id'], r['chars'], '问题帧', r['issues'], '最低相似度', r['min_own'], [x[0] for x in r['detail']][:3])
