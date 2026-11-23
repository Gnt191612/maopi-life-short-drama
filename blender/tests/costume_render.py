# -*- coding: utf-8 -*-
"""服道化设计用：每个角色站姿全身 3/4 正面 + 背面，输出 build/submission/costume_<cid>_front.png / _back.png
blender -b --factory-startup -P blender/tests/costume_render.py -- [cid ...]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'lib')): sys.path.insert(0, p)
import config
import bpy
from mathutils import Vector
import shoot, poses, realism, life
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
CIDS = argv or ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
out = os.path.join(config.ROOT, 'build', 'submission'); os.makedirs(out, exist_ok=True)
for cid in CIDS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    rig = shoot.append_cast(cid)
    realism.apply_hdri('dorm_am')
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down'), frame=1)
    life.hands(rig, 1)
    sc.frame_set(1)
    h = poses.head_pos(rig).z + 0.15
    cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 50
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
    sun.rotation_euler = (0.9, 0.15, 0.5); sun.data.energy = 3
    sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 600, 900; sc.eevee.taa_render_samples = 32
    for tag, loc in (('front', (1.5, -3.6, h * 0.55)), ('back', (-1.2, 3.8, h * 0.55))):
        cam.location = loc
        cam.rotation_euler = (Vector((0, 0, h * 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, 'costume_%s_%s.png' % (cid, tag)); bpy.ops.render.render(write_still=True)
    print('COSTUME', cid, flush=True)
