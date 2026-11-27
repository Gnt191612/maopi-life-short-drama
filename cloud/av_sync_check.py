# -*- coding: utf-8 -*-
"""音画同步客观检查（本地）：每个单人说话镜头，逐帧量说话人的嘴张开幅度（InsightFace 106/68 点内唇距离 ÷ 脸高），
和配音轨 voice.wav 的音量包络（每 1/24 秒）做互相关，得出：
  lag   = 嘴型比声音晚几帧（正数=嘴慢，负数=嘴快；|lag|>2 帧肉眼就能看出来）
  corr  = 对上的程度（0～1，越高越同步；<0.3 基本没对上）
  mute  = 有声音时嘴闭着的帧占比（>40% 就是「说话不张嘴」）
2026-11-27：用户指出旧版视频音频对不上，尤其角色语音和动作、口型对不上；新方案（白模动作控制 + LatentSync）做完必须用它验收。
用法：python cloud/av_sync_check.py <结果目录（含 real/<任务id>.mp4）> [任务id ...]  → build/review/av_sync.json + 控制台表格"""
import os, sys, json, glob, wave, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import torch  # noqa: F401
from insightface.app import FaceAnalysis
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'], allowed_modules=['detection', 'landmark_2d_106']); app.prepare(ctx_id=0, det_size=(640, 640))
# 106 点模型的内唇上下中点（insightface 2d106det：上唇内缘 71、下唇内缘 53 附近；取一组点做均值更稳）
UP, LO = [71, 63, 65], [53, 59, 57]

def env(wav, n):
    with wave.open(wav) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; sr = w.getframerate()
    hop = sr / 24.0; e = np.array([np.sqrt(np.mean(a[int(i * hop):int((i + 1) * hop)] ** 2) + 1e-9) for i in range(n)])
    return e / (e.max() + 1e-9)

def mouth(video):
    c = cv2.VideoCapture(video); out = []
    while True:
        ok, im = c.read()
        if not ok: break
        fs = app.get(im)
        if not fs: out.append(np.nan); continue
        f = max(fs, key=lambda x: x.bbox[2] - x.bbox[0]); p = f.landmark_2d_106
        h = f.bbox[3] - f.bbox[1]
        out.append(float(np.mean(p[LO, 1]) - np.mean(p[UP, 1])) / max(h, 1))
    m = np.array(out); ok = ~np.isnan(m)
    if ok.sum() < 5: return m, ok
    m[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), m[ok])
    return m, ok

res_dir = sys.argv[1]; want = sys.argv[2:]; rows = []
for vj in sorted(glob.glob(os.path.join(PACK, '*', 'voice.json'))):
    tid = os.path.basename(os.path.dirname(vj))
    if want and tid not in want: continue
    v = os.path.join(res_dir, 'real', tid + '.mp4')
    if not os.path.exists(v): v = os.path.join(res_dir, tid + '.mp4')
    if not os.path.exists(v): continue
    m, ok = mouth(v); n = len(m)
    if n < 10 or ok.mean() < 0.3: rows.append(dict(id=tid, note='脸检测不到（侧脸/背影/远景）', face=round(float(ok.mean()), 2))); continue
    e = env(os.path.join(PACK, tid, 'voice.wav'), n)
    mz = (m - m.mean()) / (m.std() + 1e-9); ez = (e - e.mean()) / (e.std() + 1e-9)
    best = max(range(-8, 9), key=lambda L: np.mean(mz[max(0, L):n + min(0, L)] * ez[max(0, -L):n - max(0, L)]))
    corr = float(np.mean(mz[max(0, best):n + min(0, best)] * ez[max(0, -best):n - max(0, best)]))
    speak = e > 0.25; closed = m < np.percentile(m, 30) + 0.25 * (np.percentile(m, 90) - np.percentile(m, 30))
    mute = float((speak & closed).sum() / max(1, speak.sum()))
    rows.append(dict(id=tid, lag=best, corr=round(corr, 2), mute=round(mute, 2), face=round(float(ok.mean()), 2)))
    r = rows[-1]; bad = abs(best) > 2 or corr < 0.3 or mute > 0.4
    print('%-12s lag %+d 帧  corr %.2f  说话不张嘴 %3.0f%%  脸检出 %3.0f%%  %s' % (tid, best, corr, mute * 100, ok.mean() * 100, '✗' if bad else '✓'), flush=True)
out = os.path.join(ROOT, 'build', 'review', 'av_sync.json'); json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
good = [r for r in rows if 'corr' in r and abs(r['lag']) <= 2 and r['corr'] >= 0.3 and r['mute'] <= 0.4]
print('合格 %d / 可测 %d / 共 %d（标准：|lag|≤2 帧、corr≥0.3、说话不张嘴≤40%%）' % (len(good), sum(1 for r in rows if 'corr' in r), len(rows)))
