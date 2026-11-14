# -*- coding: utf-8 -*-
"""自动挑选角色音色（不依赖人耳）：对 voices/ 下每个候选测
  吐字清晰度（whisper 字错率）、音高是否符合角色年龄性别、语调起伏是否自然、语速是否正常；
再用 CAM++ 声纹保证不同角色彼此听起来不像同一个人。结果写 voices/pick.json 与 voices/report.json。
运行：<CosyVoice 环境的 python> voice_tools/voice_pick.py
"""
import os, sys, json, re
import numpy as np, soundfile as sf, librosa, onnxruntime, torch
import torchaudio.compliance.kaldi as kaldi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from tts10 import cer   # 会把仓库根目录加入 sys.path
import config
VOI = os.path.join(HERE, 'voices')
# 角色：合理的说话基频中位数范围（Hz）
F0 = {'林晓': (110, 160), '陈瑶': (95, 135), '周明远': (85, 125), '王老师': (90, 130), '林母': (165, 235),
      '同学甲': (115, 170), '同学乙': (190, 270), '网友': (185, 280), '网友2': (105, 170), '网友3': (185, 290), 'VO': (80, 125)}
ORDER = ['林晓', '陈瑶', '周明远', '王老师', '同学甲', '林母', '同学乙', '网友', '网友2', '网友3', 'VO']   # 主角先选，后选的要避开已选声纹

def embed(sess, wav16):
    feat = kaldi.fbank(torch.from_numpy(wav16).unsqueeze(0), num_mel_bins=80, dither=0, sample_frequency=16000)
    feat = feat - feat.mean(dim=0, keepdim=True)
    e = sess.run(None, {sess.get_inputs()[0].name: feat.unsqueeze(0).numpy()})[0].flatten()
    return e / np.linalg.norm(e)

def measure(path, text, asr, sess):
    w, sr = sf.read(path, dtype='float32')
    if w.ndim > 1: w = w.mean(1)
    w16 = librosa.resample(w, orig_sr=sr, target_sr=16000)
    hyp = asr.transcribe(w16, language='zh', initial_prompt='以下是普通话的句子。', fp16=False)['text']
    f0, vf, _ = librosa.pyin(w16, fmin=60, fmax=420, sr=16000, frame_length=1024)
    f0 = f0[vf & ~np.isnan(f0)]
    med = float(np.median(f0)) if len(f0) else 0.0
    st = float(np.std(12 * np.log2(f0 / med))) if len(f0) else 0.0          # 语调起伏（半音）
    iv = librosa.effects.split(w16, top_db=35); speech = sum(e - s for s, e in iv) / 16000
    n = len(re.findall(r'[\u4e00-\u9fff]', text)); rate = n / max(speech, 0.1)
    clip = float(np.mean(np.abs(w) > 0.99))
    return dict(cer=round(cer(text, hyp), 3), f0=round(med, 1), semitone_std=round(st, 2), rate=round(rate, 2),
                clip=round(clip, 4), asr=hyp), embed(sess, w16)

def score(role, m):
    lo, hi = F0[role]; s = m['cer'] * 6
    if m['f0'] < lo: s += (lo - m['f0']) / (hi - lo) * 2
    if m['f0'] > hi: s += (m['f0'] - hi) / (hi - lo) * 2
    if m['semitone_std'] < 1.6: s += (1.6 - m['semitone_std']) * 0.8      # 太平 = 念经
    if m['semitone_std'] > 4.8: s += (m['semitone_std'] - 4.8) * 0.6      # 太飘 = 不自然
    if m['rate'] < 3.3: s += (3.3 - m['rate']) * 0.5
    if m['rate'] > 6.0: s += (m['rate'] - 6.0) * 0.5
    s += m['clip'] * 50
    return s

def main():
    import whisper
    asr = whisper.load_model('small', device='cpu')
    sess = onnxruntime.InferenceSession(os.path.join(config.COSYVOICE_DIR, 'pretrained_models', 'CosyVoice2-0.5B', 'campplus.onnx'), providers=['CPUExecutionProvider'])
    vmeta = json.load(open(os.path.join(VOI, 'voices.json'), encoding='utf-8'))
    rep, embs = {}, {}
    for name, v in vmeta.items():
        m, e = measure(os.path.join(VOI, name + '.wav'), v['text'], asr, sess)
        m['score'] = round(score(v['role'], m), 3); rep[name] = dict(role=v['role'], **m); embs[name] = e
        print(name, m, flush=True)
    pick, chosen = {}, []
    for role in ORDER:
        cands = [n for n in rep if rep[n]['role'] == role]
        if not cands: continue
        def total(n):
            sim = max([float(embs[n] @ embs[c]) for c in chosen], default=0)
            rep[n]['max_sim_to_picked'] = round(sim, 3)
            return rep[n]['score'] + max(0.0, sim - 0.55) * 4               # 与已选角色太像要扣分
        best = min(cands, key=total)
        pick[role] = best; chosen.append(best)
        print('PICK', role, best, rep[best], flush=True)
    json.dump(pick, open(os.path.join(VOI, 'pick.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(rep, open(os.path.join(VOI, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
