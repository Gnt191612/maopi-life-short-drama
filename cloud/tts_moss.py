# -*- coding: utf-8 -*-
"""MOSS-TTSD v1.0 对话配音试跑（写实化实例上运行，2026-11-27 用户同意加对比）：
一次生成一整段多人对话（[S1][S2] 标签），比逐句单独合成更像真人对话（有来回的节奏、语气承接）。
音色参考 = 每个角色现有配音里的一句（3～10 秒，带原文），只借音色；生成的是整段新对话。
参数照官方模型卡：audio_temperature 1.1、top_p 0.9、top_k 50、repetition_penalty 1.1；约 12.5 token = 1 秒。
用法：python3 tts_moss.py <dialog.json> <输出目录>
  dialog.json = {"refs": {"S1": {"wav": "...", "text": "..."}, ...}, "lines": [["S1", "台词"], ...], "name": "s06_dialog"}
输出：<输出目录>/<name>.wav（整段）+ <name>.json（耗时）"""
import os, sys, json, time
import torch, torchaudio
from transformers import AutoModel, AutoProcessor
D = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
MP = os.environ.get('MOSS_TTSD', '/root/models/MOSS-TTSD-v1.0')
dev = 'cuda'; dtype = torch.bfloat16
try:
    import flash_attn  # noqa: F401
    attn = 'flash_attention_2'
except Exception:
    attn = 'sdpa'
t0 = time.time()
proc = AutoProcessor.from_pretrained(MP, trust_remote_code=True)
model = AutoModel.from_pretrained(MP, trust_remote_code=True, torch_dtype=dtype, attn_implementation=attn).to(dev).eval()
if hasattr(proc, 'audio_tokenizer') and hasattr(proc.audio_tokenizer, 'to'): proc.audio_tokenizer = proc.audio_tokenizer.to(dev)
sr = proc.model_config.sampling_rate
print('模型加载 %.0f 秒，采样率 %d，注意力 %s' % (time.time() - t0, sr, attn), flush=True)
spk = sorted(D['refs']); wavs, prefix = [], []
for s in spk:
    w, r = torchaudio.load(D['refs'][s]['wav']); w = w.mean(0, keepdim=True)
    if r != sr: w = torchaudio.functional.resample(w, r, sr)
    wavs.append(w); prefix.append('[%s]%s' % (s, D['refs'][s]['text']))
codes = proc.encode_audios_from_wav(wavs, sampling_rate=sr) if 'sampling_rate' in proc.encode_audios_from_wav.__code__.co_varnames else proc.encode_audios_from_wav(wavs)
prompt_codes = proc.encode_audios_from_wav([torch.cat(wavs, dim=1)])
target = ''.join('[%s]%s' % (s, t) for s, t in D['lines'])
conv = [proc.build_user_message(text=''.join(prefix) + target, reference=codes),
        proc.build_assistant_message(audio_codes_list=prompt_codes)]
batch = proc([conv], mode='continuation')
batch = {k: (v.to(dev) if hasattr(v, 'to') else v) for k, v in batch.items()}
n_tok = int(sum(len(t) for _, t in D['lines']) / 4.0 * 12.5 * 1.6) + 200   # 中文约 4 字/秒，留 60% 余量
t1 = time.time()
with torch.no_grad():
    outs = model.generate(**batch, max_new_tokens=n_tok, audio_temperature=1.1, audio_top_p=0.9, audio_top_k=50, audio_repetition_penalty=1.1)
audio = proc.decode(outs)
a = audio[0] if isinstance(audio, (list, tuple)) else audio
if hasattr(a, 'audio'): a = a.audio
a = torch.as_tensor(a).float().cpu()
if a.dim() == 1: a = a[None]
p = os.path.join(out, D['name'] + '.wav'); torchaudio.save(p, a, sr)
info = dict(load_s=round(t1 - t0), gen_s=round(time.time() - t1), audio_s=round(a.shape[-1] / sr, 1), attn=attn)
json.dump(info, open(os.path.join(out, D['name'] + '.json'), 'w'), ensure_ascii=False)
print('MOSS DONE', p, info, flush=True)
