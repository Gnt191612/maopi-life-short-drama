# -*- coding: utf-8 -*-
"""定妆照对比：角色头部按照片视角（正面，偏航角取脸型拟合结果）+ 3/4 + 正侧面渲染，素模（灰）和带皮肤各一套。
blender -b --factory-startup -P blender/tests/identity_compare.py -- <角色.blend> <cid> <输出目录> [偏航角°]
之后用 blender/tests/identity_sheet.py 和定妆照拼成对比图"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
import poses, realism, life
a = sys.argv[sys.argv.index('--') + 1:]
blend, cid, out = a[:3]; yaw = float(a[3]) if len(a) > 3 else 0.0
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.56, 0.58, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5; sc.world = w
with bpy.data.libraries.load(blend) as (s, d): d.objects = list(s.objects)
for o in d.objects: sc.collection.objects.link(o)
rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
poses.SUPPORT_ON = False; poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down')); life.hands(rig, None)
bpy.context.view_layer.update()
head = poses.head_pos(rig) + Vector((0, 0.0, 0.035))
# 柔和的正面主光 + 侧补光（接近定妆照的影棚光）
for name, loc, e, sz in (('key', (0.5, -1.4, 0.45), 55, 0.7), ('fill', (-0.9, -0.9, 0.2), 28, 1.5), ('top', (0.0, -0.3, 1.0), 15, 1.0)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.shape = 'DISK'; l.data.energy = e; l.data.size = sz;   # 圆形灯（方灯在头发隆起处反出方形高光）
    l.location = head + Vector(loc)
    l.rotation_euler = (head - l.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 85
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.eevee.taa_render_samples = 48
sc.render.resolution_x, sc.render.resolution_y = 1024, 1280; sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = -0.6
clay = bpy.data.materials.new('clay'); clay.use_nodes = True
b = clay.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0.62, 0.6, 0.58, 1); b.inputs['Roughness'].default_value = 0.6
VIEWS = (('front', -yaw), ('34', 35), ('side', 90))
if os.environ.get('V11_DBG'):   # 排查用：只拍正脸；NOSSS 关皮肤透光，NOTEETH 隐藏牙齿
    VIEWS = VIEWS[:1]
    if 'NOTEETH' in os.environ['V11_DBG']:
        for o in sc.objects:
            if o.name.endswith('_teeth_base'): o.hide_render = True
    if 'NOSSS' in os.environ['V11_DBG']:
        for m in bpy.data.node_groups:
            for n in m.nodes:
                if n.type == 'BSDF_PRINCIPLED' and 'Subsurface Weight' in n.inputs:
                    for l in list(n.inputs['Subsurface Weight'].links): m.links.remove(l)
                    n.inputs['Subsurface Weight'].default_value = 0.0
def shoot(tag):
    for view, ang in VIEWS:
        r = math.radians(ang); cam.location = head + Vector((0.62 * math.sin(r), -0.62 * math.cos(r), 0.0))
        cam.rotation_euler = (head - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, '%s_%s_%s.png' % (cid, tag, view)); bpy.ops.render.render(write_still=True)
shoot('skin')
for o in sc.objects:   # 素模：皮肤和衣服统一灰色，眼睛保留
    if o.type == 'MESH' and not any(k in o.name for k in ('eye', 'Eye', 'lash')):
        o.data.materials.clear(); o.data.materials.append(clay)
        for p in o.data.polygons: p.material_index = 0
shoot('clay')
print('COMPARE OK', cid, flush=True)
