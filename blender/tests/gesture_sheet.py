# -*- coding: utf-8 -*-
"""手势总览：把角色的习惯动作/说话手势逐个摆出来，从 3/4 正面拍，拼成 build/review/gestures_<cid>.jpg，检查手臂有没有横在脸前、插进身体。
blender -b --factory-startup -P blender/tests/gesture_sheet.py -- <cid> [手势 ...]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'blender'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'blender', 'lib'))
import config
import bpy
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
cid = argv[0]
import shoot, poses, realism, life
GEST = argv[1:] or sorted({g for d in (shoot.HABITS.get(cid, {}), ) for v in d.values() for g in v} | set(shoot.TALK.get(cid, [])) | {'down', 'phone', 'gesture'})
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rig = shoot.append_cast(cid)
realism.apply_hdri('dorm_am')
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 70; cam.location = (0.7, -1.9, 1.45)
cam.rotation_euler = (Vector((0, 0, 1.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x = sc.render.resolution_y = 480; sc.eevee.taa_render_samples = 16
out = os.path.join(config.ROOT, 'build', 'review', 'gest_' + cid); os.makedirs(out, exist_ok=True)
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun); sun.rotation_euler = (0.8, 0.2, 0.6); sun.data.energy = 3
for i, g in enumerate(GEST):
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms=g), frame=i + 1)
    life.hands(rig, i + 1, poses.ARMS[g].get('prop') in ('hand', 'ear'))   # 手指和正片一样：放松微屈 / 拿手机握住
for i, g in enumerate(GEST):
    sc.frame_set(i + 1); sc.render.filepath = os.path.join(out, '%02d_%s.png' % (i, g)); bpy.ops.render.render(write_still=True)
print('GEST DONE', cid, len(GEST))
