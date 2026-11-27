# -*- coding: utf-8 -*-
"""多实例并行：把镜头任务按时长均衡分成 N 份（贪心：从长到短，每次放进当前总时长最短的那份），结果确定可复现。
环境变量 V11_SHARD="i/N"（i 从 1 开始）；不设 = 全部任务。keyframes.py 用。
本地查看分配：python cloud/shard.py <cloud_pack 目录> N"""
import os, sys, json

def parse():
    s = os.environ.get('V11_SHARD', '').strip()
    if not s or '/' not in s: return 1, 1
    i, n = s.split('/'); return int(i), int(n)

def assign(pack, n):
    man = json.load(open(os.path.join(pack, 'manifest.json'), encoding='utf-8'))
    dur = {}
    for t in man['tasks']:
        try: dur[t] = json.load(open(os.path.join(pack, t, 'task.json'), encoding='utf-8'))['n']
        except Exception: dur[t] = 1
    bins = [[0, []] for _ in range(n)]
    for t in sorted(man['tasks'], key=lambda t: -dur[t]):
        b = min(bins, key=lambda b: b[0]); b[0] += dur[t]; b[1].append(t)
    return [set(b[1]) for b in bins], [b[0] for b in bins]

def mine(pack):
    """本实例负责的任务 id 集合（不分片时返回 None = 全部）"""
    i, n = parse()
    if n <= 1: return None
    return assign(pack, n)[0][i - 1]

if __name__ == '__main__':
    sets, frames = assign(sys.argv[1], int(sys.argv[2]))
    for k, (s, f) in enumerate(zip(sets, frames), 1):
        print('实例 %d：%d 个镜头，%d 帧（%.1f 分钟）' % (k, len(s), f, f / 24 / 60))
