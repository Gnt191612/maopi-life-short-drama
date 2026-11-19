# -*- coding: utf-8 -*-
"""锁定角色长相 v2（在仙宫云 Krea2 镜像实例上运行）：长相标准由用户从候选里挑定（/root/ComfyUI/input/canon_<cid>.png）。
每个机位：1) 白模 →「二转三」写实化（保住构图、姿势、服装）→ base_<cid>_<view>.png；
         2)「Qwen2.1-人物替换」：图1 = 标准长相，图2 = 第 1 步的照片 → swap_<cid>_<view>.png（照片换照片，最自然）。
用法：python3 identity_swap.py <cid> [机位 ...]"""
import sys, shutil, os
sys.path.insert(0, '/root')
import comfy_run
from identity_run import LOOK
HAIR = {'classB': '发型使用图1：乌黑长发中分、全部向后梳成低马尾，戴黑色发箍，没有刘海。'}
cid = sys.argv[1]; views = sys.argv[2:] or ['face_front', 'face_34', 'half', 'full']
SWAP = ('使用图1中的人物替换图2中的人物，置于同一画面位置。长相与图1完全相同，是同一个人（五官、脸型、眉眼、肤色一致）。'
        '保持图2的姿势、表情、构图、景别、服装和光影不变。{hair}')
for v in views:
    base = '/root/v11_out/base_%s_%s.png' % (cid, v)
    if not os.path.exists(base):
        base = comfy_run.run('Krea2-二转三-图生图-新版.json', 'base_%s_%s' % (cid, v), {'10.image': '%s_%s.png' % (cid, v)}, prefix=LOOK[cid])
    if not base: continue
    shutil.copy(base, '/root/ComfyUI/input/base_%s_%s.png' % (cid, v))
    comfy_run.run('【推荐】Qwen2.1-人物替换.json', 'swap_%s_%s' % (cid, v),
                  {'3.image': 'canon_%s.png' % cid, '10.image': 'base_%s_%s.png' % (cid, v), '39.text': SWAP.format(hair=HAIR.get(cid, ''))})
print('SWAP DONE', flush=True)
