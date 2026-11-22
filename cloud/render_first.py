# -*- coding: utf-8 -*-
"""给云端写实关键帧补渲高清首帧（本地 Blender 运行，免费）：预览画质只有 640×360，二转三工作流放大到 200 万像素后很糊，
模型会「脑补」出第二个人（2026-11-22 试片）。这里打开已拍好的片段 .blend，按原机位渲 1920×1080 单帧。
blender -b build/shots/<片段>.blend --factory-startup -P cloud/render_first.py -- <输出目录> <帧号> [帧号 ...]
输出 <输出目录>/first_<帧号>.png"""
import sys, os
import bpy
a = sys.argv[sys.argv.index('--') + 1:]
out, frames = a[0], [int(x) for x in a[1:]]
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
sc.render.image_settings.file_format = 'PNG'
if sc.render.engine.startswith('BLENDER_EEVEE'): sc.eevee.taa_render_samples = max(32, sc.eevee.taa_render_samples)
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, 'first_%04d.png' % f)
    bpy.ops.render.render(write_still=True)
    print('FIRST OK', f, flush=True)
