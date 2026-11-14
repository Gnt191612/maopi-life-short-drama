# -*- coding: utf-8 -*-
"""v11 配音：IndexTTS2（B 站开源）。音色 = voices_v2/pick.json 指定的 Spark-TTS 设计参考音；
情绪 = 台词表第 4 列「语气说明」，交给 IndexTTS2 的文本情绪模型转成情绪向量，逐句控制（解决 v10 语气单调）。
每句若干候选，whisper 比对字错率挑最准的；写入 assets/audio，并删掉对应口型缓存，让 run_all 重新生成。
运行：<IndexTTS2 环境的 python> voice_tools/tts11.py [ID ...]   （环境变量 V11_INDEXTTS_DIR 指向 index-tts 仓库）
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
INDEX_DIR = os.environ.get('V11_INDEXTTS_DIR') or os.path.join(config.TOOLS, 'index-tts')
sys.path.insert(0, INDEX_DIR)
HERE = os.path.dirname(os.path.abspath(__file__))
import torch, torchaudio
from lines import LINES   # 台词表唯一来源：story/lines.py

def cer(ref, hyp):
    """按无声调拼音比对字错率：同音字不算错，只惩罚读错/漏读"""
    from pypinyin import lazy_pinyin
    norm = lambda s: re.sub(r'[^一-鿿0-9a-zA-Z]', '', re.sub(r'\[.*?\]', '', s))
    try:   # whisper 常把「七点五十」写成「7.50」，先把阿拉伯数字转成汉字再比
        import cn2an
        hyp = re.sub(r'(\d{1,2})[.:：](\d{2})', lambda m: cn2an.an2cn(m.group(1)) + '点' + cn2an.an2cn(str(int(m.group(2)))), hyp)   # 时刻
        hyp = cn2an.transform(hyp, 'an2cn')
    except Exception: pass
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

def trim(wav, sr, th=0.01, pad=0.08):
    """去掉首尾静音，保留 80ms 余量"""
    a = wav[0].abs(); idx = (a > th).nonzero()
    if len(idx) == 0: return wav
    s = max(0, int(idx[0]) - int(pad * sr)); e = min(wav.shape[1], int(idx[-1]) + int(pad * sr))
    return wav[:, s:e]

OUT = config.AUDIO; os.makedirs(OUT, exist_ok=True)
VOI = os.path.join(HERE, 'voices_v2')
N_CAND = int(os.environ.get('NCAND', 3))
EMO_ALPHA = float(os.environ.get('EMO_ALPHA', 0.65))   # 情绪强度：官方建议文本情绪 0.6 左右，过高会失真
# 按人物性格定情绪幅度（导演把关）：林晓外放、情绪大起大落；陈瑶冷静克制；周明远温和内敛；王老师沉稳；
# 林母热络絮叨；同学甲咋呼、爱起哄；同学乙俏皮
ROLE_ALPHA = {'林晓': 0.8, '陈瑶': 0.5, '周明远': 0.6, '王老师': 0.5, '林母': 0.7, '同学甲': 0.8, '同学乙': 0.7}
# 文本情绪模型读不准的复合情绪（阴阳怪气、强装轻松、紧张、尴尬……），导演逐句手定情绪向量
# 顺序：高兴, 愤怒, 悲伤, 恐惧, 反感, 低落, 惊讶, 自然
EMO_OVERRIDE = {
 'A05e': [0.6, 0, 0, 0, 0, 0, 0.2, 0.2],     # 压低声音兴冲冲
 'A08':  [0.3, 0, 0, 0, 0.1, 0, 0, 0.6],     # 无奈又好笑
 'A14':  [0.5, 0, 0, 0.25, 0, 0, 0, 0.25],   # 强装轻松、心虚
 'B07':  [0.45, 0, 0, 0, 0.35, 0, 0.1, 0.1], # 阴阳怪气
 'B08':  [0.6, 0, 0, 0, 0.2, 0, 0, 0.2],     # 捂嘴偷笑、揶揄
 'D03':  [0.3, 0, 0, 0, 0, 0, 0, 0.7],       # 真诚坦然、释然
 'D04a': [0, 0, 0.25, 0.3, 0, 0.15, 0, 0.3], # 不好意思、越说越小声
 'D04b': [0.3, 0, 0, 0.25, 0, 0, 0, 0.45],   # 尴尬地笑
 'E01':  [0, 0, 0, 0.2, 0, 0, 0, 0.8],       # 深吸一口气下定决心
 'F01':  [0.6, 0, 0, 0, 0, 0, 0, 0.4],       # 笑着打断
 'H01':  [0, 0, 0, 0.5, 0, 0.3, 0, 0.2],     # 紧张、终于说出口
 'L01':  [0, 0, 0, 0, 0, 0, 0.35, 0.65],     # 压低声音好奇地问
}

def main():
    only = set(sys.argv[1:])
    pick = json.load(open(os.path.join(VOI, 'pick.json'), encoding='utf-8'))
    os.chdir(INDEX_DIR)
    from indextts.infer_v2 import IndexTTS2, QwenEmotion
    # 先用文本情绪模型把每句的「语气说明」算成情绪向量，再卸载它——8 GB 显卡放不下两个模型，挤爆显存会慢十几倍
    todo = [l for l in LINES if not only or l[0] in only]
    q = QwenEmotion(os.path.join('checkpoints', 'qwen0.6bemo4-merge'))
    EMO = {lid: EMO_OVERRIDE.get(lid) or list(q.inference(ins).values()) for lid, spk, text, ins in todo}
    del q; import gc; gc.collect(); torch.cuda.empty_cache()
    tts = IndexTTS2(cfg_path='checkpoints/config.yaml', model_dir='checkpoints', use_fp16=True, use_cuda_kernel=False, use_qwen_emo=False)
    import whisper
    asr = whisper.load_model('small', device='cpu')   # 校验放 CPU：8 GB 显卡上与 IndexTTS2 同时放 GPU 会爆显存、慢十几倍
    meta_p = os.path.join(OUT, 'meta.json')
    meta = json.load(open(meta_p, encoding='utf-8')) if os.path.exists(meta_p) else {}
    for lid, spk, text, ins in LINES:
        if only and lid not in only: continue
        voice = pick[spk]
        if not only and meta.get(lid, {}).get('engine') == 'indextts2' and meta[lid].get('voice') == voice: continue
        ref = os.path.join(VOI, voice + '.wav')
        cands = []
        for k in range(N_CAND):
            torch.manual_seed(2000 + k * 31 + sum(map(ord, lid)))
            p = os.path.join(OUT, '%s_c%d.wav' % (lid, k))
            # 情绪只看语气说明（带上台词原文会被字面意思带偏，如「你不懂」被判成愤怒）
            tts.infer(spk_audio_prompt=ref, text=text, output_path=p, emo_vector=EMO[lid], emo_alpha=ROLE_ALPHA.get(spk, EMO_ALPHA),
                      use_random=False, verbose=False)
            wav, sr = torchaudio.load(p)
            wav = trim(wav, sr); torchaudio.save(p, wav, sr, encoding='PCM_S', bits_per_sample=16)
            a16 = torchaudio.functional.resample(wav, sr, 16000)[0].numpy().astype('float32')
            hyp = asr.transcribe(a16, language='zh', initial_prompt='以下是普通话的句子。')['text']
            e = cer(text, hyp); d = wav.shape[1] / sr
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
        vis = os.path.join(config.VISEMES, lid + '.json')
        if os.path.exists(vis): os.remove(vis)   # 口型随新配音重算
        meta[lid] = dict(spk=spk, text=text, voice=voice, engine='indextts2', emo=ins, cer=round(best[0], 3), dur=round(best[1], 3), asr=best[3])
        json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('==>', lid, 'pick cer=%.2f' % best[0], flush=True)

if __name__ == '__main__':
    main()
