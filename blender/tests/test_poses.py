# -*- coding: utf-8 -*-
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import bpy
from mathutils import Vector
import poses

TESTS = [('stand', 'down'), ('sit', 'desk'), ('sit_bed', 'phone'), ('lie', 'phone_up'), ('crouch', 'phone'), ('slump', 'face_hands'),
         ('hug_knees', 'knees'), ('stand', 'phone'), ('stand', 'selfie'), ('stand', 'phone_ear'), ('stand', 'brush'), ('stand', 'cover_face'),
         ('stand', 'wave'), ('stand', 'clap'), ('stand', 'phone2'), ('stand', 'tray')]
bpy.ops.wm.open_mainfile(filepath=os.path.join(config.CAST, 'lin.blend'))
sc = bpy.context.scene; rig = bpy.data.objects['lin_rig']
bpy.ops.mesh.primitive_plane_add(size=20)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 35
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3; sun.rotation_euler = (0.8, 0.2, 0.6); sc.collection.objects.link(sun)
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.4, 0.4, 0.43)
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 300, 300
for i, (base, arms) in enumerate(TESTS):
    z = 0.6 if base in ('sit_bed', 'lie', 'hug_knees') else 0.0
    poses.apply_state(rig, dict(pos=(0, 0, z), yaw=0, base=base, arms=arms))
    tgt = Vector((0, 0, 0.9 if base == 'stand' else 0.7))
    cam.location = tgt + Vector((1.9, -2.4, 0.5)); cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(config.RENDERS, 'pose_%02d.png' % i); bpy.ops.render.render(write_still=True)
print('POSES OK', flush=True)
