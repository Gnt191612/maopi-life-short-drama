# -*- coding: utf-8 -*-
"""二转三对照实验（云端）：采样起始步（KSamplerAdvanced 21 共 8 步）往后挪 = 图生图，保留白模构图，只重绘质感。
python3 exp_real.py <输入图文件名>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
src = sys.argv[1]
for st in (2, 3, 4):
    comfy_run.run('Krea2-二转三-图生图-新版.json', 'exp_s%d' % st, {'10.image': src, '1.seed': 7, '21.start_at_step': st})
print('EXP DONE', flush=True)
