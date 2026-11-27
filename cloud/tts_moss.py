# -*- coding: utf-8 -*-
"""MOSS-TTSD v1.0 对话配音（写实化实例上运行，2026-11-27 用户同意加对比）：
一次生成一整段多人对话（[S1][S2] 标签，continuation 方式），比逐句单独合成更像真人对话（有来回的节奏、语气承接）。
音色参考 = 每个角色现有配音里的一句（3～10 秒，带原文），只借音色；生成的是整段新对话。
代码按官方 README「Basic Usage」（Hugging Face OpenMOSS-Team/MOSS-TTSD-v1.0，11-27 核对原文）写；生成参数用官方默认：
audio_temperature 1.1、audio_top_p 0.9、audio_top_k 50、audio_repetition_penalty 1.1；1 秒约 12.5 个 token。
用法：python tts_moss.py <dialog.json> <输出目录> [--seeds 3]
  dialog.json = {"name": "s06_dialog", "refs": {"S1": {"wav": "ref_S1.wav", "text": "..."}, ...}, "lines": [["S1", "台词"], ...]}
输出：<输出目录>/<name>_<k>.wav（每个随机种子一版，挑最好的）+ <name>.json（耗时、时长）"""
import os, sys, json, time, importlib.util
import torch, torchaudio
from transformers import AutoModel, AutoProcessor
torch.backends.cuda.enable_cudnn_sdp(False)   # 官方：cuDNN 的 SDPA 有问题，关掉
for f in (torch.backends.cuda.enable_flash_sdp, torch.backends.cuda.enable_mem_efficient_sdp, torch.backends.cuda.enable_math_sdp): f(True)
D = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
seeds = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 3
base = os.path.dirname(os.path.abspath(sys.argv[1]))
MP = os.environ.get('MOSS_TTSD', '/root/models/MOSS-TTSD-v1.0')
dev = 'cuda'; dtype = torch.bfloat16
attn = 'flash_attention_2' if importlib.util.find_spec('flash_attn') and torch.cuda.get_device_capability()[0] >= 8 else 'sdpa'
t0 = time.time()
proc = AutoProcessor.from_pretrained(MP, trust_remote_code=True)
proc.audio_tokenizer = proc.audio_tokenizer.to(dev)
model = AutoModel.from_pretrained(MP, trust_remote_code=True, attn_implementation=attn, torch_dtype=dtype).to(dev).eval()
sr = int(proc.model_config.sampling_rate)
print('模型加载 %.0f 秒，采样率 %d，注意力 %s' % (time.time() - t0, sr, attn), flush=True)
spk = sorted(D['refs']); wavs = []
for s in spk:
    w, r = torchaudio.load(os.path.join(base, D['refs'][s]['wav']))
    if w.shape[0] > 1: w = w.mean(dim=0, keepdim=True)
    if r != sr: w = torchaudio.functional.resample(w, r, sr)
    wavs.append(w)
ref_codes = proc.encode_audios_from_wav(wavs, sampling_rate=sr)
prompt_audio = proc.encode_audios_from_wav([torch.cat(wavs, dim=-1)], sampling_rate=sr)[0]
prefix = ' '.join('[%s] %s' % (s, D['refs'][s]['text']) for s in spk)
target = ' '.join('[%s] %s' % (s, t) for s, t in D['lines'])
conv = [[proc.build_user_message(text=prefix + ' ' + target, reference=ref_codes), proc.build_assistant_message(audio_codes_list=[prompt_audio])]]
batch = proc(conv, mode='continuation'); ids = batch['input_ids'].to(dev); mask = batch['attention_mask'].to(dev)
chars = sum(len(t) for _, t in D['lines']); n_tok = int(chars / 4.0 * 12.5 * 1.8) + 250   # 中文约 4 字/秒，留 80% 余量
info = dict(load_s=round(time.time() - t0), attn=attn, versions=[])
for k in range(seeds):
    torch.manual_seed(20261127 + k); t1 = time.time()
    with torch.no_grad():
        outs = model.generate(input_ids=ids, attention_mask=mask, max_new_tokens=n_tok,
                              audio_temperature=1.1, audio_top_p=0.9, audio_top_k=50, audio_repetition_penalty=1.1)
    a = proc.decode(outs)[0].audio_codes_list[0]
    p = os.path.join(out, '%s_%d.wav' % (D['name'], k)); torchaudio.save(p, a.float().cpu().unsqueeze(0), sr)
    info['versions'].append(dict(file=os.path.basename(p), gen_s=round(time.time() - t1), audio_s=round(a.shape[-1] / sr, 1)))
    print('MOSS 第 %d 版' % k, info['versions'][-1], flush=True)
json.dump(info, open(os.path.join(out, D['name'] + '.json'), 'w'), ensure_ascii=False, indent=1)
print('MOSS DONE', info, flush=True)
