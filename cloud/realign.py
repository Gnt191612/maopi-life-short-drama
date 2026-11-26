# -*- coding: utf-8 -*-
"""写实画面按最新时间轴重对齐（本地，合成前自动跑）：
写实帧按「片段内帧号」存放（real/<片段>_<起始帧>/frame_####.png）。如果之后调整了节奏（某拍加长/缩短、白模重拍后时间轴变了），
旧帧号就会和新时间轴、新配音字幕错位（2026-11-25 用户要求：节奏调整后的片段也要能正确对齐）。
做法：<结果目录>/timelines/ 存着「写实画面是按哪个时间轴做的」快照；和 build/shots/<片段>_timeline.json 逐拍比较，
长度变了的拍按比例重新铺满新长度（变长均匀补帧，变短均匀抽帧），新增的拍没有写实画面就留给白模补，
结果写进 real/<片段>_aligned/，原来的镜头目录挪到 stale/，再把新时间轴存成快照。
用法：python cloud/realign.py <结果目录>            第一次运行（没有快照）只建快照
      python cloud/realign.py <结果目录> --check    只报告哪些片段节奏变了，不改文件"""
import os, sys, json, glob, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import config
res = sys.argv[1]; check = '--check' in sys.argv
real = os.path.join(res, 'real'); snap = os.path.join(res, 'timelines'); stale = os.path.join(res, 'stale')
os.makedirs(snap, exist_ok=True)

def beats(path):
    return {b['id']: (b['f0'], b['f1']) for b in json.load(open(path, encoding='utf-8'))}

changed = []
for cur in sorted(glob.glob(os.path.join(config.SHOTS, '*_timeline.json'))):
    sid = os.path.basename(cur)[:-14]; sp = os.path.join(snap, os.path.basename(cur))
    if not os.path.exists(sp):
        shutil.copy(cur, sp); continue
    old, new = beats(sp), beats(cur)
    if old == new: continue
    changed.append(sid)
    diffs = [(b, old.get(b), new[b]) for b in new if old.get(b) != new[b]]
    print('节奏变了', sid, '共 %d 拍' % len(diffs), diffs[:4], flush=True)
    if check: continue
    frames = {}
    for d in glob.glob(os.path.join(real, sid + '_*')):
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, 'frame_*.png')): frames[int(f[-8:-4])] = f
    out = os.path.join(real, sid + '_aligned_tmp'); os.makedirs(out, exist_ok=True); n = 0
    for b, (n0, n1) in new.items():
        if b not in old: continue                          # 新增的拍：没有写实画面，合成时用白模补
        o0, o1 = old[b]; nl, ol = n1 - n0 + 1, o1 - o0 + 1
        for k in range(nl):
            src = frames.get(o0 + (round(k * (ol - 1) / (nl - 1)) if nl > 1 else 0))
            if src: shutil.copy(src, os.path.join(out, 'frame_%04d.png' % (n0 + k))); n += 1
    os.makedirs(stale, exist_ok=True)
    for d in glob.glob(os.path.join(real, sid + '_*')):
        if d != out and os.path.isdir(d): shutil.move(d, os.path.join(stale, os.path.basename(d)))
        elif d.endswith('.mp4'): shutil.move(d, os.path.join(stale, os.path.basename(d)))
    os.replace(out, os.path.join(real, sid + '_aligned'))
    shutil.copy(cur, sp)
    print('已重对齐', sid, '写实帧 %d' % n, flush=True)
print('REALIGN', '无变化' if not changed else '变化片段：' + ','.join(changed), flush=True)
