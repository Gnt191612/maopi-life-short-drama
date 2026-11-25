# -*- coding: utf-8 -*-
"""躺着举手机检查：角色躺平（base=lie）摆 phone_up，从侧面、脚那头、头顶三个方向拍 → build/review/liephone/
blender -b --factory-startup -P blender/tests/lie_phone.py -- <cid> [arms]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'lib')): sys.path.insert(0, p)
import config
import bpy
from mathutils import Vector
import shoot, poses, realism, life
argv = sys.argv[sys.argv.index('--') + 1:]
cid = argv[0]; arms = argv[1] if len(argv) > 1 else 'phone_up'
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rig = shoot.append_cast(cid)
realism.apply_hdri('dorm_am')
held = shoot.make_phone(cid + '_held'); held.parent = rig; held.parent_type = 'BONE'; held.parent_bone = 'wrist.R'
shoot.setup_held_phone(held, rig)
poses.apply_state(rig, dict(pos=(0, 0, 0.9), yaw=0, base='lie', arms=arms), frame=1)
life.hands(rig, 1, True, bool(poses.ARMS[arms].get('support')) or arms == 'phone_up')
sc.frame_set(1); bpy.context.view_layer.update()
scr = next(o for o in bpy.data.objects if o.name.startswith('prop_screen_') and '_held' in o.name)
nrm = (scr.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized(); hp = poses.head_pos(rig)
print('SCREENDOT', round(nrm.dot((hp - scr.matrix_world.translation).normalized()), 2), 'phone_to_eye_m', round((hp - scr.matrix_world.translation).length, 2))
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 35
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun); sun.rotation_euler = (0.6, 0.2, 0.6); sun.data.energy = 3
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x = sc.render.resolution_y = 400; sc.eevee.taa_render_samples = 16
out = os.path.join(config.ROOT, 'build', 'review', 'liephone'); os.makedirs(out, exist_ok=True)
c = (rig.matrix_world @ rig.pose.bones['spine03'].head) if 'spine03' in rig.pose.bones else hp
for j, off in enumerate((Vector((1.6, 0, 0.3)), Vector((0, -1.8, 0.9)), Vector((0, 1.2, 1.0)))):
    cam.location = c + off; cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out, '%s_%s_%d.png' % (cid, arms, j)); bpy.ops.render.render(write_still=True)
print('LIEPHONE DONE')
