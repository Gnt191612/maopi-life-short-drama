# -*- coding: utf-8 -*-
"""搭建并渲染一个地点片段：blender -b --factory-startup -P blender/shoot_segment.py -- <seg_id> [--step N] [--norender]
输出（均在 build/ 下，可随时重新生成）：
  shots/<seg>.blend            完整动画白模（云端可直接重渲任意图层）
  renders/<seg>/beauty_####.png 白模画面；depth_####.png 深度控制图
  shots/<seg>_timeline.json    各拍起止帧、台词帧位置
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
import bpy
import shoot
from segments import segments

argv = sys.argv[sys.argv.index('--') + 1:]
seg_id = argv[0]; step = int(argv[argv.index('--step') + 1]) if '--step' in argv else 1
norender = '--norender' in argv
seg = next(x for x in segments() if x[0] == seg_id)
t0 = time.time()
timeline = shoot.build_segment(*seg)
json.dump(timeline, open(os.path.join(config.SHOTS, seg_id + '_timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
# 镜头切换点（每台机位从哪一帧开始用）——云端按镜头切分任务
cuts = sorted(((m.frame, m.camera.name, m.camera.get('move', 'static')) for m in bpy.context.scene.timeline_markers if m.camera), key=lambda c: c[0])   # 第三项：运镜方式（云端提示词用）
json.dump(cuts, open(os.path.join(config.SHOTS, seg_id + '_cuts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
out = os.path.join(config.RENDERS, seg_id); os.makedirs(out, exist_ok=True)
shoot.setup_render(out)
bpy.context.scene.frame_step = step
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(config.SHOTS, seg_id + '.blend'))
print('SEGMENT BUILT', seg_id, 'frames', bpy.context.scene.frame_end, '%.0fs' % (time.time() - t0), flush=True)
if not norender:
    bpy.ops.render.render(animation=True)
    print('SEGMENT RENDERED', seg_id, '%.0fs' % (time.time() - t0), flush=True)
