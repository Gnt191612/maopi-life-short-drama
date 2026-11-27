# -*- coding: utf-8 -*-
"""每个镜头的配音轨（本地，给云端口型同步用）：按 run_all.previs 相同的时间算法，把落在这个镜头里的台词放到对应时刻，其余静音，
写成 dist/cloud_pack/<任务id>/voice.wav（16kHz 单声道），同时写 voice.json（说话人、台词、在镜头内的起止秒）。
只做「一个说话人、他就是画面里的角色」的镜头；多人镜头里口型同步模型只会改最大的那张脸，说话人不是最大脸时会对错嘴，跳过并列出。
用法：python cloud/shot_audio.py [任务id ...]   （不给 id = 全部有台词的镜头）"""
import os, sys, json, glob, wave, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import config, segments as S
from looks import NAME
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); SR = 16000
CID = {v: k for k, v in NAME.items()}
def load(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2: a = a.reshape(-1, 2).mean(1)
        sr = w.getframerate()
    return np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a) if sr != SR else a
want = sys.argv[1:]
tasks = {}
for tj in glob.glob(os.path.join(PACK, '*', 'task.json')):
    t = json.load(open(tj, encoding='utf-8')); tasks.setdefault(t['segment'], []).append(t)
made, skipped = [], []
for sid in [s[0] for s in S.segments()]:
    tlp = os.path.join(config.SHOTS, sid + '_timeline.json')
    if not os.path.exists(tlp): continue
    lines = [(fr, lid) for b in json.load(open(tlp, encoding='utf-8')) for fr, lid in b['audio'] if not lid.startswith('X') and lid in S.TEXT]
    for t in tasks.get(sid, []):
        if want and t['id'] not in want: continue
        f0, f1 = t['frames']; mine = [(fr, lid) for fr, lid in lines if f0 <= fr <= f1]
        if not mine: continue
        spk = {CID.get(S.TEXT[lid][0]) for _, lid in mine}
        if len(spk) != 1 or (t['characters'] and len(t['characters']) > 1) or (spk - set(t['characters'])):
            skipped.append((t['id'], [S.TEXT[l][0] for _, l in mine], t['characters'])); continue
        buf = np.zeros(int((f1 - f0 + 1) / 24.0 * SR) + SR, np.float32); meta = []
        for fr, lid in mine:
            a = load(os.path.join(S.AUD, lid + '.wav')); i = int((fr - f0) / 24.0 * SR); buf[i:i + len(a)] += a[:max(0, len(buf) - i)]
            meta.append(dict(lid=lid, speaker=S.TEXT[lid][0], text=S.TEXT[lid][1], start=round((fr - f0) / 24.0, 2), dur=round(len(a) / SR, 2)))
        buf = buf[:int((f1 - f0 + 1) / 24.0 * SR)]
        op = os.path.join(PACK, t['id'], 'voice.wav')
        with wave.open(op, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
        json.dump(meta, open(os.path.join(PACK, t['id'], 'voice.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        made.append(t['id'])
print('配音轨 %d 个：%s' % (len(made), ' '.join(made)))
print('跳过（多人或说话人不在画面里）%d 个：' % len(skipped)); [print('  ', s) for s in skipped]
