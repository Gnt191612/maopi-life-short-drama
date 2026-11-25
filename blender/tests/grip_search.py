# -*- coding: utf-8 -*-
"""握手机参数搜索：手机在右手腕骨局部的位置 × 手指三节弯曲角度，统计「插进手机的手部顶点数」和「手指离手机背面的距离」，
挑出不穿模又贴合的一组。blender -b --factory-startup -P blender/tests/grip_search.py -- <cid>"""
import os, sys, itertools, math
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'lib')): sys.path.insert(0, p)
import bpy
import numpy as np
from mathutils import Vector, Matrix
import shoot, poses, life
cid = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
rig = shoot.append_cast(cid)
poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='phone'), frame=None)
body = [o for o in rig.children if o.type == 'MESH' and o.name.endswith('_body')][0]
W, H, T = 0.075, 0.155, 0.008
ROT = Matrix(((0, 0, -1), (-1, 0, 0), (0, 1, 0)))   # 手机轴在腕骨局部：X=-Y_w, Y=+Z_w, Z(屏幕)=-X_w
pb = rig.pose.bones
hand_idx = None
def verts_wl():
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); m = ev.to_mesh()
    co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); ev.to_mesh_clear()
    co = co.reshape(-1, 3); Mb = np.array(body.matrix_world, np.float32); wv = co @ Mb[:3, :3].T + Mb[:3, 3]
    Wi = np.array((rig.matrix_world @ pb['wrist.R'].matrix).inverted(), np.float32)
    return wv @ Wi[:3, :3].T + Wi[:3, 3]
best = []
for g1, g2, g3, gt in itertools.product((0, 6), (20, 35, 50), (25, 45), (5, 15, 25)):
    life.GRIP = (g1, g2, g3); life.GRIP_THUMB = gt; life.hands(rig, None, True, False); bpy.context.view_layer.update()
    lv = verts_wl()
    near = lv[(np.abs(lv[:, 0]) < 0.08) & (lv[:, 1] > -0.02) & (lv[:, 1] < 0.24) & (np.abs(lv[:, 2]) < 0.12)]
    for cx, cy, cz in itertools.product((-0.024, -0.028, -0.032, -0.036), (0.10, 0.115, 0.13), (0.035, 0.05)):
        q = (near - np.array([cx, cy, cz], np.float32)) @ np.array(ROT, np.float32)   # 转到手机局部
        inside = np.sum((np.abs(q[:, 0]) < W / 2) & (np.abs(q[:, 1]) < H / 2) & (np.abs(q[:, 2]) < T / 2))
        back = q[(np.abs(q[:, 0]) < W / 2) & (np.abs(q[:, 1]) < H / 2) & (q[:, 2] < -T / 2)]   # 手机背面一侧、投影落在手机上的手部顶点
        gap = float(np.min(-T / 2 - back[:, 2])) if len(back) else 1.0                     # 离背面最近的距离
        cover = len(back)
        score = inside * 10 + gap * 2000 - min(cover, 400) * 0.05
        ins = near[(np.abs(q[:, 0]) < W / 2) & (np.abs(q[:, 1]) < H / 2) & (np.abs(q[:, 2]) < T / 2)]
        where = 'thumbside' if len(ins) and float(np.mean(ins[:, 2])) > 0.03 else ('palm' if len(ins) and float(np.mean(ins[:, 1])) < 0.11 else 'fingers')
        best.append((score, inside, round(gap * 1000, 1), cover, (g1, g2, g3, gt), (cx, cy, cz), where))
best.sort(key=lambda r: r[0])
for r in best[:8]: print('BEST', r)
