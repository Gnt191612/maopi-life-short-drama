# -*- coding: utf-8 -*-
"""重定向测试：林晓走路（07_01）、爬梯子（13_33）、坐下起立（13_01），各取若干帧拼成胶片条。"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import bpy
from mathutils import Vector
import retarget

CLIPS = [('07_01', 1, 72), ('13_33', 1, 120), ('13_01', 1, 120)]
for name, f0, f1 in CLIPS:
    bpy.ops.wm.open_mainfile(filepath=os.path.join(config.CAST, 'lin.blend'))
    sc = bpy.context.scene; sc.render.fps = 24
    tgt = bpy.data.objects['lin_rig']
    src = retarget.load_bvh(os.path.join(config.MOCAP, '%s.bvh') % name)
    retarget.retarget(src, tgt, f0, f1, action_name=name)
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.ops.mesh.primitive_plane_add(size=20)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
    cam.location = (4.5, -4.5, 1.3); d = Vector((0, 0, 0.9)) - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 28; sc.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3; sun.rotation_euler = (0.8, 0.2, 0.5); sc.collection.objects.link(sun)
    sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.4, 0.4, 0.43)
    sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 360, 360
    for i, f in enumerate(range(f0, f1 + 1, max(1, (f1 - f0) // 5))):
        sc.frame_set(f); sc.render.filepath = os.path.join(config.RENDERS, 'mocap_%s_%d.png' % (name, i)); bpy.ops.render.render(write_still=True)
    print('MOCAP OK', name, flush=True)
