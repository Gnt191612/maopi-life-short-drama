# -*- coding: utf-8 -*-
"""抽帧检查：打开拍好的片段，按 EEVEE 预览画质渲染指定帧（或每拍的首/中/尾帧）。
blender -b --factory-startup -P blender/tests/render_frames.py -- <seg_id> <输出目录> [帧号 ...]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy

argv = sys.argv[sys.argv.index('--') + 1:]
seg, out = argv[0], argv[1]; frames = [int(a) for a in argv[2:]]
bpy.ops.wm.open_mainfile(filepath=os.path.join(config.SHOTS, seg + '.blend'))
sc = bpy.context.scene
if not frames:
    tl = json.load(open(os.path.join(config.SHOTS, seg + '_timeline.json'), encoding='utf-8'))
    for b in tl: frames += [b['f0'] + 2, (b['f0'] + b['f1']) // 2, b['f1'] - 1]
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = 640, 360
sc.use_nodes = False
os.makedirs(out, exist_ok=True)
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, '%s_%04d.png' % (seg, f))
    bpy.ops.render.render(write_still=True)
print('FRAMES', seg, frames, flush=True)
