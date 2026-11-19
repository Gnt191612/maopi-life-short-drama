# -*- coding: utf-8 -*-
"""侧脸特写（检查耳朵上方、两鬓头发是否贴着头皮）：每人正侧面 + 斜后方各一张。
blender -b --factory-startup -P blender/tests/side_heads.py -- [角色id ...]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
import poses, realism, life
IDS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv and sys.argv[-1] != '--' else ['lin', 'chen', 'zhou', 'wang', 'classA']
OUT = os.path.join(config.RENDERS, 'side_heads'); os.makedirs(OUT, exist_ok=True)
for cid in IDS:
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
    w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.6, 0.62, 0.65, 1); sc.world = w
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (s, d): d.objects = list(s.objects)
    for o in d.objects: sc.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
    poses.SUPPORT_ON = False; poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down')); life.hands(rig, None)
    bpy.context.view_layer.update()
    head = poses.head_pos(rig) + Vector((0, 0.01, 0.06))
    for name, loc, e in (('key', (1.2, -0.8, 2.2), 260), ('fill', (-1.2, -0.8, 1.8), 120)):
        l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = e; l.data.size = 1.5; l.location = loc
        l.rotation_euler = (head - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 85
    sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x = sc.render.resolution_y = 520; sc.view_settings.view_transform = 'AgX'
    for view, ang in (('side', 90), ('backside', 140)):
        a = math.radians(ang); cam.location = head + Vector((0.62 * math.sin(a), -0.62 * math.cos(a), 0.0))
        cam.rotation_euler = (head - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (cid, view)); bpy.ops.render.render(write_still=True)
    print('SIDE OK', cid, flush=True)
