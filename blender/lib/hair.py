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
         'bob01': dict(L=0.22, steps=16, droop=0.75, n=26000), 'ponytail01': dict(L=0.36, steps=22, droop=0.8, n=26000)}

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
    h.inputs['Roughness'].default_value = 0.32; h.inputs['Radial Roughness'].default_value = 0.35; h.inputs['Coat'].default_value = 0.1
    h.inputs['Random Roughness'].default_value = 0.2
    nt.links.new(h.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m

def build(cid, rig, body, shell, style_name, seed=1):
    """返回发丝曲线物体；shell = 发片网格（作为发型轮廓，之后隐藏渲染）"""
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
