# -*- coding: utf-8 -*-
"""多实例并行：给第 i 台实例打一个只含自己那份镜头素材的包（家里上行慢，不必每台都传全片）。
所有镜头的 task.json（很小）和 manifest 都保留——shard.py 按它们计算分配，必须和完整包算出来的一致。
用法：python cloud/shard_pack.py <i> <N>   → dist/cloud_pack_s<i>of<N>.zip"""
import os, sys, json, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shard
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
if sys.argv[1] == 'only':   # 试跑：python cloud/shard_pack.py only s02_01_0539,s09_01_0384 → 只带这几个镜头的素材（上行慢，不传全片）
    pre = [x for x in sys.argv[2].split(',') if x]
    mine = [t for t in json.load(open(os.path.join(PACK, 'manifest.json'), encoding='utf-8'))['tasks'] if any(t.startswith(p) for p in pre)]
    i, n = 0, 0
else:
    i, n = int(sys.argv[1]), int(sys.argv[2])
    mine = shard.assign(PACK, n)[0][i - 1]
man = json.load(open(os.path.join(PACK, 'manifest.json'), encoding='utf-8'))
need_refs = set()
out = os.path.join(ROOT, 'dist', 'cloud_pack_only.zip' if n == 0 else 'cloud_pack_s%dof%d.zip' % (i, n))
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    base = os.path.dirname(PACK)
    z.write(os.path.join(PACK, 'manifest.json'), os.path.relpath(os.path.join(PACK, 'manifest.json'), base))
    for t in man['tasks']:
        td = os.path.join(PACK, t)
        for f in os.listdir(td):
            if f == 'task.json' or t in mine: z.write(os.path.join(td, f), os.path.relpath(os.path.join(td, f), base))
        if t in mine: need_refs |= set(json.load(open(os.path.join(td, 'task.json'), encoding='utf-8')).get('characters', []))
    for f in os.listdir(os.path.join(PACK, 'refs')):
        if any(f.endswith('_%s.jpg' % c) for c in need_refs):
            z.write(os.path.join(PACK, 'refs', f), os.path.relpath(os.path.join(PACK, 'refs', f), base))
print('SHARD PACK', out, '%d 个镜头' % len(mine), '%.1f MB' % (os.path.getsize(out) / 1e6))
