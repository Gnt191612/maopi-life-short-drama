# -*- coding: utf-8 -*-
"""GLB 模型多角度预览（检查 AI 图生 3D 的效果）：正面 / 3/4 / 侧面 / 背面各一张。
blender -b --factory-startup -P blender/tests/glb_turntable.py -- <模型.glb> <输出目录>"""
import sys, os, math
import bpy
from mathutils import Vector
src, out = sys.argv[sys.argv.index('--') + 1:][:2]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
objs = [o for o in sc.objects if o.type == 'MESH']
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2; size = max(hi - lo)
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.57, 0.6, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6; sc.world = w
for name, d, e in (('key', Vector((1.2, -1.6, 1.4)), 600), ('fill', Vector((-1.6, -1.0, 0.6)), 250), ('rim', Vector((0.3, 1.8, 1.2)), 300)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = e * size * size * 4; l.data.size = size * 1.5
    l.location = c + d * size * 1.5; l.rotation_euler = (c - l.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 70
sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 768; sc.view_settings.view_transform = 'AgX'
# GLB 坐标：Y 朝上导入后转成 Blender 的 Z 朝上；模型正面通常朝 -Y
for view, ang in (('front', 0), ('34', 35), ('side', 90), ('back', 180)):
    a = math.radians(ang); dist = size * 2.4
    cam.location = c + Vector((dist * math.sin(a), -dist * math.cos(a), size * 0.05)); cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out, 'glb_%s.png' % view); bpy.ops.render.render(write_still=True)
print('TURNTABLE OK', size, flush=True)
