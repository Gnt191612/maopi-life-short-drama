# -*- coding: utf-8 -*-
"""鞋子目录：同一个人依次穿 shoes01~06，渲脚部 3/4 视角，挑选鞋型。
blender -b --factory-startup -P blender/tests/shoes_catalog.py"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy, addon_utils
addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from mathutils import Vector
OUT = os.path.join(config.RENDERS, 'shoes_catalog'); os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
sc = bpy.context.scene
body = HumanService.create_human(macro_detail_dict={'gender': 1.0, 'age': 0.44, 'muscle': 0.5, 'weight': 0.5, 'proportions': 0.5, 'height': 0.5,
                                                    'cupsize': 0.5, 'firmness': 0.5, 'race': {'asian': 1.0, 'caucasian': 0.0, 'african': 0.0}})
HumanService.add_mhclo_asset(os.path.join(config.mpfb_data(), 'clothes', 'male_casualsuit03', 'male_casualsuit03.mhclo'), body, asset_type='Clothes', set_up_rigging=False)
bpy.ops.mesh.primitive_plane_add(size=10)
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.5, 0.52, 1); sc.world = w
l = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA')); l.data.energy = 300; l.data.size = 2; l.location = (1.2, -1.5, 1.5)
l.rotation_euler = (Vector((0, 0, 0.1)) - l.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
t = Vector((0, -0.02, 0.10)); cam.location = t + Vector((0.55, -0.75, 0.30)); cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 480, 360
for k in range(1, 7):
    before = set(bpy.data.objects)
    HumanService.add_mhclo_asset(os.path.join(config.mpfb_data(), 'clothes', 'shoes%02d' % k, 'shoes%02d.mhclo' % k), body, asset_type='Clothes', set_up_rigging=False)
    sc.render.filepath = os.path.join(OUT, 'shoes%02d.png' % k); bpy.ops.render.render(write_still=True)
    for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
print('SHOES OK', flush=True)
