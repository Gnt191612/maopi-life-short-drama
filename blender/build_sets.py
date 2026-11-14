# -*- coding: utf-8 -*-
"""搭建全部场景白模：每个地点存 assets/sets/<name>.blend（含 marks 站位点），并渲染一张广角预览。
运行：blender -b --factory-startup -P build_sets.py [-- name ...]
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
import bpy
from mathutils import Vector
import sets

OUT = config.SETS; REN = os.path.join(config.RENDERS, 'sets')
os.makedirs(OUT, exist_ok=True); os.makedirs(REN, exist_ok=True)

def look_cam(name, loc, target, lens):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); bpy.context.scene.collection.objects.link(cam)
    cam.location = loc; cam.data.lens = lens; cam.data.clip_end = 400
    d = Vector(target) - Vector(loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam

def one(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sets._cube = None; sets._MATS.clear()
    info = sets.build(name)
    sc = bpy.context.scene
    sc['v11_marks'] = json.dumps(info['marks'])
    for k, (loc, tgt, lens) in info['cams'].items(): look_cam('cam_' + k, loc, tgt, lens)
    sc.camera = bpy.data.objects['cam_' + next(iter(info['cams']))]
    sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 640, 360
    sc.eevee.use_raytracing = True; sc.eevee.taa_render_samples = 32; sc.view_settings.view_transform = 'AgX'
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, name + '.blend'))
    sc.render.filepath = os.path.join(REN, name + '.png'); bpy.ops.render.render(write_still=True)
    print('SET OK', name, len(bpy.data.objects), 'objects', flush=True)

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for n in (argv or list(sets.BUILDERS)):
        try: one(n)
        except Exception as e:
            import traceback; print('SET FAIL', n, e, traceback.format_exc()[-600:], flush=True)
