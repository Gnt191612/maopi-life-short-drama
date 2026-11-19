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
         'bob01': dict(L=0.22, steps=16, droop=0.75, n=26000),
         'ponytail01': dict(L=0.36, steps=22, droop=0.8, n=55000, smooth=True, fringe=True),      # 刘海末端加大错落、侧面不发炸毛
         'wavybob': dict(L=0.20, steps=18, droop=0.55, n=30000, shrink=0.88, smooth=True)}       # 林母：轮廓往头部收 12%，不再蓬成一团

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
 # vol：发层厚度（米），发丝在「贴头皮」与「头皮外 vol」之间分层分布——原先所有发丝挤在 6mm 薄壳里，又扁又像头盔
 'lin':    dict(top=0.110, front=0.092, side=0.060, back=0.058, lift=0.42, messy=0.08, part=None, fringe='down', n=150000, clump=0, curl=0.0, vol=0.020),  # 韩式碎盖
 'chen':   dict(top=0.100, front=0.096, side=0.042, back=0.042, lift=0.38, messy=0.03, part='L', fringe='side', n=145000, clump=0, curl=0.0, vol=0.018),  # 韩式偏分
 'zhou':   dict(top=0.036, front=0.032, side=0.017, back=0.017, lift=0.50, messy=0.03, part=None, fringe='up', n=155000, clump=0, curl=0.0, vol=0.008),   # 利落板寸
 'wang':   dict(top=0.066, front=0.062, side=0.024, back=0.024, lift=0.28, messy=0.02, part='R', fringe='side', n=130000, melanin=0.80, clump=0, curl=0.0, vol=0.012),  # 偏短侧分
 'classA': dict(top=0.072, front=0.062, side=0.027, back=0.029, lift=0.46, messy=0.05, part=None, fringe='up', n=155000, clump=0, curl=0.0, vol=0.016),  # 上翘短发
}

def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)

def _head_frame(rig):
    """头部参照系：两眼中点、颅骨中心 H（两眼中点后方约 8.5cm）、眉高；静止时面朝 -Y"""
    pb = rig.pose.bones; MW = rig.matrix_world
    eyes = (MW @ pb['eye.L'].head + MW @ pb['eye.R'].head) / 2
    return eyes, eyes + Vector((0, 0.085, 0.015)), eyes.z + 0.03

def _hairline_fn(eyes, brow_z, rnd, front=0.045, temple=0.016, ear=-0.012, behind=-0.035, nape=-0.098):
    """发际线高度（按方位角，0=正前方，90=侧面，180=正后方），叠加平滑起伏——真人发际线不是一条直线。
    参数：前额/太阳穴相对眉高，两鬓/耳后/后颈相对眼睛高度（米）"""
    s1, s2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
    F, T, E, B, N = brow_z + front, brow_z + temple, eyes.z + ear, eyes.z + behind, eyes.z + nape
    def base(a):
        if a < 35: return F
        if a < 65: return F + (T - F) * _smooth(35, 65, a)
        if a < 100: return T + (E - T) * _smooth(65, 95, a)
        if a < 130: return E + (B - E) * _smooth(100, 130, a)
        return B + (N - B) * _smooth(130, 170, a)
    return lambda az: base(abs(az)) + 0.004 * math.sin(math.radians(az) * 7 + s1) + 0.0022 * math.sin(math.radians(az) * 17 + s2)

def _scalp(bv, bp, H, hairline_z, soft=0.016, front_boost=1.0):
    """发际线以上、朝外的头皮面 → 发根三角形（主区 + 发际线过渡带，过渡带越往外越稀）与发帽面。
    front_boost：前额发际线后 3cm 内发根加密倍数（梳背头时这圈最容易透出头皮）"""
    main, ring, boost = [], [], {}
    for fi, p in enumerate(bp):
        if len(p) < 3: continue
        c = sum((bv[i] for i in p), Vector()) / len(p); rel = c - H
        if rel.length > 0.17: continue
        n = ((bv[p[1]] - bv[p[0]]).cross(bv[p[2]] - bv[p[0]])).normalized()
        if n.dot(rel) < 0: n = -n
        if n.dot(rel.normalized()) < 0.2: continue
        az = math.degrees(math.atan2(rel.x, -rel.y)); hz = hairline_z(az)
        if c.z < hz - soft: continue
        if c.z < hz: ring.append((fi, (c.z - (hz - soft)) / soft))
        else: main.append(fi); boost[fi] = front_boost if abs(az) < 70 and c.z < hz + 0.03 else 1.0
    tris = []
    def add(fi, w):
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2 * w))
        if len(p) == 4: d4 = bv[p[3]]; tris.append((a, c, d4, ((c - a).cross(d4 - a)).length / 2 * w))
    for fi in main: add(fi, boost[fi])
    n_main = len(tris)
    for fi, w in ring: add(fi, 0.4 * w * w)
    return tris, n_main, main

def _sampler(tris, rnd):
    import bisect
    acc, s_ = [], 0
    for t in tris: s_ += t[3]; acc.append(s_)
    def sample():
        ti = min(len(tris) - 1, bisect.bisect_left(acc, rnd.random() * s_)); t = tris[ti]
        u, v = rnd.random(), rnd.random()
        if u + v > 1: u, v = 1 - u, 1 - v
        return ti, t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v, ((t[1] - t[0]).cross(t[2] - t[0])).normalized()
    return sample

def _scalp_cap(cid, bv, bp, faces, H, rig, parent_inverse, rgb=((0.010, 0.007, 0.005), (0.022, 0.015, 0.010))):
    """深色头皮底层：覆盖区头皮外移 1mm、边缘收进皮肤，发丝缝隙里透出的是发根阴影而不是白头皮"""
    used = sorted({i for fi in faces for i in bp[fi]}); remap = {o: k for k, o in enumerate(used)}
    cm = bpy.data.meshes.new(cid + '_scalpcap'); cm.from_pydata([bv[i] for i in used], [], [[remap[i] for i in bp[fi]] for fi in faces]); cm.update()
    cbm = bmesh.new(); cbm.from_mesh(cm); cbm.normal_update()
    for v in cbm.verts:
        nn_ = v.normal if (v.co - H).dot(v.normal) > 0 else -v.normal
        v.co += nn_ * (-0.001 if v.is_boundary else 0.001)
    cbm.to_mesh(cm); cbm.free()
    for poly in cm.polygons: poly.use_smooth = True
    cap = bpy.data.materials.new(cid + '_hair_cap'); cap.use_nodes = True; nt = cap.node_tree
    cb = nt.nodes['Principled BSDF']; cb.inputs['Roughness'].default_value = 1.0   # 纯哑光、无高光：头顶朝天的面在亮环境里会反出一层灰白，像秃顶
    if 'Specular IOR Level' in cb.inputs: cb.inputs['Specular IOR Level'].default_value = 0.0
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 6
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = (*rgb[0], 1); mx.inputs[7].default_value = (*rgb[1], 1)
    nt.links.new(nz.outputs['Fac'], mx.inputs['Factor']); nt.links.new(mx.outputs[2], cb.inputs['Base Color']); cm.materials.append(cap)
    capobj = bpy.data.objects.new(cid + '_scalpcap', cm); bpy.context.scene.collection.objects.link(capobj)
    capobj.parent = rig; capobj.parent_type = 'BONE'; capobj.parent_bone = 'head'; capobj.matrix_parent_inverse = parent_inverse.copy()
    return capobj

def _curves_object(cid, strands, radius, rig, melanin=0.97, soft_flag=None):
    """发丝点列 → 头发曲线物体（发根粗发梢细），挂到头部骨骼"""
    hc = bpy.data.hair_curves.new(cid + '_strands'); hc.add_curves([len(s) for s in strands])
    for i, v in enumerate(vv for s in strands for vv in s): hc.points[i].position = v
    for k, c in enumerate(hc.curves):
        n = len(c.points); r_ = radius * (0.45 if soft_flag and soft_flag[k] else 1.0)
        for j, pt in enumerate(c.points): pt.radius = r_ * (1 - 0.7 * j / max(1, n - 1))
    obj = bpy.data.objects.new(cid + '_strands', hc); bpy.context.scene.collection.objects.link(obj)
    hc.materials.append(hair_material(cid + '_hairmat', melanin))
    hb_ = rig.pose.bones['head']
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = 'head'
    obj.matrix_parent_inverse = (rig.matrix_world @ hb_.matrix @ Matrix.Translation((0, hb_.length, 0))).inverted()
    return obj

def _hair_nodes(obj, gname, **vals):
    """叠加一层 Blender 自带的程序化发丝节点，按名字设参数"""
    md = obj.modifiers.new(gname, 'NODES'); md.node_group = _node_group(gname)
    for item in md.node_group.interface.items_tree:
        if getattr(item, 'in_out', '') == 'INPUT' and item.name in vals: md[item.identifier] = vals[item.name]

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

    s1, s2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
    def hairline_z(az):
        """发际线高度（按方位角，0=正前方，90=侧面，180=正后方）；叠加平滑起伏，真人发际线不是一条直线"""
        return _hairline(az) + 0.004 * math.sin(math.radians(az) * 7 + s1) + 0.0022 * math.sin(math.radians(az) * 17 + s2)

    def _hairline(az):
        a = abs(az)
        front = brow_z + 0.045          # 前额发际线：眉上约 4.5cm
        temple = brow_z + 0.016         # 太阳穴略后收
        ear = eyes.z - 0.012            # 两鬓：绕过耳朵上缘，带一点鬓角
        behind = eyes.z - 0.030         # 耳后
        nape = eyes.z - 0.062           # 后颈发际线（原 -0.098：后颈推短后，下面那截深色发帽露出来像一块黑胶布）
        if a < 35: return front
        if a < 65: return front + (temple - front) * _smooth(35, 65, a)
        if a < 100: return temple + (ear - temple) * _smooth(65, 95, a)
        if a < 130: return ear + (behind - ear) * _smooth(100, 130, a)
        return behind + (nape - behind) * _smooth(130, 170, a)

    def side_of(c):
        """0~1：这个点有多「靠两鬓、耳朵上方」（侧面、低于头顶）。那一圈真实头发是服帖贴着头皮的"""
        rel = c - H; a = abs(math.degrees(math.atan2(rel.x, -rel.y)))
        sidew = _smooth(50, 78, a) * (1 - _smooth(125, 160, a))
        low = 1 - _smooth(eyes.z + 0.04, H.z + 0.06, c.z)
        return sidew * low

    def region_len(c):
        """按部位插值长度：头顶长、两侧后脑短"""
        rel = c - H; az = math.degrees(math.atan2(rel.x, -rel.y))
        height = _smooth(eyes.z + 0.02, H.z + 0.07, c.z)                # 0 两侧下部 → 1 头顶
        frontness = _smooth(-0.02, 0.06, -rel.y)                         # 越靠前越像刘海
        side_back = S['back'] if abs(az) > 110 else S['side']
        L = side_back + (S['top'] - side_back) * height
        return L + (S['front'] - L) * frontness * height, az, height

    # 1) 头皮覆盖区（发际线以上、朝外的头部表面）
    cover, soft_faces, cap_faces, soft_w = [], [], [], {}
    SOFT = 0.016                                                             # 发际线过渡带 1.6cm：越往外越稀
    for fi, p in enumerate(bp):
        if len(p) < 3: continue
        c = sum((bv[i] for i in p), Vector()) / len(p); rel = c - H
        if rel.length > 0.17: continue
        n = ((bv[p[1]] - bv[p[0]]).cross(bv[p[2]] - bv[p[0]])).normalized()
        if n.dot(rel) < 0: n = -n
        if n.dot(rel.normalized()) < 0.2: continue
        az = math.degrees(math.atan2(rel.x, -rel.y))
        hz = hairline_z(az)
        if c.z < hz - SOFT: continue
        if c.z < hz:                                                          # 过渡区：密度从发际线往外线性减到 0（不铺底色）
            soft_faces.append(fi); soft_w[fi] = (c.z - (hz - SOFT)) / SOFT; continue
        cover.append(fi)
        if c.z > hz + 0.008 * (1 - 0.7 * side_of(c)): cap_faces.append(fi)    # 深色发帽缩进发际线 8mm（两鬓只缩 2~3mm，耳朵上方不露出空隙）
    if not cover: return None
    tris = []
    for fi in cover:
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2))
        if len(p) == 4: d4 = bv[p[3]]; tris.append((a, c, d4, ((c - a).cross(d4 - a)).length / 2))
    n_main = len(tris)
    for fi in soft_faces:
        p = bp[fi]; a, b_, c = bv[p[0]], bv[p[1]], bv[p[2]]
        tris.append((a, b_, c, ((b_ - a).cross(c - a)).length / 2 * 0.4 * soft_w[fi] ** 2))
    import bisect
    total = sum(t[3] for t in tris); acc = []; s_ = 0
    for t in tris: s_ += t[3]; acc.append(s_)

    def clump_noise(root, k):
        """相邻发丝共享的扰动（按 1.2cm 网格取种子）→ 自然成缕"""
        key = (round(root.x / 0.012), round(root.y / 0.012), round(root.z / 0.012), k)
        r = random.Random(hash(key) & 0xffffffff)
        return Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)))

    strands, soft_flag = [], []
    for _ in range(S['n']):
        ti = min(len(tris) - 1, bisect.bisect_left(acc, rnd.random() * total)); t = tris[ti]; soft = ti >= n_main
        u, v = rnd.random(), rnd.random()
        if u + v > 1: u, v = 1 - u, 1 - v
        root = t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v
        nrm = ((t[1] - t[0]).cross(t[2] - t[0])).normalized()
        if nrm.dot(root - H) < 0: nrm = -nrm
        L, az, height = region_len(root); L *= rnd.uniform(0.8, 1.15)
        if abs(az) > 88:                                                             # 耳后、后颈推短：越靠下越短（原先后脑的长发越过后脑勺悬空垂下，翘出一撮）
            L *= 0.3 + 0.7 * _smooth(eyes.z - 0.06, eyes.z + 0.03, root.z)
        if soft: L *= rnd.uniform(0.25, 0.6)                                        # 发际线过渡区：短、细、贴着头皮
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
        lift = S['lift'] * (0.15 + 0.85 * _smooth(0.025, 0.07, (root - whorl).length)) * (0.25 + 0.75 * height)   # 两侧后脑贴头型，不外翘；发旋附近顺着发流平躺
        if soft: lift *= 0.3                                                         # 发际线的细发顺着头皮趴着
        lift *= 1 - 0.85 * side_of(root)                                             # 两鬓、耳朵上方：头发服帖地贴着头皮，不翘不鼓
        d = (nrm * lift + flow * (1 - lift)).normalized()
        p = root + nrm * 0.0008; pts = [p.copy()]
        lf = rnd.random() ** 0.7                                                     # 这根发丝在发层里的位置（0 贴头皮 ~ 1 最外层）
        for k in range(n_steps):
            g = 0.25 if S['fringe'] == 'down' and -rel.y > 0.0 else (0.08 + 0.25 * (1 - height))   # 重力：刘海、两侧往下顺
            jitter = clump_noise(root, k // 3) * S['messy'] * 0.6 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * S['messy'] * 0.25
            d = (d * 0.65 + flow * 0.35 * (1 - S['lift'] * 0.5) - up * g + jitter * 0.4).normalized()
            if S['fringe'] == 'comma' and -rel.y > 0.03 and k > n_steps * 0.55:   # 逗号刘海：发梢向内勾成 C 形
                d = (d - (q_dir := (root - H).normalized()) * 0.45 - up * 0.25).normalized()
            q = p + d * step
            loc, nn, _, dist = bb.find_nearest(q)                               # 保持在头皮外：离开距离随长度增加 → 体积
            sf = side_of(q)                                                       # 越靠两鬓/耳朵上方，越贴头皮（那里不该有空隙）
            grow = (k + 1) / n_steps
            min_off = (0.0015 + grow * (0.004 + S['lift'] * 0.006)) * (1 - 0.7 * sf)                # 发根贴头皮
            layer = S['vol'] * lf * min(1.0, grow * 2.5) * (1 - 0.6 * sf)                            # 分层：外层发丝离头皮更远 → 蓬松有厚度（两鬓仍服帖）
            min_off += layer * 0.7
            max_off = min_off + 0.004 + layer * 0.3 + (0.004 if S['fringe'] == 'down' and -(q - H).y > 0.03 else 0.0)   # 上限：不游离出去（刘海可稍离开额头）
            if loc is not None and (dist < min_off or dist > max_off):
                out = (q - loc).normalized() if (q - loc).length > 1e-7 else nn
                if out.dot(q - H) < 0: out = -out
                q = loc + out * (min_off if dist < min_off else max_off)
            relq = q - H
            if relq.dot(fwd) > 0.035 and q.z < brow_z + fstop: break              # 刘海长短错落、不遮眼睛
            azq = math.degrees(math.atan2(relq.x, -relq.y))
            if abs(azq) > 88 and q.z < hairline_z(azq) - 0.010: break
            if abs(azq) > 60 and q.z < eyes.z - 0.04: break                       # 两侧头发不长过耳垂（否则被耳朵挤到耳后，垂下一片）              # 后颈、耳后：长过发际线 1cm 就停（原先顺着脖子往下长，翘出一撮「小尾巴」）
            d = (q - p).normalized(); p = q; pts.append(p.copy())
        if len(pts) >= 2: strands.append(pts); soft_flag.append(soft)
    # 3) 曲线 + 材质
    hc = bpy.data.hair_curves.new(cid + '_strands'); hc.add_curves([len(s) for s in strands])
    for i, v in enumerate(vv for s in strands for vv in s): hc.points[i].position = v
    r0 = 0.00012 if S['top'] < 0.035 else 0.00016
    for c, sf in zip(hc.curves, soft_flag):
        n = len(c.points); r_ = r0 * (0.45 if sf else 1.0)               # 发际线的细软绒发更细，远看是渐变而不是一排刺
        for j, pt in enumerate(c.points): pt.radius = r_ * (1 - 0.7 * j / max(1, n - 1))
    obj = bpy.data.objects.new(cid + '_strands', hc); bpy.context.scene.collection.objects.link(obj)
    hc.materials.append(hair_material(cid + '_hairmat', S.get('melanin', 0.97)))   # 王老师：鬓角花白（黑色素低一点）
    def nodes(gname, **vals):   # 叠加一层程序化发丝节点，按名字设参数
        md = obj.modifiers.new(gname, 'NODES'); md.node_group = _node_group(gname)
        for item in md.node_group.interface.items_tree:
            if getattr(item, 'in_out', '') == 'INPUT' and item.name in vals: md[item.identifier] = vals[item.name]
    if S['clump'] > 0: nodes('Clump Hair Curves', **{'Existing Guide Map': False, 'Guide Distance': S['clump'], 'Factor': 0.8, 'Shape': 0.65,
                                  'Tip Spread': 0.0015, 'Preserve Length': True, 'Seed': seed})                 # 成缕、发梢收拢
    if S['curl'] > 0:
        nodes('Curl Hair Curves', **{'Existing Guide Map': False, 'Guide Distance': S['clump'], 'Radius': S['curl'], 'Frequency': 2.5,
                                     'Curl Start': 0.25, 'Random Offset': 0.5, 'Seed': seed})                   # 纹理烫
    nodes('Smooth Hair Curves', **{'Amount': 0.7, 'Iterations': 8, 'Weight': 0.5, 'Preserve Length': True})    # 理顺线条：顺着头型、干净利落
    hb_ = rig.pose.bones['head']
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = 'head'
    obj.matrix_parent_inverse = (rig.matrix_world @ hb_.matrix @ Matrix.Translation((0, hb_.length, 0))).inverted()
    # 4) 头皮底色层：覆盖区外移 0.8mm，深色带细纹（短发/寸头透出的发根阴影），边缘收进皮肤
    used = sorted({i for fi in cap_faces for i in bp[fi]}); remap = {o: k for k, o in enumerate(used)}
    cm = bpy.data.meshes.new(cid + '_scalpcap'); cm.from_pydata([bv[i] for i in used], [], [[remap[i] for i in bp[fi]] for fi in cap_faces]); cm.update()
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
    if S['top'] < 0.04:   # 寸头：头皮透过短发看得见——发帽是发根深色与肤色的混合，不是一顶黑头盔
        mx.inputs[6].default_value = (0.02, 0.015, 0.012, 1); mx.inputs[7].default_value = (0.20, 0.14, 0.11, 1)
    else:
        mx.inputs[6].default_value = (0.008, 0.006, 0.005, 1); mx.inputs[7].default_value = (0.05, 0.04, 0.035, 1)
    nt.links.new(nz.outputs['Fac'], mx.inputs['Factor']); nt.links.new(mx.outputs[2], cb.inputs['Base Color'])
    cm.materials.append(cap)
    capobj = bpy.data.objects.new(cid + '_scalpcap', cm); bpy.context.scene.collection.objects.link(capobj)
    capobj.parent = rig; capobj.parent_type = 'BONE'; capobj.parent_bone = 'head'
    capobj.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
    if shell is not None: shell.hide_render = True
    print('HAIR OK', cid, 'short-style', len(strands), 'strands', 'cap faces', len(cover), flush=True)
    return obj

# ---------------- 女式长发：按发际线种满发根，按发型走向生长（不再依赖发片轮廓：轮廓盖不到的耳周、后脑会秃） ----------------
# ponytail 马尾：头发贴着头皮梳向扎发点，扎紧后垂下（sleek 头顶发层厚度，tail 马尾长）
# bob 披发（短发/长发通用）：从发旋向四周梳开，过了颅骨最宽处自然下垂到发尾（L 最长、vol 蓬松厚度、hem 发尾高度相对眼睛、part 分缝、wave 微卷半径）
LONG = {
 # front/temple：前额、太阳穴发际线相对眉高（米，建模时未缩放的头：头顶在眼睛上方约 10cm，原先 4.5cm 的前额发际线几乎到头顶）
 # 参照真人马尾：头顶圆润有发量（sleek 1.4cm），扎发点在后脑勺约耳朵上缘高度（tie_up），马尾粗（tail_r）、长到背中部、顺着后背垂下
 'classB': dict(style='ponytail', n=110000, sleek=0.014, tail=0.36, tail_r=0.034, tie_up=-0.05, front=0.018, temple=0.0, ear=-0.018, behind=-0.045, radius=0.0002,
                headband=(0.012, 0.012, 0.014)),   # 低马尾 + 黑色发箍（照用户选定的标准长相）
 # 林母：及胸披发（建模时未缩放：发尾在眼睛下方 27cm ≈ 成人 30cm，到胸口）；tuck 发尾内扣程度
 'mom':    dict(style='bob', n=95000, L=0.46, vol=0.020, hem=-0.27, tuck=0.15, part='L', wave=0.0, melanin=0.85, front=0.022, temple=0.002),   # 卷发节点会把发丝拧成扁带，先不用
}

def build_long(cid, rig, body, shell, seed=1):
    S = LONG[cid]; rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    bb, bv, bp = _world_bvh(body, dg)
    eyes, H, brow_z = _head_frame(rig)
    up = Vector((0, 0, 1))
    tris, n_main, cap_faces = _scalp(bv, bp, H, _hairline_fn(eyes, brow_z, rnd, front=S['front'], temple=S['temple'],
                                                                      ear=S.get('ear', -0.012), behind=S.get('behind', -0.035)),
                                     soft=0.007, front_boost=2.5 if S['style'] == 'ponytail' else 1.0)   # 过渡带收窄：梳起来的头发会露出整条发际线，宽的稀疏带看着像秃了一圈
    if not tris: return None
    sample = _sampler(tris, rnd)

    axis_y = H.y - 0.03                                                 # 脖子、后背的中轴（竖线）

    def clamp_off(q, lo, hi):
        """把点放到离皮肤 lo~hi 的范围里（在皮肤里面就推出来）。
        里外按「离头部中心/身体中轴更远的一侧是外面」判断——网格法线朝向不可靠（实测有朝里的，发丝被塞进头里）"""
        loc, nn, _, d = bb.find_nearest(q)
        if loc is None: return q
        C = H if loc.z > eyes.z - 0.03 else Vector((H.x, axis_y, loc.z))
        out = loc - C; out = out.normalized() if out.length > 1e-7 else Vector((0, 1, 0))
        if nn is not None and nn.length > 0.5: out = nn if nn.dot(out) > 0 else -nn
        v = q - loc; inside = v.dot(out) < 0
        if inside or d < lo: return loc + out * lo
        return loc + v.normalized() * hi if d > hi else q

    def lock(key):   # 相邻发丝共享的扰动 → 自然成缕
        r = random.Random(hash(key) & 0xffffffff); return Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)))

    strands, soft_flag, tie = [], [], None
    if S['style'] == 'ponytail':
        dirT = Vector((0, 1.0, S['tie_up'])).normalized()          # 扎发点：后脑勺偏上
        hit = bb.ray_cast(H, dirT, 0.3)[0]
        T = (hit if hit is not None else H + dirT * 0.10) + dirT * (S['sleek'] + 0.008)
        axis0 = Vector((0, 0.3, -1)).normalized(); u_ = Vector((1, 0, 0)); v_ = axis0.cross(u_).normalized()
        for _ in range(S['n']):
            ti, root, nrm = sample(); soft = ti >= n_main
            if nrm.dot(root - H) < 0: nrm = -nrm
            lf = rnd.random() ** 0.7                                   # 在发层厚度里的位置：有的贴头皮，有的在外层
            # 1) 梳向扎发点：从颅骨中心看，发丝方向从「发根方向」平滑转到「扎发点方向」（像经线汇向一点），
            #    每一步从颅骨中心沿该方向打射线找到头皮，再往外放发层厚度——路径连续顺滑。
            #    （原先逐步贴头皮修正，在低精度头模上走成锯齿，头顶轮廓一圈毛刺、逆光发白）
            a0 = (root - H).normalized(); a1 = (T - H).normalized()
            ang = math.acos(max(-1.0, min(1.0, a0.dot(a1)))); nst = max(3, int(ang / 0.06))
            pts = [root + nrm * 0.0008]
            for k in range(1, nst + 1):
                t = k / nst
                dvec = a0.slerp(a1, t) if ang > 1e-3 else a1
                hit = bb.ray_cast(H, dvec, 0.3)[0]
                if hit is None: break
                crown = 0.35 + 0.65 * _smooth(eyes.z - 0.01, H.z + 0.06, hit.z)   # 发层：头顶最厚（圆润），两鬓、后颈服帖
                off = 0.0012 + S['sleek'] * lf * crown * _smooth(0.0, 0.25, t)
                pts.append(hit + dvec * off)
                if (pts[-1] - T).length < 0.02: break
            pts.append(T + (pts[-1] - T) * 0.35)                        # 收进发圈
            p = pts[-1]
            if soft: pts = pts[:max(3, len(pts) // 2)]                   # 发际线外圈的细软绒发：短一截，顺着往后
            else:                                                       # 2) 扎紧后垂下：保持它在马尾截面里的方位，先紧后蓬、末端收尖
                th = rnd.uniform(0, 2 * math.pi); rho = rnd.random() ** 0.5            # 在马尾圆截面里均匀分布（原先只占半边，成了扁带）
                Lt = S['tail'] * rnd.uniform(0.7, 1.08); nseg = max(4, int(Lt / 0.018)); ph = rnd.uniform(0, 6.28)
                lk = lock(('pt', int(th * 5), int(rho * 3)))
                for j in range(1, nseg + 1):
                    t = j * Lt / nseg
                    c = T + Vector((0, 0.035 * _smooth(0, 0.08, t) + 0.02 * t, -0.97 * t))   # 出了发圈稍往后，随即顺着后背垂下
                    R = 0.007 + S['tail_r'] * _smooth(0.0, 0.07, t) - S['tail_r'] * 0.55 * _smooth(0.12, S['tail'], t)
                    q = c + (u_ * math.cos(th) + v_ * math.sin(th)) * rho * R + lk * 0.006 * _smooth(0.05, 0.25, t) \
                        + Vector((math.sin(t * 18 + ph), 0, 0)) * 0.0015
                    loc, _, _, _ = bb.find_nearest(q)                         # 靠到后背时只往后让开（原先沿径向推开，马尾在背上分成两股）
                    if loc is not None and q.y < loc.y + 0.006 and abs(q.z - loc.z) < 0.03: q.y = loc.y + 0.006
                    pts.append(q)
            strands.append(pts); soft_flag.append(soft)
        tie = (T, axis0)
    else:   # bob
        part_x = {'L': 0.03, 'R': -0.03}.get(S.get('part'))
        whorl = H + Vector((0, 0.05, 0.085)); hem = eyes.z + S['hem']
        shoulder_z = (rig.matrix_world @ rig.pose.bones['neck01'].head).z                  # 脖子根 ≈ 肩膀高度
        torso_y = (rig.matrix_world @ rig.pose.bones['spine01'].head).y                    # 上身前后中心
        for _ in range(S['n']):
            ti, root, nrm = sample(); soft = ti >= n_main
            if nrm.dot(root - H) < 0: nrm = -nrm
            rel = root - H; az = abs(math.degrees(math.atan2(rel.x, -rel.y)))
            if part_x is not None and az < 70:                           # 分缝：前额头发梳向两侧、往后带过太阳穴（大边越过头顶），不垂到脸上
                sx = 1.0 if root.x > part_x else -1.0
                flow = Vector((sx, 0.55, -0.15))
            else:
                flow = root - whorl; flow.z = min(flow.z, 0.0) - 0.02
            lf = rnd.random() ** 0.6; L = S['L'] * rnd.uniform(0.85, 1.1) * (0.35 if soft else 1.0)
            lk = lock(('bob', round(root.x / 0.015), round(root.y / 0.015), round(root.z / 0.015)))
            hem_i = hem + rnd.uniform(-0.008, 0.008) + lk.z * 0.006
            behind = root.y > eyes.y + 0.075
            p = root + nrm * 0.0008; d = (nrm * 0.5 + flow.normalized()).normalized(); pts = [p.copy()]; s = 0.0
            while s < L and len(pts) < 60:
                on_head = p.z > eyes.z + 0.015
                loc, nn, _, _ = bb.find_nearest(p)
                f = flow.normalized()
                if on_head and nn is not None: f = (f - nn * f.dot(nn)).normalized()         # 头顶：顺着头型梳
                g = 0.10 if on_head else 0.55                                                  # 过了颅骨最宽处：重力为主，自然垂下
                d = (d * 0.55 + f * 0.40 * (1.0 if on_head else 0.3) - up * g + lk * 0.05).normalized()
                if p.z < shoulder_z + 0.04:   # 到了肩膀：不再往两侧走，顺着往下垂（落在肩前/肩后由下面的位置约束决定）
                    d = Vector((d.x * 0.3, d.y * 0.3, d.z - 0.6)).normalized()
                if p.z < hem_i + 0.035:                                                         # 发尾微微内扣
                    inward = Vector((H.x - p.x, H.y - p.y, 0)); d = (d + inward.normalized() * S.get('tuck', 0.35)).normalized()
                q = p + d * 0.012; s += 0.012
                vol = S['vol'] * lf * _smooth(0.0, 0.05, s)
                q = clamp_off(q, 0.0015 + vol * 0.5, 0.002 + vol) if on_head else clamp_off(q, 0.006 + vol * 0.6, 9.0)
                if not on_head and q.y < eyes.y + 0.05 and abs(q.x - H.x) < 0.082:   # 垂在脸颊外侧，不挡脸
                    q.x = H.x + math.copysign(0.082, q.x - H.x)
                elif q.z < brow_z + 0.012 and q.y < eyes.y + 0.04 and abs(q.x - H.x) < 0.068:   # 刘海不过眉：扫向两侧
                    q.x = H.x + math.copysign(0.068, q.x - H.x)
                if q.z < shoulder_z + 0.03 and abs(q.x - H.x) < 0.24:       # 肩膀以下：明确落在肩膀后面（耳后的头发）或前面，不搭在肩头上横着支出去
                    w_ = _smooth(shoulder_z + 0.03, shoulder_z - 0.01, q.z)
                    if behind: q.y = max(q.y, q.y + (torso_y + 0.075 - q.y) * w_)
                    else: q.y = min(q.y, q.y + (torso_y - 0.10 - q.y) * w_)
                p = q; pts.append(p.copy())
                if p.z < hem_i: break
            if len(pts) >= 2: strands.append(pts); soft_flag.append(soft)
    obj = _curves_object(cid, strands, S.get('radius', 0.00015), rig, S.get('melanin', 0.97), soft_flag)
    if S.get('wave'): _hair_nodes(obj, 'Curl Hair Curves', **{'Existing Guide Map': False, 'Guide Distance': 0.01, 'Radius': S['wave'],
                                                           'Frequency': 1.6, 'Curl Start': 0.35, 'Random Offset': 0.5, 'Seed': seed})
    _hair_nodes(obj, 'Smooth Hair Curves', **{'Amount': 0.6, 'Iterations': 6, 'Weight': 0.5, 'Preserve Length': True})
    _scalp_cap(cid, bv, bp, cap_faces, H, rig, obj.matrix_parent_inverse)
    if tie is not None: _hair_tie(cid, rig, *tie)
    if S.get('headband'): _headband(cid, rig, bb, H, S['sleek'], S['headband'], obj.matrix_parent_inverse, eyes.z)
    if shell is not None: shell.hide_render = True; shell.hide_viewport = True
    print('HAIR OK', cid, S['style'], len(strands), 'strands', 'scalp faces', len(cap_faces), flush=True)
    return obj

def _headband(cid, rig, bb, H, sleek, rgb, parent_inverse, eyes_z, width=0.010):
    """发箍：从一侧耳上绕过头顶到另一侧耳上的窄带，压在头发表面（发际线后约 4cm），哑光深色。
    离头皮的距离跟发层厚度一致（头顶厚、两侧薄），不浮空"""
    pts = []
    for k in range(41):
        a = -1.40 + 2.80 * k / 40
        d = Vector((math.sin(a), -0.38 * math.cos(a), math.cos(a))).normalized()   # 头顶处略向前倾
        hit = bb.ray_cast(H, d, 0.3)[0]
        if hit is None: continue
        crown = 0.35 + 0.65 * _smooth(eyes_z - 0.01, H.z + 0.06, hit.z)
        pts.append((hit + d * (0.0012 + sleek * crown * 0.75 + 0.0015), d))
    if len(pts) < 4: return None
    bm2 = bmesh.new(); rows = []
    for i, (p, d) in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]).normalized()
        side = t.cross(d).normalized() * width / 2
        rows.append((bm2.verts.new(p + side), bm2.verts.new(p - side)))
    for (a0, b0), (a1, b1) in zip(rows, rows[1:]): bm2.faces.new((a0, b0, b1, a1))
    me = bpy.data.meshes.new(cid + '_headband'); bm2.to_mesh(me); bm2.free()
    for poly in me.polygons: poly.use_smooth = True
    m = bpy.data.materials.new(cid + '_headband'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = 0.9
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.15   # 哑光布面，不反灰光
    me.materials.append(m)
    ob = bpy.data.objects.new(cid + '_headband', me); bpy.context.scene.collection.objects.link(ob)
    s = ob.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.003; s.offset = 1.0
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = 'head'; ob.matrix_parent_inverse = parent_inverse.copy()
    return ob

def _hair_tie(cid, rig, T, axis):
    """发圈：深色布艺发圈套在扎发处"""
    bm2 = bmesh.new(); segs, ring, R, r = 24, 8, 0.013, 0.006
    vs = [[bm2.verts.new(((R + r * math.cos(b * 2 * math.pi / ring)) * math.cos(a * 2 * math.pi / segs),
                          (R + r * math.cos(b * 2 * math.pi / ring)) * math.sin(a * 2 * math.pi / segs), r * math.sin(b * 2 * math.pi / ring)))
           for b in range(ring)] for a in range(segs)]
    for a in range(segs):
        for b in range(ring): bm2.faces.new((vs[a][b], vs[(a + 1) % segs][b], vs[(a + 1) % segs][(b + 1) % ring], vs[a][(b + 1) % ring]))
    tm = bpy.data.meshes.new(cid + '_hairtie'); bm2.to_mesh(tm); bm2.free()
    for poly in tm.polygons: poly.use_smooth = True
    tmat = bpy.data.materials.new(cid + '_hairtie'); tmat.use_nodes = True
    tmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.06, 0.12, 1)
    tmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8; tm.materials.append(tmat)
    tob = bpy.data.objects.new(cid + '_hairtie', tm); bpy.context.scene.collection.objects.link(tob)
    tob.matrix_world = Matrix.LocRotScale(T + axis * 0.004, axis.to_track_quat('Z', 'Y'), None)
    bpy.context.view_layer.update()
    mw = tob.matrix_world.copy(); tob.parent = rig; tob.parent_type = 'BONE'; tob.parent_bone = 'head'; tob.matrix_world = mw

def build(cid, rig, body, shell, style_name, seed=1):
    """返回发丝曲线物体；shell = 发片网格（作为发型轮廓，之后隐藏渲染）"""
    if cid in SHORT:   # 男式短发：按真实发型结构生成
        return build_short(cid, rig, body, shell, seed)
    if cid in LONG:    # 女式长发：按发际线 + 发型走向生成
        return build_long(cid, rig, body, shell, seed)
    st = STYLE.get(style_name, STYLE['short02']); rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    sb, sv, sp = _world_bvh(shell, dg)
    bb, bv, bp = _world_bvh(body, dg)
    head = (rig.matrix_world @ rig.pose.bones['head'].matrix).translation
    if st.get('shrink'):   # 轮廓整体往头部中心收（头顶以上不动，避免压进头皮）
        hc_ = head + Vector((0, 0.01, 0.06))
        sv = [hc_ + (v - hc_) * st['shrink'] if (v - hc_).length * st['shrink'] > 0.09 else v for v in sv]
        sb = BVHTree.FromPolygons(sv, sp)
    neck_z = (rig.matrix_world @ rig.pose.bones['neck02'].matrix).translation.z
    eye = (rig.matrix_world @ rig.pose.bones['eye.L'].head)
    brow_z = eye.z + 0.03
    fwd = Vector((0, -1, 0))   # 角色静止时面朝 -Y
    def is_face_front(c):
        """是否属于「脸正面」（眉毛以下、眼睛更靠前）——这些地方不长发。
        用眼睛而非 head 作前后基准：head 骨骼点在耳后，若以它为界，耳朵/鬓角会被误判成脸而剃秃一圈。"""
        return c.y < eye.y + 0.005 and c.z < brow_z + 0.012
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
            if loc_ is None or d_ > 0.012:
                # 马尾/长发的发片常不延伸到耳周，射线打不到、距离也远，但真人耳周本就有头发。
                # 对「眼后 + 头部两侧 + 不太突出 + 法线不朝下」的头皮面兜底纳入，补掉耳周秃区；
                # 严格限制在眼后（排除脸颊/太阳穴）与 |x|<0.09（排除耳朵尖），不影响面部与耳朵。
                if not (cen.y > eye.y + 0.025 and abs(cen.x) > 0.045 and
                        eye.z - 0.055 < cen.z < eye.z + 0.10 and
                        (cen - head).length < 0.17 and n.z > -0.35):
                    continue
        if is_face_front(cen): continue   # 脸正面留出（眉毛以上、眼睛更前）；耳周不再被误剃
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
                not is_face_front(sum((bv[i] for i in bp[g]), Vector()) / len(bp[g]))}
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
        if cg.z < neck_z or is_face_front(cg): continue
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
        L = st['L'] * rnd.uniform(0.75, 1.1); step = L / st['steps']
        fringe = rnd.uniform(-0.004, 0.03) + (rnd.uniform(-0.02, 0.04) if st.get('fringe') else 0.0)   # 加大刘海末端错落：避免齐平锅盖边
        is_front = (root - head).dot(fwd) > 0.01                        # 前额刘海发根
        # 耳周/鬓角发根：这区域离发片轮廓远，强吸附会把发丝反复拽向远处发片、拧成放射状乱刺。
        # 单独标记，用弱吸附让发丝顺重力自然下垂贴住，避免鸟巢状交叉。
        is_ear = (abs(root.x) > 0.045 and eye.y + 0.005 < root.y < eye.y + 0.11 and
                  eye.z - 0.075 < root.z < eye.z + 0.095)
        p = root + n * 0.001; d = n; pts = [p.copy()]
        for k in range(st['steps']):
            down = Vector((0, 0, -1)); away = (p - head); away.z = 0
            away = away.normalized() if away.length > 1e-6 else Vector()
            # 侧面/耳周发丝不再水平外推——away*0.08 把鬓角发丝推成横向炸毛的细线
            side_out = 0.0 if (abs(root.x) > 0.045 or is_ear) else 0.08
            d = (d * (1 - st['droop'] * 0.35) + down * st['droop'] * 0.35 + away * side_out).normalized()
            q = p + d * step
            loc, nn, i, dist = sb.find_nearest(q)
            if loc is None or dist > 0.035: break
            # 前额刘海减弱对平发片轮廓的吸附（0.8→0.45），让末端随重力自然错落，不再齐平
            snap = 0.45 if is_front and (q - head).dot(fwd) > 0.01 else (0.5 if is_ear else 0.8)
            if k > 0: q = q.lerp(loc + (q - loc).normalized() * 0.004 if (q - loc).length > 1e-6 else loc, snap)
            rel = q - head
            if rel.dot(fwd) > 0.03 and q.z < brow_z + fringe: break    # 刘海到眉毛附近就停，末端长短错落
            hb, hdist = bb.find_nearest(q)[0], bb.find_nearest(q)[3]   # 不穿进头皮
            if hdist is not None and hdist < 0.002 and hb is not None: q = hb + (q - hb).normalized() * 0.002 if (q - hb).length > 1e-6 else q
            d = (q - p).normalized(); p = q; pts.append(p.copy())
        if len(pts) >= 3: strands.append(pts)
    tie = None
    if style_name.startswith('ponytail'):   # 马尾：找到扎发处，发丝在那里收拢成一束（扎口最紧，往下逐渐散开），再加一个发圈
        band = [v for v in sv if head.z + 0.03 < v.z < head.z + 0.14]
        if band:
            tip = max(band, key=lambda v: v.y)                              # 发型轮廓最靠后的点：马尾从这里伸出去
            tie = tip - Vector((0, 0.012, 0))
            tail = [v for v in sv if v.y > tie.y - 0.01 and v.z < tie.z - 0.02]
            axis = ((sum(tail, Vector()) / len(tail)) - tie).normalized() if tail else Vector((0, 0.3, -1)).normalized()
            for pts in strands:
                for i, p in enumerate(pts):
                    rel = p - tie; t = rel.dot(axis)
                    if t < -0.06: continue
                    radial = rel - axis * t
                    if t <= 0: f = 0.25 + 0.75 * min(1.0, radial.length / 0.06)   # 扎口前：往扎发点汇拢
                    else: f = 0.22 + 0.78 * min(1.0, t / 0.16)                    # 扎口后：先紧后松
                    pts[i] = tie + axis * t + radial * f
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
    if st.get('smooth'):
        md = obj.modifiers.new('Smooth Hair Curves', 'NODES'); md.node_group = _node_group('Smooth Hair Curves')
        for item in md.node_group.interface.items_tree:
            if getattr(item, 'in_out', '') == 'INPUT' and item.name in ('Amount', 'Iterations', 'Weight', 'Preserve Length'):
                md[item.identifier] = {'Amount': 0.5, 'Iterations': 5, 'Weight': 0.5, 'Preserve Length': True}[item.name]
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
    if tie is not None:   # 发圈：深色布艺发圈套在扎发处
        bm2 = bmesh.new(); segs, ring, R, r = 24, 8, 0.015, 0.0065
        vs = [[bm2.verts.new(((R + r * math.cos(b * 2 * math.pi / ring)) * math.cos(a * 2 * math.pi / segs),
                              (R + r * math.cos(b * 2 * math.pi / ring)) * math.sin(a * 2 * math.pi / segs), r * math.sin(b * 2 * math.pi / ring)))
               for b in range(ring)] for a in range(segs)]
        for a in range(segs):
            for b in range(ring): bm2.faces.new((vs[a][b], vs[(a + 1) % segs][b], vs[(a + 1) % segs][(b + 1) % ring], vs[a][(b + 1) % ring]))
        tm = bpy.data.meshes.new(cid + '_hairtie'); bm2.to_mesh(tm); bm2.free()
        for poly in tm.polygons: poly.use_smooth = True
        tmat = bpy.data.materials.new(cid + '_hairtie'); tmat.use_nodes = True
        tmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.06, 0.12, 1)
        tmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8; tm.materials.append(tmat)
        tob = bpy.data.objects.new(cid + '_hairtie', tm); bpy.context.scene.collection.objects.link(tob)
        tob.matrix_world = Matrix.LocRotScale(tie + axis * 0.010, axis.to_track_quat('Z', 'Y'), None)
        bpy.context.view_layer.update()
        mw = tob.matrix_world.copy(); tob.parent = rig; tob.parent_type = 'BONE'; tob.parent_bone = 'head'; tob.matrix_world = mw
    shell.hide_render = True    # 原发片只用来定义发型轮廓，不参与渲染（避免硬边和透明空洞）
    print('HAIR OK', cid, style_name, len(strands), 'strands', 'cap faces', len(cover), flush=True)
    return obj
