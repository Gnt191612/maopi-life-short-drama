# -*- coding: utf-8 -*-
"""锚点模式素材（本地运行，免费）：给指定镜头每隔约 4 秒取一帧白模、再加上最后一帧，按原机位渲 1920×1080，
写进 dist/cloud_pack/<任务id>/anchor_<帧号>.png + anchors.json（首帧同时覆盖 first.png）。
云端 keyframes.py 给每个锚点出一张写实图，video_run.py 用相邻两个锚点做首尾帧控制，视频每隔几秒被拉回白模的位置和姿势，
不会越跑越偏（2026-11-25：纯图生视频的镜头里，坐在上铺的人后来站到了地上、拍着拍着换了个房间）。
用法：python cloud/make_anchors.py <任务id,任务id,...> [--step 96]"""
import os, sys, json, glob, shutil, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import config
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
STEP = int(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 96   # 24fps 下 96 帧 = 4 秒 = Wan 16fps 的 64 帧（6 的倍数，换算后正好 4k）

def anchors(f0, f1):
    a = list(range(f0, f1, STEP))
    if f1 - a[-1] < 30 and len(a) > 1: a.pop()   # 最后一段太短（<1.25 秒）就并进前一段
    return a + [f1]

def main():
    ids = [x for x in sys.argv[1].split(',') if x]
    by_seg = {}
    for tid in ids:
        tj = os.path.join(PACK, tid, 'task.json')
        if not os.path.exists(tj): print('没有任务', tid); continue
        t = json.load(open(tj, encoding='utf-8')); by_seg.setdefault(t['segment'], []).append((tid, anchors(*t['frames'])))
    for seg, jobs in by_seg.items():
        blend = os.path.join(config.SHOTS, seg + '.blend')
        if not os.path.exists(blend):   # 片段 .blend 被删过：只搭场景不渲染（几分钟）
            subprocess.run([config.BLENDER, '-b', '--factory-startup', '-P', os.path.join(config.BLENDER_SCRIPTS, 'shoot_segment.py'), '--', seg, '--norender'],
                           env=config.blender_env(), capture_output=True)
        if not os.path.exists(blend): print('搭不出片段', seg); continue
        tmp = os.path.join(PACK, '_anchor_' + seg)
        frames = sorted({f for _, a in jobs for f in a})
        subprocess.run([config.BLENDER, '-b', blend, '--factory-startup', '-P', os.path.join(ROOT, 'cloud', 'render_first.py'), '--', tmp] + [str(f) for f in frames],
                       env=config.blender_env(), capture_output=True)
        for tid, a in jobs:
            td = os.path.join(PACK, tid); ok = []
            for f in a:
                src = os.path.join(tmp, 'first_%04d.png' % f)
                if not os.path.exists(src): continue
                shutil.copy(src, os.path.join(td, 'anchor_%04d.png' % f)); ok.append(f)
                if f == a[0]: shutil.copy(src, os.path.join(td, 'first.png'))
            if len(ok) == len(a): json.dump(a, open(os.path.join(td, 'anchors.json'), 'w')); print('ANCHORS', tid, a, flush=True)
            else: print('锚点没渲全', tid, a, ok, flush=True)
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
