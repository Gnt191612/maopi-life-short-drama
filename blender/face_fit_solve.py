# -*- coding: utf-8 -*-
"""脸型拟合 · 第 2 步（普通 Python，numpy/scipy/opencv）：按照片关键点求 MakeHuman 五官形态目标的权重。
输入：face_fit_export.py 导出的 <cid>_head.npz + assets/identity/<cid>_landmarks_full.json
做法：照片视角（偏航/俯仰角网格搜索）下正交投影模型关键点；交替求「照片→模型平面的相似变换」与「形态目标权重」（带边界的最小二乘 + 正则，
权重越小越接近普通人脸）；脸部外轮廓按高度取模型投影的最外侧顶点，每轮重新选。
输出：build/face_fit/<cid>_fit.json（目标名 → 权重）+ 叠加对比图 <cid>_fit_overlay.png
python blender/face_fit_solve.py <cid>"""
import os, sys, json
import numpy as np, cv2
from scipy.optimize import lsq_linear
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'face_fit')
PMAX = int(os.environ.get('FIT_PMAX', 6))   # 俯仰角搜索范围（度）：照片基本平视，放太宽会用抬头低头去「冒充」脸的上下比例
LAMBDA = 0.02        # 正则强度（相对两眼间距²）：越大越保守
W = dict(eye=3.0, nose=2.0, mouth=2.0, chin=2.0, contour=1.0, skull=0.8)   # 头骨轮廓是按头发外缘估的，权重低一点

def load(cid):
    z = np.load(os.path.join(OUT, cid + '_head.npz'))
    lm = json.load(open(os.path.join(ROOT, 'assets', 'identity', cid + '_landmarks_full.json'), encoding='utf-8'))
    return z, lm

def groups(z):
    tn = list(z['tnames']); G, gname = [], []
    for pos, neg in z['vars']:
        for t in (pos, neg):
            if not t: continue
            names = ['l-' + t[3:], 'r-' + t[3:]] if t.startswith('LR:') else [t]
            G.append(sum(z['D'][tn.index(n)] for n in names)); gname.append(names)
    return np.array(G), gname     # (J, N, 3)

def rot(yaw, pitch):
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]); Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rx @ Rz

class Model:
    def __init__(s, z):
        s.X0 = z['X'].astype(float); s.N = z['N']; s.iod = float(z['iod']); s.G, s.gname = groups(z)
        s.lips = z['lips']; s.ears = z['ears']; s.scalp = z['scalp']; s.loopL = z['loopL']; s.loopR = z['loopR']
        X = s.X0; c = (z['cL'] + z['cR']) / 2; s.c = c; i = s.iod
        mid = np.abs(X[:, 0] - c[0]) < i * 0.06
        zone = mid & (X[:, 2] < c[2] - i * 0.2) & (X[:, 2] > c[2] - i * 1.3)
        s.nose = np.nonzero(zone)[0][np.argmin(X[zone, 1])]
        # 鼻底：鼻尖下方、法线朝下的鼻小柱底面，取最靠后的那个点（与上唇交界）
        below = mid & (X[:, 2] < X[s.nose, 2]) & (X[:, 2] > X[s.nose, 2] - i * 0.42) & (s.N[:, 2] < -0.4) & (X[:, 1] < X[s.nose, 1] + i * 0.35)   # 范围收紧：原来会选到上唇
        s.subnasal = np.nonzero(below)[0][np.argmax(X[below, 1])] if below.any() else s.nose
        lipz = X[s.lips, 2].min()
        # 下巴：先找唇下最突出的点（颏前点），再在它附近（排除更靠后的脖子）取最低点
        ch = mid & (X[:, 2] < lipz - i * 0.2) & (X[:, 2] > lipz - i * 1.6)
        pog = np.nonzero(ch)[0][np.argmin(X[ch, 1])]
        ch2 = mid & (X[:, 2] < X[pog, 2]) & (X[:, 1] < X[pog, 1] + i * 0.45)
        s.chin = np.nonzero(ch2)[0][np.argmin(X[ch2, 2])]
        s.cand = ~s.ears & ~s.scalp & ~s.lips & (X[:, 2] > X[s.chin, 2] - i * 0.05) & (X[:, 1] < X[s.chin, 1] + i * 1.6)
        nz = (X[:, 2] < X[s.nose, 2] + i * 0.05) & (X[:, 2] > max(X[s.subnasal, 2], X[s.nose, 2] - i * 0.40) - i * 0.02) & (np.abs(X[:, 0] - c[0]) < i * 0.42) & (X[:, 1] < X[s.nose, 1] + i * 0.30) & ~s.lips   # 鼻翼只在鼻尖以下 0.4 眼距内找（原来会落到脸颊、嘴角附近）
        s.alazone = nz
    def shape(s, u): return s.X0 + np.tensordot(u, s.G, 1)

def pick(m, Y, R, lm_q):
    """当前形状 Y、旋转 R 下选出各关键点对应的顶点；lm_q = 照片点换算到模型平面后的坐标（轮廓按高度选点要用）"""
    P = Y @ R.T; u, v = P[:, 0], P[:, 2]; sel = {}
    for side, loop in (('L', m.loopL), ('R', m.loopR)):
        lu = u[loop]; out_ = loop[np.argmax(lu)] if side == 'L' else loop[np.argmin(lu)]; in_ = loop[np.argmin(lu)] if side == 'L' else loop[np.argmax(lu)]
        sel['eye_%s_out' % side] = out_; sel['eye_%s_in' % side] = in_
        cu = (u[out_] + u[in_]) / 2; w = abs(u[out_] - u[in_])
        near = loop[np.abs(lu - cu) < w * 0.12]
        # 睑缘环包含上下眼皮较宽的一圈：上眼睑取环内侧（最低的上边缘），用「靠近眼球中心高度」的一侧
        cz = (v[out_] + v[in_]) / 2
        up = near[v[near] > cz]; dn = near[v[near] < cz]
        sel['eye_%s_top' % side] = up[np.argmin(v[up])] if len(up) else near[np.argmax(v[near])]
        sel['eye_%s_bot' % side] = dn[np.argmax(v[dn])] if len(dn) else near[np.argmin(v[near])]
    sel['nose'] = m.nose; sel['subnasal'] = m.subnasal; sel['chin'] = m.chin
    az = np.nonzero(m.alazone)[0]; cu = u[m.nose]
    sel['ala_L'] = az[np.argmax(u[az])]; sel['ala_R'] = az[np.argmin(u[az])]
    lp = np.nonzero(m.lips)[0]
    sel['mouth_L'] = lp[np.argmax(u[lp])]; sel['mouth_R'] = lp[np.argmin(u[lp])]
    midl = lp[np.abs(u[lp] - cu) < m.iod * 0.05]
    sel['lip_top'] = midl[np.argmax(v[midl])]; sel['lip_bot'] = midl[np.argmin(v[midl])]
    cand = np.nonzero(m.cand)[0]
    ez = (v[sel['eye_L_out']] + v[sel['eye_R_out']]) / 2; cz = v[m.chin]; cy = P[m.chin, 1]
    for side in ('R', 'L'):
        for k, (q) in enumerate(lm_q['contour_' + side]):
            t = np.clip((ez - q[1]) / max(ez - cz, 1e-6), 0, 1)
            near = cand[P[cand, 1] < cy + m.iod * (0.6 + 1.6 * (1 - t))]   # 越靠近下巴，轮廓点越靠前（排除下巴高度两侧露出的脖子）
            band = near[np.abs(v[near] - q[1]) < m.iod * 0.05]
            if len(band) == 0: band = cand[np.argsort(np.abs(v[cand] - q[1]))[:30]]
            sel['contour_%s_%d' % (side, k)] = band[np.argmax(u[band])] if side == 'L' else band[np.argmin(u[band])]
    # 头骨轮廓（额头到头顶高度，含头皮，不含耳朵）与头顶
    sk = np.nonzero(~m.ears)[0]
    for side in ('R', 'L'):
        for k, q in enumerate(lm_q.get('skull_' + side, [])):
            band = sk[np.abs(v[sk] - q[1]) < m.iod * 0.05]
            if len(band) == 0: band = sk[np.argsort(np.abs(v[sk] - q[1]))[:30]]
            sel['skull_%s_%d' % (side, k)] = band[np.argmax(u[band])] if side == 'L' else band[np.argmin(u[band])]
    sel['skull_top'] = sk[np.argmax(v[sk])]
    return sel

def weight_of(k):
    if k.startswith('skull'): return W['skull']
    return W['eye'] if k.startswith('eye') else W['nose'] if k in ('nose', 'subnasal') or k.startswith('ala') else \
           W['mouth'] if k.startswith(('mouth', 'lip')) else W['chin'] if k == 'chin' else W['contour']

def photo_points(lm):
    pts = {k: np.array(v, float) for k, v in lm.items() if not k.startswith(('_', 'contour', 'skull_R', 'skull_L', 'hairline', 'skin_top')) and k not in ('eye_R', 'eye_L')
           and isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)}   # 只要单个点（skin_top、keep_brow3d 等不是关键点）
    for name in ('contour', 'skull'):
        for side in ('R', 'L'):
            for k, (y, x) in enumerate(lm.get('%s_%s' % (name, side), [])): pts['%s_%s_%d' % (name, side, k)] = np.array([x, y], float)
    return pts

def similarity(A, B, w):
    """求 s,R,t 使 s R A + t ≈ B（A 已翻转成 y 朝上）"""
    w = w / w.sum(); ma, mb = (w[:, None] * A).sum(0), (w[:, None] * B).sum(0)
    a, b = A - ma, B - mb; H = (w[:, None] * a).T @ b; U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); Dm = np.diag([1, d]); R = Vt.T @ Dm @ U.T
    s = (S * np.diag(Dm)).sum() / (w * (a ** 2).sum(1)).sum(); return s, R, mb - s * R @ ma

def fit(m, lm, yaw, pitch, iters=25, lam=LAMBDA, solve=True):
    R = rot(yaw, pitch); pts = photo_points(lm); keys = list(pts)
    Pp = np.array([pts[k] for k in keys]) * np.array([1, -1])   # 照片 y 朝下 → 翻成朝上
    wv = np.array([weight_of(k) for k in keys]); u = np.zeros(len(m.G))
    lists = {n: len([k for k in keys if k.startswith(n + '_')]) for n in ('contour_R', 'contour_L', 'skull_R', 'skull_L')}
    lm_q = {n: [] for n in lists}
    for it in range(iters):
        Y = m.shape(u); P = Y @ R.T
        if it == 0:   # 第一轮先用非轮廓点求相似变换
            sel = pick(m, Y, R, {n: [[0, 0]] * c for n, c in lists.items()})
            nk = [i for i, k in enumerate(keys) if not k.startswith(('contour', 'skull'))]
            M2 = np.array([[P[sel[keys[i]], 0], P[sel[keys[i]], 2]] for i in nk])
            s, Rs, t = similarity(Pp[nk], M2, wv[nk])
        Q = (s * (Rs @ Pp.T)).T + t          # 照片点在模型平面中的位置
        for n, c in lists.items():
            lm_q[n] = [Q[keys.index('%s_%d' % (n, k))] for k in range(c)]
        sel = pick(m, Y, R, lm_q)
        idx = np.array([sel[k] for k in keys]); M2 = P[idx][:, [0, 2]]
        s, Rs, t = similarity(Pp, M2, wv)
        Q = (s * (Rs @ Pp.T)).T + t
        if not solve: break
        # 线性化：M2(u + du) ≈ P0[idx] + J (u+du)，J = 各目标在所选顶点的投影位移
        J = np.einsum('jnc,kc->njk', m.G[:, idx], R[[0, 2]])          # (n, J, 2)
        base = (m.X0[idx] @ R.T)[:, [0, 2]]
        A = (J.transpose(0, 2, 1) * np.sqrt(wv)[:, None, None]).reshape(-1, len(m.G))
        b = ((Q - base) * np.sqrt(wv)[:, None]).reshape(-1)
        A = np.vstack([A, np.sqrt(lam) * m.iod * np.eye(len(m.G))]); b = np.r_[b, np.zeros(len(m.G))]
        u_new = lsq_linear(A, b, bounds=(0, 1)).x
        if np.abs(u_new - u).max() < 1e-4: u = u_new; break
        u = 0.5 * u + 0.5 * u_new
    Y = m.shape(u); P = Y @ R.T; sel = pick(m, Y, R, lm_q); idx = np.array([sel[k] for k in keys]); M2 = P[idx][:, [0, 2]]
    err = np.linalg.norm(M2 - Q, axis=1) / m.iod
    return dict(u=u, err=err, keys=keys, cost=float((wv * err ** 2).sum() / wv.sum()), s=s, Rs=Rs, t=t, R=R, sel=sel, yaw=yaw, pitch=pitch)

def to_photo(r, pts2):
    """模型平面坐标 → 照片像素"""
    p = (r['Rs'].T @ ((pts2 - r['t']) / r['s']).T).T; return p * np.array([1, -1])

def overlay(m, lm, r0, r1, path):
    img = cv2.imread(os.path.join(ROOT, 'assets', 'identity', lm['_cid'] + '.png'))
    pts = photo_points(lm); panels = []
    for r, title in ((r0, 'before (current base)'), (r1, 'fitted')):
        im = img.copy(); Y = m.shape(r['u']); P = (Y @ r['R'].T)[:, [0, 2]]
        front = (m.N @ r['R'].T)[:, 1] < -0.2
        for p in to_photo(r, P[front & m.cand][::2]): cv2.circle(im, (int(p[0]), int(p[1])), 1, (255, 200, 0), -1)
        mp = to_photo(r, P[[r['sel'][k] for k in r['keys']]])
        for k, q in zip(r['keys'], mp):
            a = pts[k]; cv2.line(im, tuple(a.astype(int)), tuple(q.astype(int)), (0, 0, 255), 2)
            cv2.circle(im, tuple(a.astype(int)), 5, (0, 255, 0), -1); cv2.circle(im, tuple(q.astype(int)), 5, (0, 0, 255), -1)
        cv2.putText(im, '%s  err %.3f iod' % (title, r['cost'] ** 0.5), (20, 60), 0, 1.4, (0, 0, 255), 3)
        allp = np.array(list(pts.values())); x0, y0 = allp.min(0) - 120; x1, y1 = allp.max(0) + 120   # 按关键点范围裁切（各角色照片尺寸不同）
        panels.append(cv2.resize(im[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)], (600, 700)))
    cv2.imwrite(path, np.hstack(panels))

def main(cid):
    z, lm = load(cid); lm['_cid'] = cid; m = Model(z)
    best = None
    for yaw in np.radians(np.arange(-30, 31, 3)):
        for pitch in np.radians(np.arange(-PMAX, PMAX + 1, 2)):
            r = fit(m, lm, yaw, pitch, iters=12)
            if best is None or r['cost'] < best['cost']: best = r
    r1 = fit(m, lm, best['yaw'], best['pitch'], iters=40)
    r0 = fit(m, lm, best['yaw'], best['pitch'], solve=False)
    weights = {}
    for uj, names in zip(r1['u'], m.gname):
        if uj > 0.02:
            for n in names: weights[n] = round(float(uj), 3)
    res = dict(cid=cid, yaw_deg=round(float(np.degrees(r1['yaw'])), 1), pitch_deg=round(float(np.degrees(r1['pitch'])), 1),
               err_before=round(r0['cost'] ** 0.5, 4), err_after=round(r1['cost'] ** 0.5, 4),
               per_point={k: round(float(e), 3) for k, e in zip(r1['keys'], r1['err'])}, weights=weights,
               # 关键点对应的网格顶点序号（MakeHuman 基础网格全序号），照片贴脸（face_project.py）用它们做对齐
               landmark_verts={k: int(z['hidx'][r1['sel'][k]]) for k in r1['keys']},
               # 照片像素 → 模型投影平面（偏航/俯仰旋转后的 x、z，米，未缩放的基础网格）：q = s·R·(x, −y) + t。发际线等照片标注投到模型上用
               eye_z=float((z['cL'][2] + z['cR'][2]) / 2),   # 拟合时（未改身材）两眼中心高度：发际线等照片投影按它补偿头的上下移动
               photo_to_model=dict(s=float(r1['s']), R=np.asarray(r1['Rs']).tolist(), t=np.asarray(r1['t']).tolist()))
    json.dump(res, open(os.path.join(OUT, cid + '_fit.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    overlay(m, lm, r0, r1, os.path.join(OUT, cid + '_fit_overlay.png'))
    print(json.dumps({k: v for k, v in res.items() if k != 'per_point'}, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main(sys.argv[1])

