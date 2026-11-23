# -*- coding: utf-8 -*-
"""快速审片：打开已搭好的片段（shoot_segment.py --norender 生成的 build/shots/<seg>.blend），每个镜头渲开头、中间两帧（960x540），
输出 build/review/<seg>/<镜头起始帧>_a.png / _b.png。比渲全部帧快几十倍，改了拍摄逻辑先用它看一遍。
blender -b build/shots/<seg>.blend --factory-startup -P blender/tests/shot_review.py -- <seg>"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
import bpy
seg = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
out = os.path.join(config.ROOT, 'build', 'review', seg); os.makedirs(out, exist_ok=True)
cuts = json.load(open(os.path.join(config.SHOTS, seg + '_cuts.json'), encoding='utf-8'))
bounds = [c[0] for c in cuts] + [sc.frame_end + 1]
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
sc.render.image_settings.file_format = 'PNG'
if sc.render.engine.startswith('BLENDER_EEVEE'): sc.eevee.taa_render_samples = 16
for k, c in enumerate(cuts):
    f0, cam = c[0], c[1]
    f1 = bounds[k + 1] - 1
    for tag, f in (('a', f0), ('b', (f0 + f1) // 2)):
        sc.frame_set(f); sc.render.filepath = os.path.join(out, '%04d_%s.png' % (f0, tag)); bpy.ops.render.render(write_still=True)
    print('REVIEW', seg, f0, cam, flush=True)
print('REVIEW DONE', seg, len(cuts))
