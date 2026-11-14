# -*- coding: utf-8 -*-
"""口型骨骼测试：林晓脸部特写，渲染 X / C / D / F 四种嘴型拼成一张图。"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import bpy
import face

bpy.ops.wm.open_mainfile(filepath=os.path.join(config.CAST, 'lin.blend'))
sc = bpy.context.scene
rig = bpy.data.objects['lin_rig']
head = rig.matrix_world @ rig.pose.bones['head'].head
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
cam.location = (head.x, head.y - 0.55, head.z + 0.05); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 85
sc.camera = cam
light = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA')); light.data.energy = 60; light.data.size = 1
light.location = (head.x + 0.6, head.y - 0.8, head.z + 0.5); light.rotation_euler = (math.radians(60), 0, math.radians(35)); sc.collection.objects.link(light)
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.3, 0.3, 0.32)
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 400, 400
for shape in ('X', 'C', 'D', 'F'):
    face.set_viseme(rig, shape)
    bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(config.RENDERS, 'face_%s.png' % shape)
    bpy.ops.render.render(write_still=True)
print('FACE TEST OK', flush=True)
