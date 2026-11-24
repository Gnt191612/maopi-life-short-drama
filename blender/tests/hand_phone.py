# -*- coding: utf-8 -*-
"""握手机特写检查：角色摆出拿手机的姿势，从三个方向拍右手特写 → build/review/handphone_<cid>.png（拼图由调用方做）
blender -b --factory-startup -P blender/tests/hand_phone.py -- <cid> [arms ...]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'lib')): sys.path.insert(0, p)
import config
import bpy
from mathutils import Vector
import shoot, poses, realism, life
if os.environ.get('HP_GRIP'): g_ = [float(v) for v in os.environ['HP_GRIP'].split(',')]; life.GRIP = tuple(g_[:3]); life.GRIP_THUMB = g_[3]
argv = sys.argv[sys.argv.index('--') + 1:]
cid = argv[0]; ARMS = argv[1:] or ['phone', 'phone2', 'selfie']
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rig = shoot.append_cast(cid)
realism.apply_hdri('dorm_am')
held = shoot.make_phone(cid + '_held'); held.parent = rig; held.parent_type = 'BONE'; held.parent_bone = 'wrist.R'
shoot.setup_held_phone(held, rig) if hasattr(shoot, 'setup_held_phone') else None
if not hasattr(shoot, 'setup_held_phone'):
    hz = float(os.environ.get('HP_Z', '0.03')); hinf = float(os.environ.get('HP_INF', '0.85'))
    held.location = (0.0, float(os.environ.get('HP_Y', '0.06')), hz)
    held.rotation_euler = tuple(float(v) for v in os.environ.get('HP_ROT', '0,0,0').split(','))
    if hinf > 0:
        con = held.constraints.new('DAMPED_TRACK'); con.target = rig; con.subtarget = 'head'; con.track_axis = 'TRACK_Z'; con.influence = hinf
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun); sun.rotation_euler = (0.8, 0.2, 0.6); sun.data.energy = 3
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x = sc.render.resolution_y = 400; sc.eevee.taa_render_samples = 16
out = os.path.join(config.ROOT, 'build', 'review', 'handphone'); os.makedirs(out, exist_ok=True)
for i, a in enumerate(ARMS):
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms=a), frame=i + 1)
    life.hands(rig, i + 1, True, a in ('phone2',))
for i, a in enumerate(ARMS):
    sc.frame_set(i + 1); bpy.context.view_layer.update()
    scr_ = next(o for o in bpy.data.objects if o.name.startswith('prop_screen_') and '_held' in o.name); nrm = (scr_.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized(); hp_ = poses.head_pos(rig); print('SCREENDOT', a, round(nrm.dot((hp_ - scr_.matrix_world.translation).normalized()), 2))
    w = rig.matrix_world @ rig.pose.bones['wrist.R'].tail
    for j, off in enumerate((Vector((0, -0.35, 0.05)), Vector((-0.3, -0.15, 0.1)), Vector((0.15, 0.25, 0.25)))):
        cam.location = w + off; cam.rotation_euler = (w - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, '%s%s_%d_%s_%d.png' % (os.environ.get('HP_TAG', ''), cid, i, a, j)); bpy.ops.render.render(write_still=True)
print('HANDPHONE DONE')
