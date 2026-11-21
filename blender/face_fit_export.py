# -*- coding: utf-8 -*-
"""脸型拟合 · 第 1 步（Blender 内）：导出头部网格与各五官形态目标的位移，交给 face_fit_solve.py 求解。
基础人体 = 角色宏参数 + 共用立体度层（DEPTH_F/M）+ 只影响侧面的个人特征（正面照片看不出来，保留原设定）；
其余正面能看出来的形态目标全部置 0，由拟合程序按照片重新求。
blender -b --factory-startup -P blender/face_fit_export.py -- <cid> <输出.npz>"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE, os.path.join(HERE, 'lib')]
import bpy, numpy as np
import build_cast as bc
from build_cast import HumanService, TargetService

# 拟合变量：(正向目标, 反向目标)；'LR:' 前缀 = 左右成对同值
VARS = [
    ('head-scale-horiz-incr', 'head-scale-horiz-decr'), ('head-scale-vert-incr', 'head-scale-vert-decr'),
    ('head-oval', None), ('head-round', None), ('head-triangular', None), ('head-invertedtriangular', None),
    ('head-square', None), ('head-diamond', None), ('head-rectangular', None),
    ('chin-width-incr', 'chin-width-decr'), ('chin-height-incr', 'chin-height-decr'), ('chin-triangle', None),
    ('chin-bones-incr', 'chin-bones-decr'), ('chin-jaw-drop-incr', 'chin-jaw-drop-decr'),
    ('LR:cheek-volume-incr', 'LR:cheek-volume-decr'), ('LR:cheek-bones-incr', 'LR:cheek-bones-decr'),
    ('LR:cheek-inner-incr', 'LR:cheek-inner-decr'), ('LR:cheek-trans-up', 'LR:cheek-trans-down'),
    ('forehead-temple-incr', 'forehead-temple-decr'),
    ('LR:eye-scale-incr', 'LR:eye-scale-decr'), ('LR:eye-trans-out', 'LR:eye-trans-in'), ('LR:eye-trans-up', 'LR:eye-trans-down'),
    ('LR:eye-height1-incr', 'LR:eye-height1-decr'), ('LR:eye-height2-incr', 'LR:eye-height2-decr'), ('LR:eye-height3-incr', 'LR:eye-height3-decr'),
    ('LR:eye-corner1-up', 'LR:eye-corner1-down'), ('LR:eye-corner2-up', 'LR:eye-corner2-down'),
    ('nose-scale-horiz-incr', 'nose-scale-horiz-decr'), ('nose-scale-vert-incr', 'nose-scale-vert-decr'),
    ('nose-trans-up', 'nose-trans-down'), ('nose-point-width-incr', 'nose-point-width-decr'),
    ('nose-flaring-incr', 'nose-flaring-decr'), ('nose-nostrils-width-incr', 'nose-nostrils-width-decr'),
    ('nose-width3-incr', 'nose-width3-decr'),
    ('mouth-scale-horiz-incr', 'mouth-scale-horiz-decr'), ('mouth-scale-vert-incr', 'mouth-scale-vert-decr'),
    ('mouth-trans-up', 'mouth-trans-down'), ('mouth-angles-up', 'mouth-angles-down'),
    ('mouth-upperlip-height-incr', 'mouth-upperlip-height-decr'), ('mouth-lowerlip-height-incr', 'mouth-lowerlip-height-decr'),
    ('mouth-upperlip-volume-incr', 'mouth-upperlip-volume-decr'), ('mouth-lowerlip-volume-incr', 'mouth-lowerlip-volume-decr'),
    ('mouth-cupidsbow-incr', 'mouth-cupidsbow-decr'), ('mouth-upperlip-width-incr', 'mouth-upperlip-width-decr'),
]
# 只影响侧面轮廓、正面照片判断不了的个人特征：保留原设定
PROFILE_KEEP = ('nose-greek', 'nose-hump', 'eyebrows-trans', 'eyebrows-angle', 'eye-eyefold', 'nose-point-up', 'nose-width1', 'chin-prominent')

def names_of(t):
    if t is None: return []
    return ['l-' + t[3:], 'r-' + t[3:]] if t.startswith('LR:') else [t]

def base_human(cid):
    name, g, age, wt, mu, ht, pr = bc.CAST[cid][:7]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bc.addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
    macro = {'gender': g, 'age': age, 'muscle': mu, 'weight': wt, 'proportions': pr, 'height': ht, 'cupsize': 0.5, 'firmness': 0.5, 'race': bc.ASIAN}
    body = HumanService.create_human(macro_detail_dict=macro); body.name = cid + '_body'
    scale = bc.FACE_SCALE_OF.get(cid, bc.FACE_SCALE)
    for n, v in bc.FACE.get(cid, {}).items():
        base = n[2:] if n[:2] in ('l-', 'r-') else n
        if any(base.startswith(k) for k in PROFILE_KEEP):
            TargetService.load_target(body, TargetService.target_full_path(n), weight=v * scale, name=n)
    depth = bc.DEPTH_M if g > 0.5 else bc.DEPTH_F
    for n, v in depth.items():
        TargetService.load_target(body, TargetService.target_full_path(n), weight=v, name='depth_' + n)
    return body

def main(cid, out):
    body = base_human(cid); me = body.data
    M = np.array(body.matrix_world)[:3, :3]
    gi = {g.name: g.index for g in body.vertex_groups}
    def members(gname):
        idx = gi[gname]; return np.array([any(g.group == idx and g.weight > 0.5 for g in v.groups) for v in me.vertices])
    helper = members('HelperGeometry') | members('JointCubes')
    lips, ears, scalp = members('lips'), members('ears'), members('scalp')
    eyeL, eyeR = members('joint-l-eye'), members('joint-r-eye')
    for m_ in body.modifiers: m_.show_viewport = False   # MPFB 自带的遮罩修改器会删掉辅助几何体，顶点序号就对不上了
    def current():
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co)
        no = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('normal', no)
        ev.to_mesh_clear(); return co.reshape(-1, 3) @ M.T, no.reshape(-1, 3) @ M.T
    X, Nn = current()
    cL, cR = X[eyeL].mean(0), X[eyeR].mean(0); iod = float(np.linalg.norm(cL - cR))
    head = (~helper) & (X[:, 2] > cL[2] - iod * 3.2)
    # 眼裂（睑缘）：用睫毛辅助网格的根部（睫毛长在睑缘上）。辅助网格隐藏但随形态目标一起变形
    def lid_ring(side):
        E = X[members('helper-%s-eye' % side)]; c = E.mean(0); R = float(np.linalg.norm(E - c, axis=1).mean())
        lash = members('helper-%s-eyelashes-1' % side) | members('helper-%s-eyelashes-2' % side)
        d = np.linalg.norm(X - c, axis=1)
        ring = np.nonzero(lash & (d < np.percentile(d[lash], 40)))[0]   # 离眼球中心最近的那部分 = 睫毛根
        print('DBG eye R %.4f lash %d ring %d' % (R, int(lash.sum()), len(ring)), flush=True)
        return ring
    loopL, loopR = lid_ring('l'), lid_ring('r')
    head = head | np.isin(np.arange(len(X)), np.r_[loopL, loopR])
    # 各形态目标的位移（形态键坐标 − 基础坐标）
    basis = np.empty(len(me.vertices) * 3, np.float32); me.shape_keys.key_blocks['Basis'].data.foreach_get('co', basis); basis = basis.reshape(-1, 3)
    tnames, D = [], []
    for pos, neg in VARS:
        for t in names_of(pos) + names_of(neg):
            if t in tnames: continue
            kb = TargetService.load_target(body, TargetService.target_full_path(t), weight=0.0, name='fit_' + t)
            kb = me.shape_keys.key_blocks['fit_' + t]
            co = np.empty(len(me.vertices) * 3, np.float32); kb.data.foreach_get('co', co)
            D.append(((co.reshape(-1, 3) - basis) @ M.T)[head]); tnames.append(t)
    hi = np.nonzero(head)[0]; remap = -np.ones(len(X), int); remap[hi] = np.arange(len(hi))
    np.savez_compressed(out, X=X[head], N=Nn[head], D=np.array(D, np.float32), tnames=np.array(tnames),
                        vars=np.array([[p or '', n or ''] for p, n in VARS]), lips=lips[head], ears=ears[head], scalp=scalp[head],
                        loopL=remap[loopL], loopR=remap[loopR], cL=cL, cR=cR, iod=iod, hidx=hi)
    print('EXPORT OK', cid, 'head verts', len(hi), 'targets', len(tnames), 'iod %.4f' % iod, 'loops', len(loopL), len(loopR), flush=True)

if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]; main(a[0], a[1])
