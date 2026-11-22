# -*- coding: utf-8 -*-
"""饰品：金色扇形耳环（林母，照用户 11-22 给的参考图）。
只戴在没被头发挡住的那只耳朵上：从两只耳垂往外、往前打射线，碰到头发少的一侧就是露出来的耳朵。
造型：耳垂上一颗金色小耳钉 + 下面挂一片半圆扇形金片（放射状细骨 + 外圈），扇面朝向侧面，挂在头部骨骼上。"""
import math
import bpy, bmesh
from mathutils import Vector as V, Matrix as Mx
from mathutils.bvhtree import BVHTree

EARRING = {'mom': dict(rgb=(1.0, 0.72, 0.30), radius=0.016, drop=0.024, ribs=9)}   # 耳垂被卷发盖住大半：吊坠加长到卷发下沿外

def _gold(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Metallic'].default_value = 1.0; b.inputs['Roughness'].default_value = 0.22
    return m

def _bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); me = ev.to_mesh()
    t = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); ev.to_mesh_clear()
    return t

def earring(cid, rig, body, hair_objs):
    S = EARRING[cid]; MW = body.matrix_world
    g = body.vertex_groups.get('ears')
    if g is None: print('EARRING skip: no ears group', flush=True); return
    # 用变形后的网格（身材形态键会移动耳朵；原始网格坐标偏高，耳环飘到头顶上）
    mods = [(m, m.show_viewport) for m in body.modifiers if m.type in ('MASK', 'SUBSURF')]
    for m, _ in mods: m.show_viewport = False
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me_ = ev.to_mesh()
    ids = [v.index for v in body.data.vertices if any(e.group == g.index and e.weight > 0.3 for e in v.groups)]
    ear = [MW @ me_.vertices[i].co for i in ids]; ev.to_mesh_clear()
    for m, s_ in mods: m.show_viewport = s_
    head = MW @ V((0, 0, 0)); hx = sum(p.x for p in ear) / len(ear)
    bv = [_bvh(o) for o in hair_objs if o is not None and o.type == 'MESH']
    best = None
    for side in (-1, 1):
        pts = [p for p in ear if (p.x - hx) * side > 0]
        if not pts: continue
        lobe = min(pts, key=lambda p: p.z + 0.3 * abs(p.y - sum(q.y for q in pts) / len(pts)))   # 最低、靠耳朵中间的点 = 耳垂
        hits = 0
        for d in (V((side, 0, 0)), V((side, -1, 0)).normalized(), V((side * 0.5, -1, 0)).normalized(), V((side, 0.5, 0)).normalized()):
            for t in bv:
                if t.ray_cast(lobe + d * 0.003, d, 0.25)[0] is not None: hits += 1
        print('EARRING side', side, 'lobe', tuple(round(c, 3) for c in lobe), 'hair hits', hits, flush=True)
        if best is None or hits < best[0]: best = (hits, side, lobe)
    if best is None: return
    _, side, lobe = best
    bm = bmesh.new(); r = S['radius']
    # 耳钉：小球
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.0022, matrix=Mx.Translation(lobe + V((side * 0.002, 0, 0))))
    # 扇面：在 y-z 平面（朝侧面），圆心在耳钉下方 drop，扇形朝下展开 180°
    c = lobe + V((side * 0.004, 0, -S['drop']))
    def P(a, rr): return c + V((0, math.cos(a) * rr, -math.sin(a) * rr))
    n = 24; th = 0.0012
    ring_o = [P(math.pi * i / n, r) for i in range(n + 1)]; ring_i = [P(math.pi * i / n, r * 0.82) for i in range(n + 1)]
    def slab(a_, b_, c_, d_):   # 有厚度的四边形片
        vs = [bm.verts.new(p + V((sx * th, 0, 0))) for sx in (-1, 1) for p in (a_, b_, c_, d_)]
        for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)): bm.faces.new([vs[i] for i in f])
    for i in range(n): slab(ring_i[i], ring_o[i], ring_o[i + 1], ring_i[i + 1])           # 外圈
    for k in range(S['ribs']):                                                              # 放射细骨
        a = math.pi * (k + 0.5) / S['ribs']; w = 0.05
        slab(P(a - w * 0.4, r * 0.18), P(a - w, r * 0.82), P(a + w, r * 0.82), P(a + w * 0.4, r * 0.18))
    slab(P(0, r * 0.2), P(0, -r * 0.0) + V((0, 0, 0.0015)), P(math.pi, -r * 0.0) + V((0, 0, 0.0015)), P(math.pi, r * 0.2))   # 扇轴横梁
    for a_ in (0.0,):   # 挂环：耳钉到扇轴的一小段
        slab(lobe + V((side * 0.003, -0.0006, -0.001)), c + V((0, -0.0006, 0.002)), c + V((0, 0.0006, 0.002)), lobe + V((side * 0.003, 0.0006, -0.001)))
    me = bpy.data.meshes.new(cid + '_earring'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    me.materials.append(_gold(cid + '_gold', S['rgb']))
    ob = bpy.data.objects.new(cid + '_earring', me); bpy.context.scene.collection.objects.link(ob)
    pb = rig.pose.bones['head']; RW = rig.matrix_world
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = 'head'
    ob.matrix_parent_inverse = (RW @ pb.matrix @ Mx.Translation((0, pb.length, 0))).inverted()
    print('EARRING OK', cid, 'side', side, flush=True)
    return ob
