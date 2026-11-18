# -*- coding: utf-8 -*-
"""穿模自动检查：打开拍好的片段动画（build/shots/<seg>.blend），每隔 N 帧检查人物网格顶点是否钻进家具/场景物体、或钻进别的角色。
blender -b --factory-startup -P blender/tests/clip_check.py -- <seg_id ...> [--step 6]
输出：build/logs/clip_<seg>.json ——按拍列出 (角色, 被穿的物体, 穿入深度 cm, 帧)，并打印最严重的若干条。
家具基本都是长方体，所以用「点是否在物体局部包围盒内」判断，深度 = 到最近包围盒面的距离。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index('--') + 1:]
step = int(argv[argv.index('--step') + 1]) if '--step' in argv else 6
segs = [a for a in argv if not a.startswith('--') and not a.isdigit()]
CAM_ONLY = '--cam-only' in argv          # 只查机位（快）
SKIP = ('prop_screen', 'prop_phone', 'cam_', 'furn_quilt', 'furn_pillow')   # 被子、枕头是软的，人压进去/盖在身上是正常的
MARGIN = 0.015                                   # 1.5 cm 以内算贴合（坐在椅子上、手搭桌面）

def person_meshes(rig):
    return [o for o in rig.children if o.type == 'MESH' and not o.name.endswith(('_eyelashes01', '_teeth_base', '_high-poly', '_scalpcap'))
            and 'eyebrow' not in o.name]

def sample_points(objs, every):
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in objs:
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        mw = o.matrix_world
        pts += [mw @ m.vertices[i].co for i in range(0, len(m.vertices), every)]
        ev.to_mesh_clear()
    return pts

CID = {'林晓': 'lin', '陈瑶': 'chen', '周明远': 'zhou', '王老师': 'wang', '林母': 'mom', '同学甲': 'classA', '同学乙': 'classB'}

def check_cameras(sc, tl, rigs):
    """说台词的人：脸是否朝向镜头、是否在画面里、有没有被别人挡住、镜头是不是钻进了某个人身体里"""
    sys.path.insert(0, os.path.join(config.ROOT, 'story')); from lines import LINES
    spk = {l[0]: CID.get(l[1]) for l in LINES}
    from bpy_extras.object_utils import world_to_camera_view
    byname = {r.name[:-4]: r for r in rigs}
    dg = None; out = []
    for b in tl:
        for fr, lid in b['audio']:
            cid = spk.get(lid)
            if cid not in byname: continue
            f = fr + 12
            sc.frame_set(f); cam = sc.camera
            for m in sorted(sc.timeline_markers, key=lambda m: m.frame):   # 当前帧生效的机位
                if m.frame <= f and m.camera: cam = m.camera
            rig = byname[cid]; hb = rig.pose.bones['head']
            rest_face = hb.bone.matrix_local.inverted().to_3x3() @ Vector((0, -1, 0))
            hm = rig.matrix_world @ hb.matrix
            face = (hm.to_3x3() @ rest_face).normalized(); head = hm.translation + (hm.to_3x3() @ Vector((0, hb.length * 0.5, 0)))
            cpos = cam.matrix_world.translation; to_cam = (cpos - head).normalized()
            v = world_to_camera_view(sc, cam, head)
            issues = []
            if face.dot(to_cam) < 0.2: issues.append('背对镜头')
            if v.z <= 0 or not (0.02 < v.x < 0.98 and 0.02 < v.y < 0.98): issues.append('出画')
            dg = bpy.context.evaluated_depsgraph_get()
            hit, loc, _, _, obj, _ = sc.ray_cast(dg, cpos, (head - cpos).normalized(), distance=(head - cpos).length - 0.15)
            if hit and obj.parent is not None and obj.parent.type == 'ARMATURE' and obj.parent is not rig and not obj.name.startswith('prop_'):
                issues.append('被%s挡住' % obj.parent.name[:-4])
            for r in rigs:
                rh = r.matrix_world @ r.pose.bones['root'].head; top = (r.matrix_world @ r.pose.bones['head'].tail).z
                if Vector((cpos.x - rh.x, cpos.y - rh.y)).length < 0.22 and 0 < cpos.z < top + 0.1 and not cam.name.endswith('_phone'):
                    issues.append('镜头在%s身体里' % r.name[:-4])
            if issues: out.append([b['id'], lid, cid, f, cam.name, '/'.join(issues)])
    return out

def check(seg):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(config.SHOTS, seg + '.blend'))
    sc = bpy.context.scene
    tl = json.load(open(os.path.join(config.SHOTS, seg + '_timeline.json'), encoding='utf-8'))
    rigs = [o for o in sc.objects if o.type == 'ARMATURE' and o.name.endswith('_rig')]
    scenery = [o for o in sc.objects if o.type == 'MESH' and o.parent is None and not o.name.startswith(SKIP)
               and not o.name.endswith(('_rest', '_held'))]
    found = {}
    for b in ([] if CAM_ONLY else tl):
        for fr in range(b['f0'], b['f1'] + 1, step):
            sc.frame_set(fr)
            pts = {r.name[:-4]: sample_points(person_meshes(r), 7) for r in rigs}
            for cid, P in pts.items():
                if not P: continue
                lo = Vector([min(p[i] for p in P) for i in range(3)]); hi = Vector([max(p[i] for p in P) for i in range(3)])
                for o in scenery:
                    if o.hide_render: continue
                    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
                    olo = Vector([min(c[i] for c in bb) for i in range(3)]); ohi = Vector([max(c[i] for c in bb) for i in range(3)])
                    if any(olo[i] > hi[i] or ohi[i] < lo[i] for i in range(3)): continue
                    inv = o.matrix_world.inverted(); blo = Vector([min(c[i] for c in o.bound_box) for i in range(3)])
                    bhi = Vector([max(c[i] for c in o.bound_box) for i in range(3)])
                    sx = o.matrix_world.to_scale(); depth = 0.0; n = 0
                    for p in P:
                        q = inv @ p
                        dd = min(min(q[i] - blo[i], bhi[i] - q[i]) * sx[i] for i in range(3))
                        if dd > MARGIN: depth = max(depth, dd); n += 1
                    if n >= 3:
                        k = (b['id'], cid, o.name)
                        if k not in found or depth > found[k][0]: found[k] = (depth, fr, n)
                # 人与人：A 的顶点离 B 的顶点很近且 B 在 A 的包围盒内部方向——用 KD 树找「互相嵌入」的点数
                for cid2, Q in pts.items():
                    if cid2 <= cid or not Q: continue
                    kd = KDTree(len(Q))
                    for i, q in enumerate(Q): kd.insert(q, i)
                    kd.balance()
                    close = sum(1 for p in P if kd.find(p)[2] < 0.006)
                    if close >= 25:
                        k = (b['id'], cid, cid2)
                        if k not in found or close > found[k][2]: found[k] = (0.0, fr, close)
    cam_issues = check_cameras(sc, tl, rigs)
    rows = sorted(([*k, round(v[0] * 100, 1), v[1], v[2]] for k, v in found.items()), key=lambda r: -r[3] - r[5] / 100)
    for r in cam_issues: print('CAM', seg, *r, flush=True)
    json.dump(cam_issues, open(os.path.join(config.LOGS, 'cam_%s.json' % seg), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(rows, open(os.path.join(config.LOGS, 'clip_%s.json' % seg), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    for r in rows[:25]: print('CLIP', seg, *r, flush=True)
    print('CLIPSUM', seg, len(rows), flush=True)

for s in segs: check(s)
