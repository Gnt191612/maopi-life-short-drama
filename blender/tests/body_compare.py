# -*- coding: utf-8 -*-
"""全身检查图：正面 / 3/4 / 侧面 / 背面，带皮肤与素模各一套（站姿、手臂自然下垂）。
blender -b --factory-startup -P blender/tests/body_compare.py -- <角色.blend> <cid> <输出目录>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
import poses, realism, life
blend, cid, out = sys.argv[sys.argv.index('--') + 1:][:3]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.56, 0.58, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5; sc.world = w
with bpy.data.libraries.load(blend) as (s, d): d.objects = list(s.objects)
for o in d.objects: sc.collection.objects.link(o)
rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
poses.SUPPORT_ON = False; poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down')); life.hands(rig, None)
bpy.context.view_layer.update()
if os.environ.get('V11_NOCLOTH'):   # 只看身体：衣服、鞋隐藏，身体上被衣服遮住的部分重新显示
    body = bpy.data.objects[cid + '_body']
    for o in list(sc.objects):
        if o.type == 'MESH' and o is not body and o.parent is not None and not any(k in o.name for k in ('eye', 'Eye', 'lash', 'teeth', 'hair', 'pony', 'scalp', 'headband', 'tail', 'brow')):
            o.hide_render = True
    for m in body.modifiers:
        if m.type == 'MASK' and m.name != 'Hide helpers': m.show_render = False
bpy.ops.mesh.primitive_plane_add(size=8); floor = bpy.context.active_object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True; fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.35, 0.36, 1); floor.data.materials.append(fm)
H = 1.63; c = Vector((0, 0, H * 0.5))
for name, loc, e, sz in (('key', (1.6, -3.0, 2.6), 900, 2.5), ('fill', (-2.4, -2.0, 1.6), 400, 3.0), ('rim', (0.5, 2.8, 2.4), 500, 2.0)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.shape = 'DISK'; l.data.energy = e; l.data.size = sz; l.location = loc
    l.rotation_euler = (c - l.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.eevee.taa_render_samples = 48
sc.render.resolution_x, sc.render.resolution_y = 640, 1100; sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = -0.4
VIEWS = (('front', 0), ('34', 35), ('side', 90), ('back', 180))
def shoot(tag):
    for view, ang in VIEWS:
        r = math.radians(ang); cam.location = c + Vector((4.2 * math.sin(r), -4.2 * math.cos(r), 0.0))
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, '%s_%s_%s.png' % (cid, tag, view)); bpy.ops.render.render(write_still=True)
shoot('skin')
clay = bpy.data.materials.new('clay'); clay.use_nodes = True
b = clay.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0.62, 0.6, 0.58, 1); b.inputs['Roughness'].default_value = 0.6
for o in sc.objects:
    if o.type == 'MESH' and o is not floor and not any(k in o.name for k in ('eye', 'Eye', 'lash')):
        o.data.materials.clear(); o.data.materials.append(clay)
        for p in o.data.polygons: p.material_index = 0
shoot('clay')
print('BODY OK', cid, flush=True)
