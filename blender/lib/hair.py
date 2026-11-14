# -*- coding: utf-8 -*-
"""真实发丝：以 MakeHuman 发片模型为发型轮廓，在头皮上种发根、让发丝贴着轮廓生长，
再用 Blender 自带的程序化发丝节点加毛躁/扰动/粗细渐变；材质用 Cycles 物理头发着色器（黑发）。发丝挂在头部骨骼上随头运动。"""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

import os
# Blender 自带的程序化发丝节点库（随 Blender 安装，按可执行文件位置推导，任何电脑通用）
LIB = os.path.join(os.path.dirname(bpy.app.binary_path), bpy.app.version_string[:3], 'datafiles', 'assets', 'geometry_nodes', 'procedural_hair_node_assets.blend')
# 发型参数：发丝最长(米)、生长步数、下垂程度、数量
STYLE = {'short02': dict(L=0.09, steps=10, droop=0.45, n=26000), 'short04': dict(L=0.07, steps=9, droop=0.4, n=24000),
         'short03': dict(L=0.07, steps=9, droop=0.4, n=24000), 'short01': dict(L=0.022, steps=4, droop=0.1, n=30000),
         'bob01': dict(L=0.22, steps=16, droop=0.75, n=26000), 'ponytail01': dict(L=0.36, steps=22, droop=0.8, n=26000),
         'wavybob': dict(L=0.20, steps=18, droop=0.55, n=30000)}   # 林母：沿微卷波波头轮廓生长

def _world_bvh(obj, dg):
    ev = obj.evaluated_get(dg); me = ev.to_mesh(); mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]; polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts, polys

def _node_group(name):
    if name not in bpy.data.node_groups:
        with bpy.data.libraries.load(LIB, link=False) as (src, dst): dst.node_groups = [name]
    return bpy.data.node_groups[name]

def hair_material(name, melanin=0.97):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL': nt.nodes.remove(n)
    h = nt.nodes.new('ShaderNodeBsdfHairPrincipled'); h.parametrization = 'MELANIN'
    h.inputs['Melanin'].default_value = melanin; h.inputs['Melanin Redness'].default_value = 0.08
    h.inputs['Roughness'].default_value = 0.28; h.inputs['Radial Roughness'].default_value = 0.32; h.inputs['Coat'].default_value = 0.15   # 健康光泽
    h.inputs['Random Roughness'].default_value = 0.2
    nt.links.new(h.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m

# ---------------- 男式短发：按真实发型结构生成（不依赖发片轮廓） ----------------
# 长度单位米：top 头顶 / front 刘海 / side 两侧 / back 后脑；lift 发根立起程度（体积）；messy 凌乱度；
# part 分缝（'L' 角色左侧 / 'R' 右侧 / None）；fringe 'down' 刘海下垂 / 'up' 上翘 / 'side' 梳向一侧；n 发丝数
SHORT = {   # 「蓬松但干净」：保留体积，减少毛躁乱翘；clump=0 不做成缕（实测显油腻），curl 卷曲半径(米)
 'lin':    dict(top=0.090, front=0.078, side=0.050, back=0.048, lift=0.48, messy=0.16, part=None, fringe='down', n=110000, clump=0, curl=0.0),     # 韩式碎盖
 'chen':   dict(top=0.082, front=0.080, side=0.034, back=0.034, lift=0.40, messy=0.05, part='L', fringe='side', n=105000, clump=0, curl=0.0),     # 韩式偏分
 'zhou':   dict(top=0.030, front=0.026, side=0.015, back=0.015, lift=0.70, messy=0.05, part=None, fringe='up', n=120000, clump=0, curl=0.0),      # 利落板寸
 'wang':   dict(top=0.055, front=0.052, side=0.020, back=0.020, lift=0.30, messy=0.04, part='R', fringe='side', n=95000, clump=0, curl=0.0),      # 偏短侧分
 'classA': dict(top=0.065, front=0.055, side=0.024, back=0.025, lift=0.70, messy=0.14, part=None, fringe='up', n=110000, clump=0, curl=0.0),     # 上翘短发
}

def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)

def build_short(cid, rig, body, shell, seed=1):
    S = SHORT[cid]; rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    bb, bv, bp = _world_bvh(body, dg)
    pb = rig.pose.bones; MW = rig.matrix_world
    eyeL, eyeR = MW @ pb['eye.L'].head, MW @ pb['eye.R'].head
    eyes = (eyeL + eyeR) / 2
    H = eyes + Vector((0, 0.085, 0.015))                     # 颅骨中心：两眼中点后方约 8.5cm
    brow_z = eyes.z + 0.03
    up, fwd = Vector((0, 0, 1)), Vector((0, -1, 0))           # 静止时面朝 -Y
    whorl = H + Vector((0, 0.055, 0.085))                     # 发旋：头顶偏后
    part_x = {'L': 0.035, 'R': -0.035}.get(S['part'])         # 分缝位置（角色左侧 = +X）

    def hairline_z(az):
        """发际线高度（按方位角，0=正前方，90=侧面，180=正后方）"""
        a = abs(az)
        front = brow_z + 0.045          # 前额发际线：眉上约 4.5cm
        temple = brow_z + 0.016         # 太阳穴略后收
        ear = eyes.z - 0.012            # 两鬓：绕过耳朵上缘，带一点鬓角
        behind = eyes.z - 0.035         # 耳后
        nape = eyes.z - 0.098           # 后颈发际线
        if a < 35: return front
        if a < 65: return front + (temple - front) * _smooth(35, 65, a)
        if a < 100: return temple + (ear - temple) * _smooth(65, 95, a)
        if a < 130: return ear + (behind - ear) * _smooth(100, 130, a)
        return behind + (nape - behind) * _smooth(130, 170, a)

    def region_len(c):
        """按部位插值长度：头顶长、两侧后脑短"""
        rel = c - H; az = math.degrees(math.atan2(rel.x, -rel.y))
        height = _smooth(eyes.z + 0.02, H.z + 0.07, c.z)                # 0 两侧下部 → 1 头顶
        frontness = _smooth(-0.02, 0.06, -rel.y)                         # 越靠前越像刘海
        side_back = S['back'] if abs(az) > 110 else S['side']
        L = side_back + (S['top'] - side_back) * height
        return L + (S['front'] - L) * frontness * height, az, height

    # 1) 头皮覆盖区（发际线以上、朝外的头部表面）
    cover, soft_faces = [], []
    for fi, p in enumerate(bp):
        if len(p) < 3: continue
        c = sum((bv[i] for i in p), Vector()) / len(p); rel = c - H
        if rel.length > 0.17: continue
        n = ((bv[p[1]] - bv[p[0]]).cross(bv[p[2]] - bv[p[0]])).normalized()
        if n.dot(rel) < 0: n = -n
        if n.dot(rel.normalized()) < 0.2: continue
        az = math.degrees(math.atan2(rel.x, -rel.y))
        hz = hairline_z(az)
        if c.z < hz - 0.012: continue
        if c.z < hz: soft_faces.append(fi); continue                        # 发际线下 1.2cm：过渡区（只种稀疏细发，不铺底色）
        cover.append(fi)
    if not cover: return None
    tris = []
    for fi in cover:
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2))
        if len(p) == 4: d4 = bv[p[3]]; tris.append((a, c, d4, ((c - a).cross(d4 - a)).length / 2))
    n_main = len(tris)
    for fi in soft_faces:
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2 * 0.3))
    import bisect
    total = sum(t[3] for t in tris); acc = []; s_ = 0
    for t in tris: s_ += t[3]; acc.append(s_)

    def clump_noise(root, k):
        """相邻发丝共享的扰动（按 1.2cm 网格取种子）→ 自然成缕"""
        key = (round(root.x / 0.012), round(root.y / 0.012), round(root.z / 0.012), k)
        r = random.Random(hash(key) & 0xffffffff)
        return Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)))

    strands = []
    for _ in range(S['n']):
        ti = min(len(tris) - 1, bisect.bisect_left(acc, rnd.random() * total)); t = tris[ti]; soft = ti >= n_main
        u, v = rnd.random(), rnd.random()
        if u + v > 1: u, v = 1 - u, 1 - v
        root = t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v
        nrm = ((t[1] - t[0]).cross(t[2] - t[0])).normalized()
        if nrm.dot(root - H) < 0: nrm = -nrm
        L, az, height = region_len(root); L *= rnd.uniform(0.8, 1.15)
        if soft: L *= rnd.uniform(0.3, 0.7)                                         # 发际线过渡区：短而稀
        # 2) 发流方向：从发旋向外放射；刘海按发型向前垂/上翘/梳向一侧；分缝两侧各自梳开
        flow = root - whorl
        rel = root - H
        if part_x is not None and rel.z > 0.025 and -rel.y > -0.07:
            # 分缝：分缝外侧（小边）往自己那侧梳下；内侧（大边）越过头顶梳向另一侧，前额的头发顺势斜扫
            side = 1.0 if (rel.x - part_x) * part_x > 0 else -1.0      # +1 = 小边
            to_x = (1.0 if part_x > 0 else -1.0) * (1.0 if side > 0 else -1.0)
            flow = Vector((to_x, -0.35, -0.15 if side > 0 else 0.05)) + flow * 0.25
        if S['fringe'] == 'up' and -rel.y > -0.02 and rel.z > 0.02:
            flow = flow + up * 1.2
        if S['fringe'] == 'back' and -rel.y > -0.03 and rel.z > 0.0:      # 侧背：前额头发向后上方梳
            flow = Vector((0, 1.0, 0.35)) + flow * 0.3
        flow = (flow - nrm * flow.dot(nrm))
        flow = flow.normalized() if flow.length > 1e-6 else fwd
        fstop = 0.004 + (clump_noise(root, 99).x * 0.5 + 0.5) * 0.028                   # 每一缕刘海停在不同高度
        if S['fringe'] == 'down' and -rel.y > 0.02: flow = (flow + Vector((clump_noise(root, 98).y * 0.6, 0, 0))).normalized()   # 碎刘海微微错开
        n_steps = max(4, min(16, int(L / 0.0045) + 3)); step = L / n_steps      # 控制点加密：曲线更柔顺
        lift = S['lift'] * (0.15 + 0.85 * _smooth(0.025, 0.07, (root - whorl).length)) * (0.25 + 0.75 * height)   # 两侧后脑贴头型，不外翘   # 发旋附近的头发顺着发流平躺（不立起来反光）
        d = (nrm * lift + flow * (1 - lift)).normalized()
        p = root + nrm * 0.0008; pts = [p.copy()]
        for k in range(n_steps):
            g = 0.25 if S['fringe'] == 'down' and -rel.y > 0.0 else (0.08 + 0.25 * (1 - height))   # 重力：刘海、两侧往下顺
            jitter = clump_noise(root, k // 3) * S['messy'] * 0.6 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * S['messy'] * 0.25
            d = (d * 0.65 + flow * 0.35 * (1 - S['lift'] * 0.5) - up * g + jitter * 0.4).normalized()
            if S['fringe'] == 'comma' and -rel.y > 0.03 and k > n_steps * 0.55:   # 逗号刘海：发梢向内勾成 C 形
                d = (d - (q_dir := (root - H).normalized()) * 0.45 - up * 0.25).normalized()
            q = p + d * step
            loc, nn, _, dist = bb.find_nearest(q)                               # 保持在头皮外：离开距离随长度增加 → 体积
            min_off = 0.0015 + (k + 1) / n_steps * (0.006 + S['lift'] * 0.012)   # 离头皮越远越蓬松：发量感
            if loc is not None and dist < min_off:
                out = (q - loc).normalized() if (q - loc).length > 1e-7 else nn
                if out.dot(q - H) < 0: out = -out
                q = loc + out * min_off
            relq = q - H
            if relq.dot(fwd) > 0.035 and q.z < brow_z + fstop: break              # 刘海长短错落、不遮眼睛
            d = (q - p).normalized(); p = q; pts.append(p.copy())
        if len(pts) >= 2: strands.append(pts)
    # 3) 曲线 + 材质
    hc = bpy.data.hair_curves.new(cid + '_strands'); hc.add_curves([len(s) for s in strands])
    for i, v in enumerate(vv for s in strands for vv in s): hc.points[i].position = v
    r0 = 0.00012 if S['top'] < 0.035 else 0.00016
    for c in hc.curves:
        n = len(c.points)
        for j, pt in enumerate(c.points): pt.radius = r0 * (1 - 0.7 * j / max(1, n - 1))
    obj = bpy.data.objects.new(cid + '_strands', hc); bpy.context.scene.collection.objects.link(obj)
    hc.materials.append(hair_material(cid + '_hairmat'))
    def nodes(gname, **vals):   # 叠加一层程序化发丝节点，按名字设参数
        md = obj.modifiers.new(gname, 'NODES'); md.node_group = _node_group(gname)
        for item in md.node_group.interface.items_tree:
            if getattr(item, 'in_out', '') == 'INPUT' and item.name in vals: md[item.identifier] = vals[item.name]
    if S['clump'] > 0: nodes('Clump Hair Curves', **{'Existing Guide Map': False, 'Guide Distance': S['clump'], 'Factor': 0.8, 'Shape': 0.65,
                                  'Tip Spread': 0.0015, 'Preserve Length': True, 'Seed': seed})                 # 成缕、发梢收拢
    if S['curl'] > 0:
        nodes('Curl Hair Curves', **{'Existing Guide Map': False, 'Guide Distance': S['clump'], 'Radius': S['curl'], 'Frequency': 2.5,
                                     'Curl Start': 0.25, 'Random Offset': 0.5, 'Seed': seed})                   # 纹理烫
    nodes('Smooth Hair Curves', **{'Amount': 0.6, 'Iterations': 6, 'Weight': 0.5, 'Preserve Length': True})    # 理顺线条：干净利落
    hb_ = rig.pose.bones['head']
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = 'head'
    obj.matrix_parent_inverse = (rig.matrix_world @ hb_.matrix @ Matrix.Translation((0, hb_.length, 0))).inverted()
    # 4) 头皮底色层：覆盖区外移 0.8mm，深色带细纹（短发/寸头透出的发根阴影），边缘收进皮肤
    used = sorted({i for fi in cover for i in bp[fi]}); remap = {o: k for k, o in enumerate(used)}
    cm = bpy.data.meshes.new(cid + '_scalpcap'); cm.from_pydata([bv[i] for i in used], [], [[remap[i] for i in bp[fi]] for fi in cover]); cm.update()
    cbm = bmesh.new(); cbm.from_mesh(cm); cbm.normal_update()
    for v in cbm.verts:
        nn_ = v.normal if (v.co - H).dot(v.normal) > 0 else -v.normal
        v.co += nn_ * (-0.001 if v.is_boundary else 0.0008)
    cbm.to_mesh(cm); cbm.free()
    for poly in cm.polygons: poly.use_smooth = True
    cap = bpy.data.materials.new(cid + '_hair_cap'); cap.use_nodes = True; nt = cap.node_tree
    cb = nt.nodes['Principled BSDF']; cb.inputs['Roughness'].default_value = 0.65
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1200; nz.inputs['Detail'].default_value = 8
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    mx.inputs[6].default_value = (0.008, 0.006, 0.005, 1); mx.inputs[7].default_value = (0.05, 0.04, 0.035, 1)
    nt.links.new(nz.outputs['Fac'], mx.inputs['Factor']); nt.links.new(mx.outputs[2], cb.inputs['Base Color'])
    cm.materials.append(cap)
    capobj = bpy.data.objects.new(cid + '_scalpcap', cm); bpy.context.scene.collection.objects.link(capobj)
    capobj.parent = rig; capobj.parent_type = 'BONE'; capobj.parent_bone = 'head'
    capobj.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
    if shell is not None: shell.hide_render = True
    print('HAIR OK', cid, 'short-style', len(strands), 'strands', 'cap faces', len(cover), flush=True)
    return obj

def build(cid, rig, body, shell, style_name, seed=1):
    """返回发丝曲线物体；shell = 发片网格（作为发型轮廓，之后隐藏渲染）"""
    if cid in SHORT:   # 男式短发：按真实发型结构生成
        return build_short(cid, rig, body, shell, seed)
    st = STYLE.get(style_name, STYLE['short02']); rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    sb, sv, sp = _world_bvh(shell, dg)
    bb, bv, bp = _world_bvh(body, dg)
    head = (rig.matrix_world @ rig.pose.bones['head'].matrix).translation
    neck_z = (rig.matrix_world @ rig.pose.bones['neck02'].matrix).translation.z
    eye = (rig.matrix_world @ rig.pose.bones['eye.L'].head)
    brow_z = eye.z + 0.03
    fwd = Vector((0, -1, 0))   # 角色静止时面朝 -Y
    # 1) 头发覆盖区：从头皮每个面沿法线向外打射线，碰到发型轮廓即属于「被头发覆盖」（准确得到发际线以内的整片头皮）
    #    发片模型靠贴图透明做发丝空隙，几何上有洞，不能直接当发帽；所以发帽和发根都基于这片头皮区域
    tris, cover = [], []
    for fi, p in enumerate(bp):
        if len(p) < 3: continue
        a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        cen = sum((bv[i] for i in p), Vector()) / len(p)
        if cen.z < neck_z or (cen - head).length > 0.30: continue   # 头部骨骼起点在后脑下方，长脸的头顶会超过 17cm，放宽
        n = ((b_ - a).cross(c - a)).normalized()
        if (cen - head).dot(n) < 0: n = -n
        hit = sb.ray_cast(cen + n * 0.001, n, 0.09)[0]
        if hit is None:   # 轮廓贴着头皮（短发/寸头）时射线可能打不到：退而看最近距离
            loc_, _, _, d_ = sb.find_nearest(cen)
            if loc_ is None or d_ > 0.012: continue
        if (cen - head).dot(fwd) > 0.0 and cen.z < brow_z + 0.012: continue   # 额头前方、眉毛以上留出
        cover.append(fi)
    # 平滑覆盖区：补上被包围的空洞、去掉孤立碎块，发际线连续不锯齿
    vf = {}
    for fi, p in enumerate(bp):
        for i in p: vf.setdefault(i, set()).add(fi)
    nbr = lambda fi: {g for i in bp[fi] for g in vf[i]} - {fi}
    cov = set(cover)
    for _ in range(3):
        cand = {g for fi in cov for g in nbr(fi)} - cov
        cov |= {g for g in cand if len(nbr(g) & cov) >= 0.6 * len(nbr(g)) and
                not ((sum((bv[i] for i in bp[g]), Vector()) / len(bp[g]) - head).dot(fwd) > 0.0 and
                     (sum((bv[i] for i in bp[g]), Vector()) / len(bp[g])).z < brow_z + 0.012)}
    cov = {fi for fi in cov if len(nbr(fi) & cov) >= 3}
    cover = sorted(cov)
    for fi in cover:
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2))
        if len(p) == 4:
            d4 = bv[p[3]]; tris.append((a, c, d4, ((c - a).cross(d4 - a)).length / 2))
    ring = {g for fi in cover for g in nbr(fi)} - set(cover)   # 发际线外一圈：只种稀疏发根、不铺发帽，形成自然过渡
    for g in ring:
        cg = sum((bv[i] for i in bp[g]), Vector()) / len(bp[g])
        if cg.z < neck_z or ((cg - head).dot(fwd) > 0.0 and cg.z < brow_z + 0.012): continue
        p = bp[g]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2 * 0.35))
    if not tris: return None
    # 发帽：把覆盖区头皮复制出来、外移 1.5 毫米，做成无缝的深色头发底层
    used = sorted({i for fi in cover for i in bp[fi]}); remap = {o: k for k, o in enumerate(used)}
    cm = bpy.data.meshes.new(cid + '_scalpcap')
    cm.from_pydata([bv[i] for i in used], [], [[remap[i] for i in bp[fi]] for fi in cover]); cm.update()
    cbm = bmesh.new(); cbm.from_mesh(cm); cbm.normal_update()
    for v in cbm.verts:   # 整体外移 1.5mm；边缘一圈收进皮肤下，发际线不留硬边
        nn_ = v.normal if (v.co - head).dot(v.normal) > 0 else -v.normal
        v.co += nn_ * (-0.0015 if v.is_boundary else 0.0015)
    cbm.to_mesh(cm); cbm.free()
    capobj = bpy.data.objects.new(cid + '_scalpcap', cm); bpy.context.scene.collection.objects.link(capobj)
    for poly in cm.polygons: poly.use_smooth = True
    total = sum(t[3] for t in tris); acc = []; s = 0
    for t in tris: s += t[3]; acc.append(s)
    import bisect
    strands = []
    for _ in range(int(st['n'] * 2.2)):   # 加密：头发浓密、有厚度
        t = tris[min(len(tris) - 1, bisect.bisect_left(acc, rnd.random() * total))]
        u, v = rnd.random(), rnd.random()
        if u + v > 1: u, v = 1 - u, 1 - v
        root = t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v
        n = ((t[1] - t[0]).cross(t[2] - t[0])).normalized()
        if (root - head).dot(n) < 0: n = -n
        # 2) 生长：沿法线长出，受重力下垂，并吸附到发型轮廓上；离开轮廓即停
        L = st['L'] * rnd.uniform(0.75, 1.1); step = L / st['steps']; fringe = rnd.uniform(-0.004, 0.03)
        p = root + n * 0.001; d = n; pts = [p.copy()]
        for k in range(st['steps']):
            down = Vector((0, 0, -1)); away = (p - head); away.z = 0
            away = away.normalized() if away.length > 1e-6 else Vector()
            d = (d * (1 - st['droop'] * 0.35) + down * st['droop'] * 0.35 + away * 0.08).normalized()
            q = p + d * step
            loc, nn, i, dist = sb.find_nearest(q)
            if loc is None or dist > 0.035: break
            if k > 0: q = q.lerp(loc + (q - loc).normalized() * 0.004 if (q - loc).length > 1e-6 else loc, 0.8)   # 离开轮廓面 4mm，头发有蓬松厚度
            rel = q - head
            if rel.dot(fwd) > 0.03 and q.z < brow_z + fringe: break   # 刘海长到眉毛附近就停（长短错落），不遮眼睛
            hb, hdist = bb.find_nearest(q)[0], bb.find_nearest(q)[3]   # 不穿进头皮
            if hdist is not None and hdist < 0.002 and hb is not None: q = hb + (q - hb).normalized() * 0.002 if (q - hb).length > 1e-6 else q
            d = (q - p).normalized(); p = q; pts.append(p.copy())
        if len(pts) >= 3: strands.append(pts)
    # 3) 建发丝曲线
    hc = bpy.data.hair_curves.new(cid + '_strands')
    hc.add_curves([len(s) for s in strands])
    flat = [v for s in strands for v in s]
    for i, v in enumerate(flat): hc.points[i].position = v
    for c in hc.curves:   # 发根粗、发梢细
        pts = c.points; n = len(pts)
        for j, pt in enumerate(pts): pt.radius = 0.00015 * (1 - 0.75 * j / max(1, n - 1))
    obj = bpy.data.objects.new(cid + '_strands', hc); bpy.context.scene.collection.objects.link(obj)
    hc.materials.append(hair_material(cid + '_hairmat'))
    # 4) 程序化细节：轻微扰动 + 毛躁
    for gname, settings in (('Hair Curves Noise', {}),):
        try:
            md = obj.modifiers.new(gname, 'NODES'); md.node_group = _node_group(gname)
            for item in md.node_group.interface.items_tree:
                if getattr(item, 'in_out', '') != 'INPUT': continue
                nm = item.name.lower()
                if 'factor' in nm or 'strength' in nm or 'distance' in nm: md[item.identifier] = 0.0007
        except Exception as e:
            print('HAIR NODE WARN', gname, e)
    # 5) 挂到头部骨骼（世界位置保持不变）
    hb_ = rig.pose.bones['head']
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = 'head'
    obj.matrix_parent_inverse = (rig.matrix_world @ hb_.matrix @ Matrix.Translation((0, hb_.length, 0))).inverted()
    # 发帽材质：接近发色的深色哑光，带细微明暗起伏（像浓密发根的阴影），发丝覆盖其上
    cap = bpy.data.materials.new(cid + '_hair_cap'); cap.use_nodes = True; nt = cap.node_tree
    cb = nt.nodes['Principled BSDF']; cb.inputs['Roughness'].default_value = 0.6
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 6
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    mx.inputs[6].default_value = (0.006, 0.005, 0.004, 1); mx.inputs[7].default_value = (0.025, 0.02, 0.016, 1)
    nt.links.new(nz.outputs['Fac'], mx.inputs['Factor']); nt.links.new(mx.outputs[2], cb.inputs['Base Color'])
    cm.materials.append(cap)
    capobj.parent = rig; capobj.parent_type = 'BONE'; capobj.parent_bone = 'head'
    capobj.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
    shell.hide_render = True    # 原发片只用来定义发型轮廓，不参与渲染（避免硬边和透明空洞）
    print('HAIR OK', cid, style_name, len(strands), 'strands', 'cap faces', len(cover), flush=True)
    return obj
