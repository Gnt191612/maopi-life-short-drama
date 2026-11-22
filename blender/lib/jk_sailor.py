# -*- coding: utf-8 -*-
"""水手服（JK）程序生成：素材库里没有合身的女式水手服，直接从身体表面「长」一件贴身长袖上衣，再加水手领、领巾、袖口。
- 上衣：取身体躯干+手臂（腰线以上、脖子根以下、手腕以上）的表面往外 3.5mm，带身体的骨骼权重 → 随动作变形，天生合身；
  身体被上衣盖住的内部用遮罩隐藏（动作时不穿模）
- 水手领：前面 V 字到胸口、后面方形披到肩胛下，黑色，沿边缘两道白线
- 领巾：V 领底部打结、两条飘带垂下（蓝色）
- 袖口：手腕处一圈黑色，两道白线
参数见 SAILOR。所有部件挂在骨架上。"""
import math
import bpy, bmesh
import numpy as np
from mathutils import Vector as V, Matrix as Mx
from mathutils.bvhtree import BVHTree

SAILOR = {'classB': dict(shirt=(0.86, 0.86, 0.85), collar=(0.012, 0.012, 0.016), stripe=(0.85, 0.85, 0.84), scarf=(0.010, 0.055, 0.42),
                         off=0.0035, v_depth=0.16, back_len=0.17, cuff=0.045)}

# V 领长袖上衣（林母，用户 11-22 给的参考图：黑色 V 领、垂坠、干练）：同样从身体表面长出来；穿在裤子外面，下摆盖过裤腰 hem
VTOP = {'mom': dict(rgb=(0.006, 0.006, 0.007), rough=0.58, off=0.007, v_depth=0.12, v_half=0.100, hem=0.032, tuck=False, ext=0.045, loose=0.009, arm_loose=0.005, slope=0.12, drape_max=0.045)}   # 第 2 轮（用户：再宽松一点）   # 第 1 版太亮像皮衣、太紧：哑光、离身体远一点；扎进高腰裤（下摆再低就到裆部以下，两腿之间没有皮肤可长）

def build_vtop(cid, rig, body, bottom):
    S = VTOP[cid]; MW = rig.matrix_world
    nk = MW @ rig.pose.bones['neck01'].head; zn, ncx, ncy = nk.z, nk.x, nk.y
    zt = max((bottom.matrix_world @ v.co).z for v in bottom.data.vertices) if bottom else zn - 0.45   # 裤腰
    z_hem = zt - S['hem']
    mods = [(m, m.show_viewport) for m in body.modifiers if m.type in ('MASK', 'SUBSURF')]
    for m, _ in mods: m.show_viewport = False
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh(); M = body.matrix_world
    P = [M @ v.co for v in me.vertices]; Nn = [(M.to_3x3() @ v.normal).normalized() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]; ev.to_mesh_clear()
    for m, s in mods: m.show_viewport = s
    gi = {g.index: g.name for g in body.vertex_groups}
    def w_of(v, keys): return sum(g.weight for g in v.groups if any(k in gi.get(g.group, '') for k in keys))
    hand = [w_of(v, ('wrist', 'hand', 'finger', 'metacarpal', 'thumb')) > 0.25 for v in body.data.vertices]
    helper = [w_of(v, ('helper', 'joint', 'HelperGeometry', 'JointCubes')) > 0.5 for v in body.data.vertices]
    def neck_line(p):
        neck_z = zn - 0.004 - 0.016 * max(0.0, min(1.0, (ncy - p.y) / 0.06))
        if p.y < ncy: neck_z = min(neck_z, zn - 0.004 - S['v_depth'] * max(0.0, 1 - abs(p.x - ncx) / S['v_half']))
        return neck_z
    def inside(i):
        p = P[i]
        neck_z = zn - 0.004 - 0.016 * max(0.0, min(1.0, (ncy - p.y) / 0.06))
        if p.y < ncy:   # 正面 V 领：中线最低（v_depth），往两侧 v_half 线性升回领口
            neck_z = min(neck_z, zn - 0.004 - S['v_depth'] * max(0.0, 1 - abs(p.x - ncx) / S['v_half']))
        return (not hand[i]) and (not helper[i]) and z_hem < p.z < neck_z
    vin = [inside(i) for i in range(len(P))]
    faces = [f for f in polys if all(vin[i] for i in f)]
    used = sorted({i for f in faces for i in f}); rm = {o: k for k, o in enumerate(used)}
    armv = np.array([w_of(body.data.vertices[i], ('arm', 'shoulder', 'clavicle')) > 0.3 for i in used])
    zc_ = (MW @ rig.pose.bones['spine01'].head).z
    def off_of(k, i):   # 领口附近贴身（V 领边落在皮肤上），越往下越松；袖子整体略松
        if armv[k]: return S['off'] + S.get('arm_loose', 0.0)
        return S['off'] + S.get('loose', 0.0) * max(0.0, min(1.0, (zn - 0.08 - P[i].z) / 0.14))
    TPs = np.array([(P[i] + Nn[i] * off_of(k, i))[:] for k, i in enumerate(used)])
    # 胸前撑平（两胸之间不勒进去）
    selc = (~armv) & (np.abs(TPs[:, 2] - zc_) < 0.10) & (np.abs(TPs[:, 0] - ncx) < 0.15) & (TPs[:, 1] < ncy)
    for z in np.arange(zc_ - 0.10, zc_ + 0.10, 0.006):
        band_ = np.nonzero(selc & (np.abs(TPs[:, 2] - z) < 0.005))[0]
        if len(band_) < 5: continue
        order = band_[np.argsort(TPs[band_, 0])]; xs, ys = TPs[order, 0], TPs[order, 1]; hull = []
        for j in range(len(order)):
            while len(hull) >= 2 and (xs[hull[-1]] - xs[hull[-2]]) * (ys[j] - ys[hull[-2]]) - (ys[hull[-1]] - ys[hull[-2]]) * (xs[j] - xs[hull[-2]]) <= 0: hull.pop()
            hull.append(j)
        hy = np.interp(xs, xs[hull], ys[hull]); TPs[order, 1] = np.maximum(hy, ys - 0.04)
    # 胸部以下垂坠：从胸部最高点往下只略往里收（不贴肚子），下摆不收（穿在裤子外面）
    zsD = np.arange(z_hem, zc_ + 0.10, 0.006); ymin = []
    for z in zsD:
        bd = np.nonzero((~armv) & (np.abs(TPs[:, 2] - z) < 0.004) & (np.abs(TPs[:, 0] - ncx) < 0.12) & (TPs[:, 1] < ncy))[0]
        ymin.append(TPs[bd, 1].min() if len(bd) else np.nan)
    ymin = np.array(ymin); ok_ = ~np.isnan(ymin)
    front = (~armv) & (TPs[:, 2] < zc_ + 0.06) & (np.abs(TPs[:, 0] - ncx) < 0.20) & (TPs[:, 1] < ncy + 0.02)
    for i in np.nonzero(front)[0]:
        z = TPs[i, 2]; up = ok_ & (zsD >= z) & (zsD <= z + 0.16)
        if not up.any(): continue
        lim = (ymin[up] + (zsD[up] - z) * S.get('slope', 0.25)).min()
        dxa = max(0.0, abs(TPs[i, 0] - ncx) - 0.04) / 0.20; wx = max(0.0, 1 - dxa) ** 2
        if TPs[i, 1] > lim: TPs[i, 1] += max(lim - TPs[i, 1], -S.get('drape_max', 0.03)) * wx
    # 背后同理：从肩胛往下垂，不贴腰
    ymax = []
    for z in zsD:
        bd = np.nonzero((~armv) & (np.abs(TPs[:, 2] - z) < 0.004) & (np.abs(TPs[:, 0] - ncx) < 0.12) & (TPs[:, 1] > ncy))[0]
        ymax.append(TPs[bd, 1].max() if len(bd) else np.nan)
    ymax = np.array(ymax); okb = ~np.isnan(ymax)
    back = (~armv) & (TPs[:, 2] < zc_ + 0.04) & (np.abs(TPs[:, 0] - ncx) < 0.20) & (TPs[:, 1] > ncy - 0.02)
    for i in np.nonzero(back)[0]:
        z = TPs[i, 2]; up = okb & (zsD >= z) & (zsD <= z + 0.16)
        if not up.any(): continue
        lim = (ymax[up] - (zsD[up] - z) * S.get('slope', 0.25)).max()
        dxa = max(0.0, abs(TPs[i, 0] - ncx) - 0.04) / 0.20; wx = max(0.0, 1 - dxa) ** 2
        if TPs[i, 1] < lim: TPs[i, 1] += min(lim - TPs[i, 1], S.get('drape_max', 0.03) * 0.6) * wx
    # 裤腰以下的部分罩在裤子外面（否则裤腰从衣服里顶出来）
    # 扎进裤子时：裤腰处上衣往外撑到贴着裤腰内侧（否则裤腰和上衣之间露一道皮肤缝）
    if bottom is not None:
        dgb = bpy.context.evaluated_depsgraph_get(); eb = bottom.evaluated_get(dgb); mb = eb.to_mesh()
        bvh = BVHTree.FromPolygons([bottom.matrix_world @ v.co for v in mb.vertices], [tuple(p.vertices) for p in mb.polygons]); eb.to_mesh_clear()
        disp = np.zeros_like(TPs)
        for k in range(len(TPs)):
            if armv[k]: continue
            if S.get('tuck'):
                if not (z_hem - 0.01 < TPs[k, 2] < zt + 0.005): continue
                q = V(TPs[k]); loc, nrm, _, d = bvh.find_nearest(q)
                if loc is None or d > 0.05: continue
                if (q - loc).dot(nrm) < 0 and d > 0.003: disp[k] = np.array((loc - nrm * 0.003)[:]) - TPs[k]
                continue
            if TPs[k, 2] > z_hem + 0.06: continue                              # 更高处的裤腰已藏在上衣里（hide_under），只管下摆附近
            q = V(TPs[k]); loc, nrm, _, d = bvh.find_nearest(q)
            if loc is None or d > 0.06: continue
            if (q - loc).dot(nrm) < 0 or d < 0.006: disp[k] = np.array((loc + nrm * 0.008)[:]) - TPs[k]
        # 外推量往周围渐变（只推一部分点会在裤腰上方留下一道波浪折痕）：邻点取「自己」与「邻居均值 ×0.85」中较大的
        nbr = [set() for _ in range(len(TPs))]
        for f in faces:
            ids = [rm[i] for i in f]
            for a in ids: nbr[a].update(ids)
        for _ in range(10):
            avg = np.array([disp[list(n)].mean(0) if n else disp[k] for k, n in enumerate(nbr)])
            take = (np.linalg.norm(avg, axis=1) * 0.85 > np.linalg.norm(disp, axis=1)) & ~armv
            disp[take] = avg[take] * 0.85
        TPs += disp
    # 领口边缘：网格台阶 → 边界点挪到 V 字线上再贴回身体表面（原来锯齿状）
    from collections import Counter
    ec = Counter(tuple(sorted((rm[f[j]], rm[f[(j + 1) % len(f)]]))) for f in faces for j in range(len(f)))
    bnd = {k for e, c in ec.items() if c == 1 for k in e}
    bvb = BVHTree.FromPolygons(P, polys)
    for k in bnd:
        q = V(TPs[k])
        if q.z > zc_ + 0.02: q.z = neck_line(q)                           # 领口（含肩部）
        elif q.z < zt and not armv[k]: TPs[k, 2] = z_hem; continue         # 下摆：同一高度（袖口不动；只改高度，保留罩在裤子外的外推）
        else: continue
        loc, nrm, _, _ = bvb.find_nearest(q)
        if loc is not None: TPs[k] = (loc + nrm * S['off'])[:]
    verts = [V(p) for p in TPs]; tfaces = [[rm[i] for i in f] for f in faces]; src_of = list(used)   # 每个上衣顶点抄哪个身体顶点的权重
    # 下摆往下续一圈布（ext）：皮肤长出来的上衣到不了裆部以下，而林母裤腰前面比裆部还低，正面总留一条缝。
    # 下摆是一整圈环，往下续不需要两腿之间有皮肤；续的部分罩在身体和裤子外面，略往外张
    if S.get('ext', 0) > 0 and not S.get('tuck'):
        hem_e = [e for e, c in ec.items() if c == 1 and all(abs(TPs[k, 2] - z_hem) < 1e-6 and not armv[k] for k in e)]
        hk = sorted({k for e in hem_e for k in e})
        bvp = None
        if bottom is not None:
            eb = bottom.evaluated_get(bpy.context.evaluated_depsgraph_get()); mb = eb.to_mesh()
            bvp = BVHTree.FromPolygons([bottom.matrix_world @ v.co for v in mb.vertices], [tuple(p.vertices) for p in mb.polygons]); eb.to_mesh_clear()
        cx_ = float(TPs[hk, 0].mean()) if hk else ncx; cy_ = float(TPs[hk, 1].mean()) if hk else ncy
        nv = {}; nseg = 3
        for k in hk:
            prev = k
            for s_ in range(1, nseg + 1):
                f_ = s_ / nseg; q = V(TPs[k]) + V((0, 0, -S['ext'] * f_))
                rad = V((q.x - cx_, q.y - cy_, 0)); rad = rad.normalized() if rad.length > 1e-6 else V((0, -1, 0))
                q += rad * 0.006 * f_                                              # 略往外张
                for t in [bvb] + ([bvp] if bvp else []):                          # 罩在身体、裤子外面
                    loc, nrm, _, d = t.find_nearest(q)
                    if loc is None: continue
                    if (q - loc).dot(nrm) < 0 or d < 0.007: q = loc + nrm * 0.008
                verts.append(q); src_of.append(used[k]); nv[(k, s_)] = len(verts) - 1
        for a, b_ in hem_e:
            for s_ in range(1, nseg + 1):
                pa = a if s_ == 1 else nv[(a, s_ - 1)]; pb = b_ if s_ == 1 else nv[(b_, s_ - 1)]
                tfaces.append([pa, pb, nv[(b_, s_)], nv[(a, s_)]])
        print('VTOP ext', len(hk), 'hem verts', flush=True)
    sm = bpy.data.meshes.new(cid + '_vtop'); sm.from_pydata(verts, [], tfaces); sm.update()
    bm_n = bmesh.new(); bm_n.from_mesh(sm); bmesh.ops.recalc_face_normals(bm_n, faces=bm_n.faces[:]); bm_n.to_mesh(sm); bm_n.free()
    for p in sm.polygons: p.use_smooth = True
    top = bpy.data.objects.new(cid + '_vtop', sm); bpy.context.scene.collection.objects.link(top)
    src = body.data.vertices
    for g in body.vertex_groups:
        if any(k in g.name for k in ('helper', 'joint', 'Delete', 'v11_')): continue
        ng = top.vertex_groups.new(name=g.name); gidx = g.index
        for k, i in enumerate(src_of):
            for e in src[i].groups:
                if e.group == gidx and e.weight > 1e-4: ng.add([k], e.weight, 'REPLACE')
    m = _mat(cid + '_vtop', S['rgb'], S['rough'])
    b = m.node_tree.nodes['Principled BSDF']
    if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = 0.15; b.inputs['Sheen Roughness'].default_value = 0.5   # 垂坠面料的柔光
    sm.materials.append(m)
    am = top.modifiers.new('rig', 'ARMATURE'); am.object = rig
    so = top.modifiers.new('thick', 'SOLIDIFY'); so.thickness = 0.0015; so.offset = 1.0
    sd = top.modifiers.new('subdiv', 'SUBSURF'); sd.levels = 1; sd.render_levels = 2
    top.parent = rig; top['v11_cloth'] = True
    bm_ = bmesh.new(); bm_.from_mesh(sm); boundary = {v.index for v in bm_.verts if v.is_boundary}; bm_.free()
    ring = set(boundary)
    for _ in range(2):
        ring |= {j for f in faces for j in (rm[i] for i in f) if any(rm[i] in ring for i in f)}
    hid = [used[k] for k in range(len(used)) if k not in ring or (S.get('tuck') and not armv[k] and TPs[k, 2] < zt + 0.012)]   # 扎进裤子：下摆边那两圈被裤子盖着，也藏（原来在裤腰处露一道皮肤缝）
    vg = body.vertex_groups.new(name='v11_vtop_covered'); vg.add(hid, 1.0, 'REPLACE')
    mk = body.modifiers.new('v11_vtop_covered', 'MASK'); mk.vertex_group = vg.name; mk.invert_vertex_group = True
    ia = next((k for k, m_ in enumerate(body.modifiers) if m_.type == 'ARMATURE'), -1); body.modifiers.move(len(body.modifiers) - 1, ia + 1)
    print('VTOP OK', cid, 'faces', len(faces), 'hem', round(z_hem, 3), 'hidden', len(hid), flush=True)
    return top

def _mat(name, rgb, rough=0.75, cloth=True):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.25
    return m

def _bone_parent(ob, rig, bone):
    MW = rig.matrix_world; pb = rig.pose.bones[bone]
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = bone
    ob.matrix_parent_inverse = (MW @ pb.matrix @ Mx.Translation((0, pb.length, 0))).inverted()

def _skin_like(ob, top, rig, TPs, top_groups):
    """按最近的上衣顶点抄骨骼权重（领子、领巾随肩膀一起动；原来挂在胸椎上，手臂放下时肩部衣服会顶出来盖住领子）"""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(TPs))
    for k, p in enumerate(TPs): kd.insert(V(p), k)
    kd.balance()
    groups = {g.name: ob.vertex_groups.new(name=g.name) for g in top.vertex_groups}
    for v in ob.data.vertices:
        _, k, _ = kd.find(ob.matrix_world @ v.co)
        for gname, w in top_groups[k]: groups[gname].add([v.index], w, 'REPLACE')
    am = ob.modifiers.new('rig', 'ARMATURE'); am.object = rig
    ob.modifiers.move(len(ob.modifiers) - 1, 0); ob.parent = rig

def build(cid, rig, body, skirt):
    S = SAILOR[cid]; MW = rig.matrix_world
    zn = (MW @ rig.pose.bones['neck01'].head).z; ncx = (MW @ rig.pose.bones['neck01'].head).x; ncy = (MW @ rig.pose.bones['neck01'].head).y
    z_waist = max((skirt.matrix_world @ v.co).z for v in skirt.data.vertices) - 0.035 if skirt else zn - 0.40
    # ---- 身体（关掉遮罩、细分，拿到完整的静止网格；顶点序号与基础网格一致）----
    mods = [(m, m.show_viewport) for m in body.modifiers if m.type in ('MASK', 'SUBSURF')]
    for m, _ in mods: m.show_viewport = False
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh(); M = body.matrix_world
    P = [M @ v.co for v in me.vertices]; Nn = [(M.to_3x3() @ v.normal).normalized() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]; ev.to_mesh_clear()
    for m, s in mods: m.show_viewport = s
    gi = {g.index: g.name for g in body.vertex_groups}
    def w_of(v, keys): return sum(g.weight for g in v.groups if any(k in gi.get(g.group, '') for k in keys))
    hand = [w_of(v, ('wrist', 'hand', 'finger', 'metacarpal', 'thumb')) > 0.25 for v in body.data.vertices]
    helper = [w_of(v, ('helper', 'joint', 'HelperGeometry', 'JointCubes')) > 0.5 for v in body.data.vertices]
    # 领口：脖子根（前低后高，像真实领口）
    def inside(i):
        p = P[i]
        neck_z = zn - 0.004 - 0.016 * max(0.0, min(1.0, (ncy - p.y) / 0.06))   # 领口贴近脖子根（原来开得太低，肩颈处露出一圈）
        return (not hand[i]) and (not helper[i]) and z_waist < p.z < neck_z and abs(p.x - ncx) < 0.95
    vin = [inside(i) for i in range(len(P))]
    faces = [f for f in polys if all(vin[i] for i in f)]
    used = sorted({i for f in faces for i in f}); rm = {o: k for k, o in enumerate(used)}
    # ---- 1) 上衣 ----
    TPs = np.array([(P[i] + Nn[i] * S['off'])[:] for i in used])
    # 胸前布料不勒进乳沟：胸部高度每个横截面的正面取「下凸包」（两胸之间被布料撑平，最多补 2.5cm）
    armv = np.array([w_of(body.data.vertices[i], ('arm', 'shoulder', 'clavicle')) > 0.3 for i in used])
    zc_ = (MW @ rig.pose.bones['spine01'].head).z
    selc = (~armv) & (np.abs(TPs[:, 2] - zc_) < 0.10) & (np.abs(TPs[:, 0] - ncx) < 0.15) & (TPs[:, 1] < ncy)
    for z in np.arange(zc_ - 0.10, zc_ + 0.10, 0.006):
        band_ = np.nonzero(selc & (np.abs(TPs[:, 2] - z) < 0.005))[0]
        if len(band_) < 5: continue
        order = band_[np.argsort(TPs[band_, 0])]; xs, ys = TPs[order, 0], TPs[order, 1]; hull = []
        for j in range(len(order)):
            while len(hull) >= 2 and (xs[hull[-1]] - xs[hull[-2]]) * (ys[j] - ys[hull[-2]]) - (ys[hull[-1]] - ys[hull[-2]]) * (xs[j] - xs[hull[-2]]) <= 0: hull.pop()
            hull.append(j)
        hy = np.interp(xs, xs[hull], ys[hull]); TPs[order, 1] = np.maximum(hy, ys - 0.04)
    # 胸部以下宽松：上衣从胸部最高点自然垂下（不贴着胸下、肚子往里收），越往下越慢慢收回腰（用户：现实中这里是宽松的）
    selD = (~armv) & (TPs[:, 2] < zc_ + 0.06) & (TPs[:, 2] > z_waist) & (np.abs(TPs[:, 0] - ncx) < 0.20)
    front = selD & (TPs[:, 1] < ncy + 0.02)
    zsD = np.arange(z_waist, zc_ + 0.10, 0.006); ymin = []
    for z in zsD:
        bd = np.nonzero((~armv) & (np.abs(TPs[:, 2] - z) < 0.004) & (np.abs(TPs[:, 0] - ncx) < 0.12) & (TPs[:, 1] < ncy))[0]
        ymin.append(TPs[bd, 1].min() if len(bd) else np.nan)
    ymin = np.array(ymin); ok_ = ~np.isnan(ymin)
    for i in np.nonzero(front)[0]:
        z = TPs[i, 2]; up = ok_ & (zsD >= z) & (zsD <= z + 0.16)
        if not up.any(): continue
        lim = (ymin[up] + (zsD[up] - z) * 0.22).min()                    # 布料从高处往下、只略往里收
        dxa = max(0.0, abs(TPs[i, 0] - ncx) - 0.04) / 0.16; wx = max(0.0, 1 - dxa) ** 2   # 正中最明显，往两侧平滑过渡（太陡会把侧面撕开）
        wz = min(1.0, (z - z_waist) / 0.05)                               # 下摆处收回腰（塞进裙子）
        if TPs[i, 1] > lim: TPs[i, 1] += max(lim - TPs[i, 1], -0.03) * wx * wz   # 最多往前 3cm
    sm = bpy.data.meshes.new(cid + '_sailor_top'); sm.from_pydata([V(p) for p in TPs], [], [[rm[i] for i in f] for f in faces]); sm.update()
    for p in sm.polygons: p.use_smooth = True
    top = bpy.data.objects.new(cid + '_sailor_top', sm); bpy.context.scene.collection.objects.link(top)
    # 骨骼权重照抄身体
    src = body.data.vertices
    for g in body.vertex_groups:
        if any(k in g.name for k in ('helper', 'joint', 'Delete', 'v11_')): continue
        ng = top.vertex_groups.new(name=g.name); gidx = g.index
        for i in used:
            for e in src[i].groups:
                if e.group == gidx and e.weight > 1e-4: ng.add([rm[i]], e.weight, 'REPLACE')
    # 袖口：离手腕 cuff 以内的面换黑色材质
    sm.materials.append(_mat(cid + '_sailor_white', S['shirt'])); sm.materials.append(_mat(cid + '_sailor_black', S['collar'], 0.7))
    hand_pts = np.array([P[i][:] for i in range(len(P)) if hand[i] and not helper[i]])
    from mathutils.kdtree import KDTree
    kd = KDTree(len(hand_pts))
    for k, p in enumerate(hand_pts): kd.insert(p, k)
    kd.balance()
    TP = [P[i] for i in used]
    for poly in sm.polygons:
        c = sum((TP[j] for j in poly.vertices), V()) / len(poly.vertices)
        if kd.find(c)[2] < S['cuff']: poly.material_index = 1
    am = top.modifiers.new('rig', 'ARMATURE'); am.object = rig
    sd = top.modifiers.new('subdiv', 'SUBSURF'); sd.levels = 1; sd.render_levels = 2
    top.parent = rig; top['v11_cloth'] = True
    # 身体被上衣盖住的内部隐藏（留边上一圈，避免露缝）
    bm_ = bmesh.new(); bm_.from_mesh(sm); boundary = {v.index for v in bm_.verts if v.is_boundary}; bm_.free()
    ring = set(boundary)
    for _ in range(2):
        ring |= {j for f in faces for j in (rm[i] for i in f) if any(rm[i] in ring for i in f)}
    hid = [used[k] for k in range(len(used)) if k not in ring]
    vg = body.vertex_groups.new(name='v11_sailor_covered'); vg.add(hid, 1.0, 'REPLACE')
    mk = body.modifiers.new('v11_sailor_covered', 'MASK'); mk.vertex_group = vg.name; mk.invert_vertex_group = True
    ia = next((k for k, m in enumerate(body.modifiers) if m.type == 'ARMATURE'), -1); body.modifiers.move(len(body.modifiers) - 1, ia + 1)
    # ---- 2) 水手领：照真实领型在 (方位角 θ, 高度 z) 上画一条带子，从领口中轴水平打射线贴到上衣表面 ----
    # 内沿 = 领口（正面是 V 字，θ=0 在 V 底），外沿 = 内沿往外平移 28°（正面成为两条斜带，到 V 底收成尖），过了肩膀后在背后落到披肩下沿
    # 带子的横向坐标 v（0 内沿 → 1 外沿）存成 UV，着色器里在靠外沿处画两道白线
    tbvh = BVHTree.FromPolygons([V(p) for p in TPs], [[rm[i] for i in f] for f in faces])
    zv = zn - S['v_depth']; zb = zn - 0.032; zf = zn - S['back_len']   # zb 放低：领口处上衣边缘在脖子根以下，射线打不到会缺一块
    def z_in(a):    # a = |θ|（度）
        return zv + (zb - zv) * min(1.0, a / 62.0) if a < 62 else zb + 0.004 * min(1.0, (a - 62) / 60)
    def z_out(a):
        if a < 100: return z_in(max(0.0, a - 17.0)) - 0.004 * min(1.0, a / 17.0)   # 正面领子宽约 8cm（外沿是内沿往外平移 17°）
        t = min(1.0, (a - 100) / 28.0); zo = z_in(83.0) - 0.004
        return zo + (zf - zo) * (t * t * (3 - 2 * t))
    def onsurf(a_deg, z, lift):
        r = math.radians(a_deg); d = V((math.sin(r), -math.cos(r), 0))
        h = tbvh.ray_cast(V((ncx, ncy, z)), d, 0.5)
        if h[0] is None: return None
        n_ = h[1] if h[1].dot(d) > 0 else -h[1]
        return h[0] + n_ * lift
    NU, NV = 121, 7
    bmc = bmesh.new(); uvl = bmc.loops.layers.uv.new('UVMap'); grid = []
    for iu in range(NU):
        th = -180.0 + 360.0 * iu / (NU - 1); a = abs(th); row = []
        for iv in range(NV):
            t = iv / (NV - 1); z = z_in(a) + (z_out(a) - z_in(a)) * t
            p = onsurf(th, z, 0.0035 + 0.0005 * t)
            row.append(bmc.verts.new(p) if p is not None else None)
        grid.append(row)
    for iu in range(NU - 1):
        for iv in range(NV - 1):
            q = (grid[iu][iv], grid[iu + 1][iv], grid[iu + 1][iv + 1], grid[iu][iv + 1])
            if None in q or len({x.index if x.index >= 0 else id(x) for x in q}) < 4: continue
            try: f = bmc.faces.new(q)
            except ValueError: continue
            for lp, (uu, vv) in zip(f.loops, ((iu, iv), (iu + 1, iv), (iu + 1, iv + 1), (iu, iv + 1))): lp[uvl].uv = (uu / (NU - 1), vv / (NV - 1))
    bmesh.ops.remove_doubles(bmc, verts=[v for v in bmc.verts], dist=0.0015)   # V 底处宽度为 0 的点合并
    cm = bpy.data.meshes.new(cid + '_sailor_collar'); bmc.to_mesh(cm); bmc.free()
    for p in cm.polygons: p.use_smooth = True
    cmat = bpy.data.materials.new(cid + '_sailor_collar'); cmat.use_nodes = True; nt = cmat.node_tree
    b = nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 0.7
    uvn = nt.nodes.new('ShaderNodeUVMap'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(uvn.outputs['UV'], sep.inputs['Vector'])
    def band(a0, a1):
        r1 = nt.nodes.new('ShaderNodeMath'); r1.operation = 'GREATER_THAN'; r1.inputs[1].default_value = a0; nt.links.new(sep.outputs['Y'], r1.inputs[0])
        r2 = nt.nodes.new('ShaderNodeMath'); r2.operation = 'LESS_THAN'; r2.inputs[1].default_value = a1; nt.links.new(sep.outputs['Y'], r2.inputs[0])
        m_ = nt.nodes.new('ShaderNodeMath'); m_.operation = 'MULTIPLY'; nt.links.new(r1.outputs[0], m_.inputs[0]); nt.links.new(r2.outputs[0], m_.inputs[1]); return m_.outputs[0]
    s1, s2 = band(0.70, 0.76), band(0.82, 0.88)                          # 靠外沿两道白线
    ad = nt.nodes.new('ShaderNodeMath'); ad.operation = 'ADD'; nt.links.new(s1, ad.inputs[0]); nt.links.new(s2, ad.inputs[1])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = (*S['collar'], 1); mx.inputs[7].default_value = (*S['stripe'], 1)
    nt.links.new(ad.outputs[0], mx.inputs['Factor']); nt.links.new(mx.outputs[2], b.inputs['Base Color'])
    cm.materials.append(cmat)
    collar = bpy.data.objects.new(cid + '_sailor_collar', cm); bpy.context.scene.collection.objects.link(collar)
    s2_ = collar.modifiers.new('thick', 'SOLIDIFY'); s2_.thickness = 0.0015; s2_.offset = 1.0
    sd2 = collar.modifiers.new('subdiv', 'SUBSURF'); sd2.levels = 1; sd2.render_levels = 2
    tg = [[(top.vertex_groups[e.group].name, e.weight) for e in v.groups] for v in top.data.vertices]
    _skin_like(collar, top, rig, TPs, tg)
    # ---- 3) 领巾：沿领口 V 字内沿（压在领子下面）到 V 底打结，两条飘带垂下 ----
    bm2 = bmesh.new()
    def ribbon(path, widths, wdir, thick=0.0018, closed=False):
        rows = []; n = len(path)
        for i, p in enumerate(path):
            t = (path[(i + 1) % n if closed else min(i + 1, n - 1)] - path[(i - 1) % n if closed else max(i - 1, 0)]).normalized()
            s = wdir(i); s = (s - t * s.dot(t)).normalized() * widths[i] / 2; th = t.cross(s).normalized() * thick / 2
            rows.append([bm2.verts.new(p + s + th), bm2.verts.new(p - s + th), bm2.verts.new(p - s - th), bm2.verts.new(p + s - th)])
        for a, b_ in zip(rows, rows[1:] + ([rows[0]] if closed else [])):
            for k in range(4): bm2.faces.new((a[k], a[(k + 1) % 4], b_[(k + 1) % 4], b_[k]))
        if not closed: bm2.faces.new(rows[0][::-1]); bm2.faces.new(rows[-1])
    for sx in (-1, 1):
        path = [p for p in (onsurf(sx * a, z_in(a) + 0.003, 0.0020) for a in [62 - 62 * k / 12 + 4 * (k / 12) for k in range(13)]) if p is not None]   # 压在领子内沿底下，只从领子边缘露出一条
        if len(path) > 2: ribbon(path, [0.026] * len(path), lambda i: V((0, 0, 1)))
    knot_c = onsurf(0, zv + 0.004, 0.0075)
    if knot_c is not None:
        for sx, swing in ((-1, 0.035), (1, -0.02)):   # 两条飘带：一长一短，交叉垂下，往下变宽
            L = 0.22 if sx < 0 else 0.18; path = []
            for f in [k / 12 for k in range(13)]:
                x_ = knot_c.x + sx * 0.004 + swing * f; z_ = zv - L * f   # 从正前方往后打射线取上衣正面（从领口中轴往外打会打到里面的面）
                h_ = tbvh.ray_cast(V((x_, ncy - 0.6, z_)), V((0, 1, 0)), 1.0)[0]
                q = (h_ + V((0, -(0.008 + 0.003 * f), 0))) if h_ is not None else (knot_c + V((0, 0, -L * f)))
                q.x = knot_c.x + sx * 0.004 + swing * f; path.append(q)
            ribbon(path, [0.022 + 0.016 * (k / 12) for k in range(13)], lambda i: V((1, 0, 0)))
        ring_ = [knot_c + V((0.012 * math.cos(2 * math.pi * k / 16), 0.006 * math.sin(2 * math.pi * k / 16) - 0.002, 0)) for k in range(16)]
        ribbon(ring_, [0.022] * 16, lambda i: V((0, 0, 1)), thick=0.003, closed=True)
    scm = bpy.data.meshes.new(cid + '_sailor_scarf'); bm2.to_mesh(scm); bm2.free()
    for p in scm.polygons: p.use_smooth = True
    scm.materials.append(_mat(cid + '_sailor_scarf', S['scarf'], 0.45))
    scarf = bpy.data.objects.new(cid + '_sailor_scarf', scm); bpy.context.scene.collection.objects.link(scarf)
    sd3 = scarf.modifiers.new('subdiv', 'SUBSURF'); sd3.levels = 1; sd3.render_levels = 2
    _skin_like(scarf, top, rig, TPs, tg)
    cfaces = cm.polygons
    print('SAILOR OK', cid, 'top faces', len(faces), 'collar faces', len(cfaces), 'hidden body verts', len(hid), flush=True)
    return top
