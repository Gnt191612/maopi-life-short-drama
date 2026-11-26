# -*- coding: utf-8 -*-
"""导出每帧各角色头部在画面里的位置（本地 Blender）：给 face_unify.py 按位置认人用。
2026-11-25：两人同框时陈瑶常被画成第二个林晓，按长相相似度认人会把两张脸都认成林晓；白模里谁在画面哪里是确定的。
blender -b build/shots/<片段>.blend --factory-startup -P cloud/export_heads.py -- <输出 json> <起始帧> <结束帧>
输出 {帧号: {角色id: [x, y, 头部到镜头距离]}}，x、y 为画面归一化坐标（左上角 0,0）"""
import sys, json
import bpy
from bpy_extras.object_utils import world_to_camera_view
a = sys.argv[sys.argv.index('--') + 1:]
out, f0, f1 = a[0], int(a[1]), int(a[2])
sc = bpy.context.scene
markers = sorted((m for m in sc.timeline_markers if m.camera), key=lambda m: m.frame)
rigs = [o for o in sc.objects if o.type == 'ARMATURE' and o.name.endswith('_rig')]
res = {}
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    cam = next((m.camera for m in reversed(markers) if m.frame <= f), sc.camera)
    d = {}
    for r in rigs:
        if all(c.hide_render for c in r.children if c.type == 'MESH'): continue
        hb = r.pose.bones.get('head')
        if hb is None: continue
        p = r.matrix_world @ hb.head.lerp(hb.tail, 0.6)
        v = world_to_camera_view(sc, cam, p)
        if v.z <= 0: continue
        d[r.name.replace('_rig', '')] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
    res[f] = d
json.dump(res, open(out, 'w'))
print('HEADS', out, f1 - f0 + 1, flush=True)
