# -*- coding: utf-8 -*-
"""角色展示图：每人 全身正面 + 脸部正面 + 脸部 3/4 侧面（影棚灰背景、柔光、Cycles）。
blender -b --factory-startup -P blender/tests/showcase.py -- [角色id ...]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
from mathutils import Vector
import poses, realism, life

IDS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv and sys.argv[-1] != '--' else ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
OUT = os.path.join(config.RENDERS, 'showcase'); os.makedirs(OUT, exist_ok=True)

def studio():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=30); fl = bpy.context.object
    m = bpy.data.materials.new('floor'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.18, 0.19, 1)
    fl.data.materials.append(m)
    w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.16, 0.16, 0.17, 1)
    sc.world = w
    for name, loc, energy, size in (('key', (1.6, -2.4, 2.4), 380, 2.5), ('fill', (-2.2, -1.8, 1.6), 140, 3.0), ('rim', (0.0, 2.2, 2.6), 260, 1.5)):
        l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = energy; l.data.size = size
        l.location = loc; l.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    sc.cycles.samples = 64; sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    return sc, cam

def shoot(sc, cam, path, loc, tgt, lens, res, dof=None):
    cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = lens
    cam.data.dof.use_dof = dof is not None
    if dof: cam.data.dof.focus_distance = (Vector(tgt) - Vector(loc)).length; cam.data.dof.aperture_fstop = dof
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)

for cid in IDS:
    sc, cam = studio()
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects: sc.collection.objects.link(o)
    for m in bpy.data.materials:   # 皮肤散射按真实尺度
        b = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes and m.node_tree else None
        if b and b.inputs['Subsurface Weight'].default_value > 0: b.inputs['Subsurface Scale'].default_value = 0.004
    rig = bpy.data.objects[cid + '_rig']
    if os.environ.get('V11_REAL', '1') == '1': realism.enhance_character(rig)   # 皮肤毛孔、眼睛湿润、衣服褶皱
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down'))
    life.hands(rig, None)                                    # 手指自然微屈（不再五指笔直）
    bpy.context.view_layer.update()
    head = poses.head_pos(rig); face = head + Vector((0, -0.08, 0.04))
    shoot(sc, cam, os.path.join(OUT, cid + '_body.png'), (0, -4.6, 0.95), (0, 0, 0.88), 50, (600, 900))
    shoot(sc, cam, os.path.join(OUT, cid + '_face.png'), face + Vector((0, -0.75, 0.02)), face, 85, (600, 600), dof=4.0)
    a = math.radians(35)
    shoot(sc, cam, os.path.join(OUT, cid + '_face34.png'), face + Vector((0.75 * math.sin(a), -0.75 * math.cos(a), 0.02)), face, 85, (600, 600), dof=4.0)
    print('SHOWCASE OK', cid, flush=True)
