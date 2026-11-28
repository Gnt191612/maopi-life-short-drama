# -*- coding: utf-8 -*-
"""合成前的后期修正（11-27）：按 cloud/postfix_text.json 处理拆好帧的写实镜头（<结果>/real/<id>/frame_####.png）
  phone  ：手机屏幕文字——逐帧用白模渲染的正确屏幕文字贴回（phone_screen_fix.fix，跟着手机移动、避开拇指）
  notice ：白纸文字（闭馆通知）——逐帧在写实画面里找纸、按透视排版（phone_screen_fix.notice_on_real）
  grade  ：回忆镜头调色（cold 冷蓝 / warm 暖金），整段统一（以前让模型画色调，和首帧打架）
第一次处理前把原帧备份到 <镜头>/_orig_post/，之后每次都从备份重做（可重复运行）。make_final.ps1 在拆帧后自动调用。
用法：python cloud/postfix_apply.py <结果目录>/real"""
import os, sys, json, glob, shutil
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import phone_screen_fix as P
real = sys.argv[1]; CFG = json.load(open(os.path.join(HERE, 'postfix_text.json'), encoding='utf-8'))

def frames(tid):
    d = os.path.join(real, tid); fs = sorted(glob.glob(os.path.join(d, 'frame_*.png')))
    if not fs: return None, []
    bk = os.path.join(d, '_orig_post'); os.makedirs(bk, exist_ok=True)
    for f in fs:
        b = os.path.join(bk, os.path.basename(f))
        if not os.path.exists(b): shutil.copy(f, b)
    return bk, fs

def grade(im, kind):
    f = im.astype(np.float32)
    if kind == 'cold':   # 冷蓝：压红、提蓝、略降饱和和亮度（夜里回忆）
        g = f.mean(2, keepdims=True); f = f * 0.8 + g * 0.2
        f[..., 2] *= 0.82; f[..., 1] *= 0.95; f[..., 0] = f[..., 0] * 1.12 + 6; f *= 0.92
    else:                 # 暖金：提红黄、压蓝、略提亮（温暖的回忆）
        f[..., 2] = f[..., 2] * 1.08 + 8; f[..., 1] *= 1.03; f[..., 0] *= 0.86; f = f * 1.03 + 4
    return np.clip(f, 0, 255).astype(np.uint8)

done = []
for tid in CFG.get('phone', []):
    bk, fs = frames(tid)
    if not fs: continue
    G = P.frames_of(os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'beauty.mp4')); M = None
    for i, f in enumerate(fs):
        r = cv2.imread(os.path.join(bk, os.path.basename(f))); o, M = P.fix(r, G[min(i, len(G) - 1)], M); cv2.imwrite(f, o)
    done.append(tid + '（手机文字）')
for tid, lines in CFG.get('notice', {}).items():
    bk, fs = frames(tid)
    if not fs: continue
    q = None
    for f in fs:
        r = cv2.imread(os.path.join(bk, os.path.basename(f))); o, q = P.notice_on_real(r, lines, q); cv2.imwrite(f, o)
    done.append(tid + '（通知文字）')
for kind, ids in CFG.get('grade', {}).items():
    for tid in ids:
        bk, fs = frames(tid)
        if not fs: continue
        for f in fs:
            src = cv2.imread(f) if tid in CFG.get('phone', []) else cv2.imread(os.path.join(bk, os.path.basename(f)))   # 手机镜头先贴字再调色
            cv2.imwrite(f, grade(src, kind))
        done.append(tid + '（%s调色）' % ('冷蓝' if kind == 'cold' else '暖金'))
# ---- 按场景统一调色（11-27 用户：同一场戏连在一起要看得出是同一场景同一时间）----
# 同一片段里每个镜头的 Lab 均值向本段中位数靠拢 60%（只平移、不改对比），手机屏幕特写和回忆调色镜头不参与（各有各的样子）
SKIP = set(CFG.get('phone', [])) | {t for ids in CFG.get('grade', {}).values() for t in ids} | set(CFG.get('notice', {}))
segs = {}
for d in sorted(glob.glob(os.path.join(real, 's*_*_*'))):
    tid = os.path.basename(d)
    if os.path.isdir(d) and tid not in SKIP and glob.glob(os.path.join(d, 'frame_*.png')): segs.setdefault(tid.rsplit('_', 1)[0], []).append(tid)
def mean_lab(tid):
    bk, fs = frames(tid); pick = fs[len(fs) // 4::max(1, len(fs) // 4)][:3] or fs[:1]
    return np.mean([cv2.cvtColor(cv2.imread(os.path.join(bk, os.path.basename(f))), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32).mean(0) for f in pick], axis=0)
nm = 0
for seg, ids in segs.items():
    if len(ids) < 2: continue
    means = {t: mean_lab(t) for t in ids}; target = np.median(np.array(list(means.values())), axis=0)
    for t in ids:
        shift = (target - means[t]) * 0.6
        if np.abs(shift).max() < 2: continue   # 差得很少就不动
        bk, fs = frames(t)
        for f in fs:
            src = cv2.imread(os.path.join(bk, os.path.basename(f)))   # 从备份原帧算（参与调色的镜头没有别的修正），重复运行不会叠加
            lab = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32) + shift
            cv2.imwrite(f, cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR))
        nm += 1
print('后期修正 %d 项：%s；按场景统一调色 %d 个镜头' % (len(done), ' '.join(done), nm))
