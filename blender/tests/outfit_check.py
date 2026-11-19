# -*- coding: utf-8 -*-
"""穿搭检查：每人站姿全身正面 / 侧面 / 背面 + 坐姿一张，看衣服是否宽松、有没有穿模。
blender -b --factory-startup -P blender/tests/outfit_check.py -- [角色id ...]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
import poses, realism, life
IDS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv and sys.argv[-1] != '--' else ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
OUT = os.path.join(config.RENDERS, 'outfit_check'); os.makedirs(OUT, exist_ok=True)
for cid in IDS:
    for state in ('stand', 'sit'):
        bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
        w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.57, 0.6, 1); sc.world = w
        with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (s, d): d.objects = list(s.objects)
        for o in d.objects: sc.collection.objects.link(o)
        rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
        poses.SUPPORT_ON = False
        if state == 'stand': poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down'))
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.05, 0.23)); seat = bpy.context.object; seat.scale = (0.5, 0.45, 0.46)
            poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='sit', arms='lap'))
        life.hands(rig, None); bpy.context.view_layer.update()
        H = config_h = max(0.9, poses.head_pos(rig).z)
        for name, loc, e in (('key', (2.0, -2.5, 2.6), 900), ('fill', (-2.2, -1.5, 1.6), 350), ('rim', (0.5, 2.5, 2.2), 400)):
            l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = e; l.data.size = 2.0; l.location = loc
            l.rotation_euler = (Vector((0, 0, H * 0.55)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
        sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x = 560; sc.render.resolution_y = 900; sc.view_settings.view_transform = 'AgX'
        views = (('front', 0), ('side', 90), ('back', 180)) if state == 'stand' else (('sit34', 35),)
        for view, ang in views:
            a = math.radians(ang); tgt = Vector((0, 0, H * 0.52)); dist = H * 1.9
            cam.location = tgt + Vector((dist * math.sin(a), -dist * math.cos(a), 0.1)); cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (cid, view)); bpy.ops.render.render(write_still=True)
    print('OUTFIT OK', cid, flush=True)
