# -*- coding: utf-8 -*-
"""角色长相候选（在仙宫云 Krea2 镜像实例上运行）：白模正脸 →「二转三」写实化，每人用不同随机种子出几张，供用户挑定标准长相。
输出 /root/v11_out/cand_<cid>_<k>.png。用法：python3 candidates.py <张数> <角色id ...>"""
import sys
sys.path.insert(0, '/root')
import comfy_run
from identity_run import LOOK
n = int(sys.argv[1])
for cid in sys.argv[2:]:
    for k in range(1, n + 1):
        comfy_run.run('Krea2-二转三-图生图-新版.json', 'cand_%s_%d' % (cid, k),
                      {'10.image': cid + '_face_front.png', '1.seed': 1000 * k + 7}, prefix=LOOK[cid])
print('CANDIDATES DONE', flush=True)
