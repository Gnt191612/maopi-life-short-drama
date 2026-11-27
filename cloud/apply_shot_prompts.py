# -*- coding: utf-8 -*-
"""把 cloud/shot_prompts.py（EN / EXTRA / CHARS）的改动直接写进已打包的 task.json，不用重新打包（重新打包要重渲白模）。
和 pack_for_cloud.py 拼提示词的格式一致：'<画面描述>. Background: <场景>. <运镜>. <风格>'，只替换第一段。
用法：python cloud/apply_shot_prompts.py [打包目录，默认 dist/cloud_pack]   之后再跑 visible_cast.py --write、shot_audio.py"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import shot_prompts as SP
pack = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dist', 'cloud_pack')
n = 0
for tp in sorted(glob.glob(os.path.join(pack, 's*_*_*', 'task.json'))):
    t = json.load(open(tp, encoding='utf-8')); tid = t['id']; old = json.dumps(t, sort_keys=True)
    if tid in SP.EN:
        rest = t['prompt'].split('. Background:', 1)[1] if '. Background:' in t['prompt'] else ''
        t['prompt'] = SP.EN[tid] + ('. Background:' + rest if rest else '')
    if tid in SP.CHARS: t['characters'] = SP.CHARS[tid]
    t.update(SP.EXTRA.get(tid, {}))
    if json.dumps(t, sort_keys=True) != old:
        json.dump(t, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); n += 1
print('更新 %d 个 task.json' % n)
