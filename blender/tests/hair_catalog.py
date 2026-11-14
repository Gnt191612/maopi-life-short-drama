# -*- coding: utf-8 -*-
"""发型目录：建一个标准青年男性头模，逐款套上发型素材（.mhclo），各渲正面 + 3/4 侧面，用于挑选发型。
blender -b --factory-startup -P blender/tests/hair_catalog.py -- <发型素材根目录> [性别 1=男 0=女]"""
import os, sys, math, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy, addon_utils
addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
root = argv[0]; gender = float(argv[1]) if len(argv) > 1 else 1.0
OUT = os.path.join(config.RENDERS, 'hair_catalog'); os.makedirs(OUT, exist_ok=True)
items = sorted(glob.glob(os.path.join(root, '**', '*.mhclo'), recursive=True))
print('CATALOG', len(items), 'hair assets', flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
sc = bpy.context.scene
body = HumanService.create_human(macro_detail_dict={'gender': gender, 'age': 0.44, 'muscle': 0.5, 'weight': 0.5, 'proportions': 0.5, 'height': 0.5,
                                                    'cupsize': 0.5, 'firmness': 0.5, 'race': {'asian': 1.0, 'caucasian': 0.0, 'african': 0.0}})
skin = 'young_asian_male' if gender > 0.5 else 'young_asian_female'
HumanService.set_character_skin(os.path.join(config.mpfb_data(), 'skins', skin, skin + '.mhmat'), body, skin_type='ENHANCED_SSS')
for rel in ('eyes/high-poly/high-poly.mhclo', 'eyebrows/eyebrow005/eyebrow005.mhclo'):
    HumanService.add_mhclo_asset(os.path.join(config.mpfb_data(), rel), body, asset_type='Eyes' if 'eyes' in rel else 'Eyebrows', set_up_rigging=False)
top = max((body.matrix_world @ v.co).z for v in body.data.vertices)
face = Vector((0, -0.06, top - 0.12))
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.18, 0.18, 0.19, 1); sc.world = w
for name, loc, e in (('key', (0.8, -1.2, top + 0.4), 140), ('fill', (-1.0, -0.9, top), 60), ('rim', (0, 1.0, top + 0.5), 120)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); l.data.energy = e; l.data.size = 1.2; l.location = loc
    l.rotation_euler = (face - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 70
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
for d in prefs.devices: d.use = (d.type == 'OPTIX')
sc.cycles.samples = 48; sc.cycles.use_denoising = True; sc.view_settings.view_transform = 'AgX'
sc.render.resolution_x = sc.render.resolution_y = 400
for path in items:
    name = os.path.splitext(os.path.basename(path))[0]
    if os.path.exists(os.path.join(OUT, name + '_34.png')): continue
    before = set(bpy.data.objects)
    try:
        HumanService.add_mhclo_asset(path, body, asset_type='Clothes', set_up_rigging=False)
    except Exception as e:
        print('CATALOG FAIL', name, e, flush=True); continue
    for view, ang in (('front', 0), ('34', 35)):
        a = math.radians(ang); cam.location = face + Vector((0.95 * math.sin(a), -0.95 * math.cos(a), 0.05))
        cam.rotation_euler = (face - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (name, view)); bpy.ops.render.render(write_still=True)
    for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
    print('CATALOG OK', name, flush=True)
