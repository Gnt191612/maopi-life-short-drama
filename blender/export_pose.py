# -*- coding: utf-8 -*-
"""导出骨骼姿态控制图（OpenPose BODY-18 格式）：云端视频模型（如 VACE / ControlNet OpenPose）直接可用。
blender -b --factory-startup -P blender/export_pose.py -- <seg_id> [--step 1] [--size 960x540]
输出 build/renders/<seg>/pose_####.png（黑底彩色骨架）与 pose_####.json（每人 18 个关键点：x, y, 置信度；person_id = 固定角色编号）
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import bpy
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index('--') + 1:]
seg = argv[0]
step = int(argv[argv.index('--step') + 1]) if '--step' in argv else 1
W, H = (int(v) for v in (argv[argv.index('--size') + 1] if '--size' in argv else '960x540').split('x'))
OUT = os.path.join(config.RENDERS, seg); os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(config.SHOTS, seg + '.blend'))
sc = bpy.context.scene
FIXED = {'lin': 1, 'chen': 2, 'zhou': 3, 'wang': 4, 'mom': 5, 'classA': 6, 'classB': 7}
# OpenPose BODY-18 顺序 -> 骨骼（None 表示另算：鼻子、耳朵）
KP = [None, 'neck01', 'upperarm01.R', 'lowerarm01.R', 'wrist.R', 'upperarm01.L', 'lowerarm01.L', 'wrist.L',
      'upperleg01.R', 'lowerleg01.R', 'foot.R', 'upperleg01.L', 'lowerleg01.L', 'foot.L', 'eye.R', 'eye.L', None, None]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
         (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
          (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
          (255, 0, 170), (255, 0, 85)]   # OpenPose 官方配色

def keypoints(rig):
    M = rig.matrix_world; pb = rig.pose.bones
    hb = pb['head']; hm = M @ hb.matrix
    rest_face = hb.bone.matrix_local.inverted().to_3x3() @ Vector((0, -1, 0)); face = (hm.to_3x3() @ rest_face).normalized()
    side = (hm.to_3x3() @ (hb.bone.matrix_local.inverted().to_3x3() @ Vector((1, 0, 0)))).normalized()
    hc = (M @ hb.head).lerp(M @ hb.tail, 0.4)
    pts = []
    for i, bn in enumerate(KP):
        if bn: pts.append(M @ pb[bn].head)
        elif i == 0: pts.append(hc + face * 0.10)                       # 鼻尖
        elif i == 16: pts.append(hc - side * 0.075)                     # 右耳（角色右侧 = 局部 -X）
        else: pts.append(hc + side * 0.075)                             # 左耳
    return pts

def draw(img, a, b, col, r=3):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    for t in np.linspace(0, 1, n):
        x, y = int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t)
        img[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = col

rigs = [o for o in sc.objects if o.type == 'ARMATURE' and o.name.endswith('_rig')]
markers = sorted((m for m in sc.timeline_markers if m.camera), key=lambda m: m.frame)
im = bpy.data.images.new('pose', W, H, alpha=False)
for f in range(sc.frame_start, sc.frame_end + 1, step):
    sc.frame_set(f)
    cam = next((m.camera for m in reversed(markers) if m.frame <= f), sc.camera)
    img = np.zeros((H, W, 3), np.uint8); people = []
    for k, rig in enumerate(rigs):
        if all(c.hide_render for c in rig.children if c.type == 'MESH'): continue   # 还没出场的路人
        flat = []; px = []
        for p in keypoints(rig):
            v = world_to_camera_view(sc, cam, p)
            ok = v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1
            x, y = v.x * W, (1 - v.y) * H
            flat += [round(x, 1), round(y, 1), 1.0 if ok else 0.0]; px.append((x, y, ok))
        if not any(p[2] for p in px): continue
        # 遮挡检测（只写进 json，不影响骨架图）：从相机向关键点打射线，先打到别的物体就算被挡住（visible_cast.py 用它判断谁真的入画，踩坑记录 68）
        # 规则：①本人至少有一个网格在渲染里可见（白模里隐藏的角色骨架仍在，曾被误算入画）②从相机打向关键点，第一个打中的必须是本人身体
        meshes = [c for c in rig.children_recursive if c.type == 'MESH']
        shown = any(not c.hide_render and not any(col.hide_render for col in c.users_collection) for c in meshes)
        own = {c.name for c in meshes}; co = cam.matrix_world.translation; dg = bpy.context.evaluated_depsgraph_get(); vis = []
        for p, q in zip(keypoints(rig), px):
            if not q[2] or not shown: vis.append(0); continue
            d = p - co; hit, _loc, _n, _i, obj, _m = sc.ray_cast(dg, co, d.normalized(), distance=d.length + 0.25)
            vis.append(1 if hit and obj is not None and obj.name in own else 0)
        # 脸朝向相机的程度（1 = 正对，0 = 侧面，<0 = 背对/低头只露头顶）：首帧要不要换脸靠它（11-27 s06_01_0446 低头只露头顶，被硬换上一张正脸）
        hb = rig.pose.bones['head']; hm = rig.matrix_world @ hb.matrix
        face = (hm.to_3x3() @ (hb.bone.matrix_local.inverted().to_3x3() @ Vector((0, -1, 0)))).normalized()
        to_cam = (co - rig.matrix_world @ hb.head).normalized()
        people.append({'person_id': FIXED.get(rig.name[:-4], 10 + k), 'pose_keypoints_2d': flat, 'unoccluded': vis, 'facing': round(face.dot(to_cam), 3)})
        for li, (i, j) in enumerate(LIMBS):
            if px[i][2] and px[j][2]: draw(img, px[i], px[j], tuple(c * 0.6 for c in COLORS[li % 18]), 2)
        for i, p in enumerate(px):
            if p[2]: draw(img, p, p, COLORS[i], 4)
    json.dump({'version': 1.3, 'people': people}, open(os.path.join(OUT, 'pose_%04d.json' % f), 'w'))
    rgba = np.concatenate([img[::-1].astype(np.float32) / 255, np.ones((H, W, 1), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel()); im.filepath_raw = os.path.join(OUT, 'pose_%04d.png' % f); im.file_format = 'PNG'; im.save()
print('POSE OK', seg, flush=True)
