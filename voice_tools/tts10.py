# -*- coding: utf-8 -*-
"""v10 配音：以 Spark-TTS 设计的自然人声为参考（voices/pick.json 指定每个角色选哪个），CosyVoice2 零样本克隆生成全部台词。
不再使用 instruct2 情绪指令（会让声音发僵），情绪由台词文本本身带出。每句 3 个候选，whisper 比对字错率挑最准的。
运行：<CosyVoice 环境的 python> voice_tools/tts10.py [ID ...]   （安装见 setup/setup_tts_*）
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
sys.path.insert(0, config.COSYVOICE_DIR); sys.path.insert(0, os.path.join(config.COSYVOICE_DIR, 'third_party', 'Matcha-TTS'))
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import re
import torch, torchaudio
from lines10 import LINES
from cosyvoice.cli.cosyvoice import CosyVoice2

def cer(ref, hyp):
    """按无声调拼音比对字错率：同音字不算错，只惩罚读错/漏读"""
    from pypinyin import lazy_pinyin
    norm = lambda s: re.sub(r'[^一-鿿0-9a-zA-Z]', '', re.sub(r'\[.*?\]', '', s))
    r, h = lazy_pinyin(norm(ref)), lazy_pinyin(norm(hyp))
    if not r: return 0.0
    dp = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, len(h) + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return dp[-1] / len(r)

OUT = config.AUDIO; os.makedirs(OUT, exist_ok=True)   # 配音直接写入固定资产目录
VOI = os.path.join(HERE, 'voices')
N_CAND = int(os.environ.get('NCAND', 3))

def trim(wav, sr, th=0.01, pad=0.08):
    """去掉首尾静音，保留 80ms 余量"""
    a = wav[0].abs(); idx = (a > th).nonzero()
    if len(idx) == 0: return wav
    s = max(0, int(idx[0]) - int(pad * sr)); e = min(wav.shape[1], int(idx[-1]) + int(pad * sr))
    return wav[:, s:e]

def main():
    only = set(sys.argv[1:])
    vmeta = json.load(open(os.path.join(VOI, 'voices.json'), encoding='utf-8'))
    pick_p = os.path.join(VOI, 'pick.json')
    pick = json.load(open(pick_p, encoding='utf-8')) if os.path.exists(pick_p) else {}
    model = CosyVoice2(os.path.join(config.COSYVOICE_DIR, 'pretrained_models', 'CosyVoice2-0.5B'), load_jit=False, load_trt=False, fp16=False)
    import whisper
    asr = whisper.load_model('small', device='cuda')
    meta_p = os.path.join(OUT, 'meta.json')
    meta = json.load(open(meta_p, encoding='utf-8')) if os.path.exists(meta_p) else {}
    for lid, spk, text, ins in LINES:
        if only and lid not in only: continue
        voice = pick.get(spk, spk + '_1')
        if not only and lid in meta and meta[lid].get('voice') == voice: continue
        ref = os.path.join(VOI, voice + '.wav'); ref_text = vmeta[voice]['text']
        cands = []
        for k in range(N_CAND):
            torch.manual_seed(1000 + k * 17 + sum(map(ord, lid)))
            chunks = [o['tts_speech'] for o in model.inference_zero_shot(text, ref_text, ref, stream=False)]
            wav = trim(torch.cat(chunks, dim=1), model.sample_rate)
            p = os.path.join(OUT, '%s_c%d.wav' % (lid, k))
            torchaudio.save(p, wav, model.sample_rate)
            a16 = torchaudio.functional.resample(wav, model.sample_rate, 16000)[0].numpy().astype('float32')
            hyp = asr.transcribe(a16, language='zh', initial_prompt='以下是普通话的句子。')['text']
            e = cer(text, hyp); d = wav.shape[1] / model.sample_rate
            cands.append((e, d, p, hyp))
            print(lid, spk, voice, 'cand', k, 'cer=%.2f' % e, '%.2fs' % d, hyp, flush=True)
            if e == 0: break
        cands.sort(key=lambda c: (round(c[0], 2), c[1]))
        best = cands[0]
        final = os.path.join(OUT, lid + '.wav')
        if os.path.exists(final): os.remove(final)
        os.replace(best[2], final)
        for c in cands[1:]:
            if os.path.exists(c[2]): os.remove(c[2])
        meta[lid] = dict(spk=spk, text=text, voice=voice, cer=round(best[0], 3), dur=round(best[1], 3), asr=best[3])
        json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('==>', lid, 'pick cer=%.2f' % best[0], flush=True)

if __name__ == '__main__':
    main()
