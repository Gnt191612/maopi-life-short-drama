# -*- coding: utf-8 -*-
"""定妆照底图：每个角色按 5 个机位渲染白模（正脸/3/4 侧脸/正侧脸/半身/全身）+ 对应深度图，
交给 lookdev/portraits.py 生成照片级定妆照（深度锁定脸型与角度，文字描述外观，正脸生成后作为其余角度的长相参考）。
blender -b --factory-startup -P blender/lookdev_renders.py -- [角色id ...]
输出 build/lookdev/<cid>_<view>.png 与 <cid>_<view>_depth.png"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import bpy
from mathutils import Vector
import poses, realism, life

IDS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv and sys.argv[-1] != '--' else ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
OUT = os.path.join(config.ROOT, 'build', 'lookdev'); os.makedirs(OUT, exist_ok=True)
# 机位：(名字, 对准部位, 水平角°, 距离 m, 焦距 mm, 分辨率)
VIEWS = [('face_front', 'face', 0, 0.75, 85, (1024, 1024)), ('face_34', 'face', 35, 0.75, 85, (1024, 1024)),
         ('face_side', 'face', 85, 0.75, 85, (1024, 1024)), ('half', 'chest', 15, 1.7, 50, (896, 1152)),
         ('full', 'body', 10, 4.2, 50, (832, 1216))]

def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.56, 0.58, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6; sc.world = w
    for name, loc, energy, size in (('key', (1.4, -2.2, 2.3), 320, 2.5), ('fill', (-2.0, -1.6, 1.6), 150, 3.0), ('rim', (0.0, 2.2, 2.5), 220, 1.5)):
        l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = energy; l.data.size = size
        l.location = loc; l.rotation_euler = (Vector((0, 0, 1.3)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    sc.cycles.samples = 64; sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_layers[0].use_pass_z = True
    sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers'); comp = nt.nodes.new('CompositorNodeComposite'); nt.links.new(rl.outputs['Image'], comp.inputs['Image'])
    norm = nt.nodes.new('CompositorNodeNormalize'); inv = nt.nodes.new('CompositorNodeInvert')
    fo = nt.nodes.new('CompositorNodeOutputFile'); fo.base_path = OUT; fo.format.file_format = 'PNG'; fo.format.color_mode = 'BW'
    nt.links.new(rl.outputs['Depth'], norm.inputs[0]); nt.links.new(norm.outputs[0], inv.inputs['Color']); nt.links.new(inv.outputs[0], fo.inputs[0])
    return sc, cam, fo

for cid in IDS:
    sc, cam, fo = scene()
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst): dst.objects = list(src.objects)
    for o in dst.objects: sc.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
    for m in bpy.data.materials:
        b = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes and m.node_tree else None
        if b and b.inputs['Subsurface Weight'].default_value > 0: b.inputs['Subsurface Scale'].default_value = 0.004
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down')); life.hands(rig, None); bpy.context.view_layer.update()
    head = poses.head_pos(rig)
    target = {'face': head + Vector((0, -0.06, 0.03)), 'chest': head + Vector((0, 0, -0.32)), 'body': Vector((0, 0, head.z * 0.52))}
    for name, part, ang, dist, lens, res in VIEWS:
        t = target[part]; a = math.radians(ang)
        cam.location = t + Vector((dist * math.sin(a), -dist * math.cos(a), 0.02)); cam.data.lens = lens
        cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.resolution_x, sc.render.resolution_y = res
        fo.file_slots[0].path = '%s_%s_depth' % (cid, name)
        sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (cid, name)); bpy.ops.render.render(write_still=True)
        # 合成器文件输出会带帧号后缀，改成固定名字
        for f in os.listdir(OUT):
            if f.startswith('%s_%s_depth' % (cid, name)) and f != '%s_%s_depth.png' % (cid, name):
                os.replace(os.path.join(OUT, f), os.path.join(OUT, '%s_%s_depth.png' % (cid, name)))
    print('LOOKDEV OK', cid, flush=True)
