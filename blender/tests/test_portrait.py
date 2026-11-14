# -*- coding: utf-8 -*-
"""写实度对比测试：角色在宿舍场景里的人像近景。blender -b -P test_portrait.py -- <cid> <eevee|cycles> <out.png>"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import bpy
from mathutils import Vector
import poses

cid, engine, out = sys.argv[sys.argv.index('--') + 1:][:3]
bpy.ops.wm.open_mainfile(filepath=os.path.join(config.SETS, 'dorm_pm.blend'))
with bpy.data.libraries.load(os.path.join(config.CAST, '%s.blend') % cid) as (src, dst):
    dst.objects = list(src.objects)
for o in dst.objects: bpy.context.scene.collection.objects.link(o)
sc = bpy.context.scene; rig = bpy.data.objects[cid + '_rig']
poses.apply_state(rig, dict(pos=(0.1, 0.6, 0), yaw=200, base='stand', arms='down'))
head = poses.head_pos(rig)
cam = bpy.data.objects.new('pcam', bpy.data.cameras.new('pcam')); sc.collection.objects.link(cam); sc.camera = cam
fwd = Vector((math.sin(math.radians(200)), -math.cos(math.radians(200)), 0)); rgt = fwd.cross(Vector((0, 0, 1)))
D_ = float(os.environ.get('P_DIST', 0.95)); cam.location = head + fwd * D_ + rgt * D_ * 0.32 + Vector((0, 0, 0.05)); cam.rotation_euler = (head + Vector((0, 0, 0.02 - 0.08 * (D_ < 1.1))) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 85
if engine == 'cycles':
    face = head + fwd * 0.09 + Vector((0, 0, 0.03))
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (face - cam.location).length; cam.data.dof.aperture_fstop = 2.8
    for m in bpy.data.materials:   # 皮肤次表面散射按真实尺度（米），避免蜡像感
        b = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes else None
        if b and b.inputs['Subsurface Weight'].default_value > 0: b.inputs['Subsurface Scale'].default_value = 0.004
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    sc.cycles.samples = int(os.environ.get('CY_SAMPLES', 256)); sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    # 真实环境光：Blender 自带的室内 HDRI（与场景灯光叠加）
    w = sc.world; w.use_nodes = True; nt = w.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(os.path.dirname(bpy.app.binary_path), '4.5', 'datafiles', 'studiolights', 'world', 'interior.exr'))
    nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color']); nt.nodes['Background'].inputs['Strength'].default_value = 0.8
    # 三点布光：主光（窗边柔光）+ 轮廓光
    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA')); key.data.energy = 120; key.data.size = 1.2; key.data.color = (1, 0.95, 0.88)
    key.location = head + fwd * 0.8 - rgt * 0.8 + Vector((0, 0, 0.5)); key.rotation_euler = (head - key.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(key)
    rim = bpy.data.objects.new('rim', bpy.data.lights.new('rim', 'AREA')); rim.data.energy = 60; rim.data.size = 0.6
    rim.location = head - fwd * 0.8 + rgt * 0.6 + Vector((0, 0, 0.4)); rim.rotation_euler = (head - rim.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(rim)
else:
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast' if engine == 'cycles' else 'None'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
print('PORTRAIT OK', engine, flush=True)
