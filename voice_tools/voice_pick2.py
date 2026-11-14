# -*- coding: utf-8 -*-
"""v11 音色自动挑选：对 voices_v2/ 的 Spark-TTS 候选逐个打分，写 voices_v2/pick.json（tts11.py 使用）。
打分项（越高越好）：
  - 清晰度：whisper 识别字错率低、平均对数概率高（含糊、电音、喉音重的会被识别得差）
  - 音高贴合角色：中位基频接近 TARGET_F0（青年男 / 中年男 / 中年女 / 青年女），男主不要尖、长辈不要嫩
  - 有起伏：基频起伏 2~4.5 半音最自然，太平像念稿，太大像夸张播音
  - 干净：谐波噪声比（HNR）高，嘶哑、沙沙声少
  - 各角色之间音色要拉开：说话人特征（MFCC 均值）与已选角色太像的扣分
运行：<IndexTTS2 环境的 python> voice_tools/voice_pick2.py
"""
import os, sys, json, glob, re
import numpy as np, librosa
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__)); VOI = os.path.join(HERE, 'voices_v2')
sys.path.insert(0, HERE)
from tts11 import cer

TARGET_F0 = {'林晓': 135, '陈瑶': 118, '周明远': 112, '王老师': 108, '林母': 205, '同学甲': 140, '同学乙': 235}
# 先挑主角，后挑配角（配角要避开主角的音色）
ORDER = ['林晓', '陈瑶', '周明远', '王老师', '林母', '同学甲', '同学乙']

def hnr(y, sr):
    h, p = librosa.effects.hpss(y)
    return 10 * np.log10((h ** 2).sum() / ((p ** 2).sum() + 1e-9))

def main():
    import whisper
    asr = whisper.load_model('small', device='cuda')
    meta = json.load(open(os.path.join(VOI, 'voices.json'), encoding='utf-8'))
    feats = {}
    for name, m in meta.items():
        p = os.path.join(VOI, name + '.wav'); y, sr = librosa.load(p, sr=16000)
        f0, _, _ = librosa.pyin(y, fmin=60, fmax=500, sr=sr); f = f0[~np.isnan(f0)]
        if len(f) < 20: continue
        r = asr.transcribe(y.astype('float32'), language='zh', initial_prompt='以下是普通话的句子。')
        lp = np.mean([s['avg_logprob'] for s in r['segments']]) if r['segments'] else -2
        mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)[1:].mean(1)
        feats[name] = dict(role=m['role'], f0=float(np.median(f)), var=float((12 * np.log2(f / np.median(f))).std()),
                           cer=cer(m['text'], r['text']), lp=float(lp), hnr=float(hnr(y, sr)), mfcc=mf)
        print(name, 'F0=%d 起伏=%.1f cer=%.2f lp=%.2f hnr=%.1f' % (feats[name]['f0'], feats[name]['var'], feats[name]['cer'], lp, feats[name]['hnr']), flush=True)
    pick, chosen, report = {}, [], {}
    for role in ORDER:
        best = None
        for name, x in feats.items():
            if x['role'] != role: continue
            s = -4 * x['cer'] + 1.5 * x['lp'] - abs(np.log2(x['f0'] / TARGET_F0[role])) * 6 \
                - max(0, 2 - x['var']) - max(0, x['var'] - 4.5) + 0.08 * x['hnr']
            if chosen:   # 与已选角色太像扣分
                dmin = min(np.linalg.norm(x['mfcc'] - feats[c]['mfcc']) for c in chosen if feats[c]['role'] in ORDER[:5])  if any(feats[c]['role'] in ORDER[:5] for c in chosen) else 99
                s -= max(0, 25 - dmin) * 0.05
            report[name] = round(float(s), 3)
            if best is None or s > best[0]: best = (s, name)
        if best: pick[role] = best[1]; chosen.append(best[1])
        print('PICK', role, best, flush=True)
    json.dump(pick, open(os.path.join(VOI, 'pick.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'mfcc'} | {'score': report.get(k)} for k, v in feats.items()},
              open(os.path.join(VOI, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
