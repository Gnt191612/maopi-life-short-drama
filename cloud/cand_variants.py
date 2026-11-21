# -*- coding: utf-8 -*-
"""角色长相候选（不同外貌方向）：每张候选单独写外貌描述，白模正脸 →「二转三」写实化。
用法：python3 cand_variants.py <方案文件.json>
方案文件：[{"name": "lin_A", "cid": "lin", "look": "一位……，", "seed": 101}, ...] → /root/v11_out/cand_<name>.png"""
import sys, json
sys.path.insert(0, '/root')
import comfy_run
for v in json.load(open(sys.argv[1], encoding='utf-8')):
    comfy_run.run('Krea2-二转三-图生图-新版.json', 'cand_' + v['name'],
                  {'10.image': v['cid'] + '_face_front.png', '1.seed': v.get('seed', 1007)}, prefix=v['look'])
print('VARIANTS DONE', flush=True)
