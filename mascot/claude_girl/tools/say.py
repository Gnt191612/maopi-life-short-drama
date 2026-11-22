# -*- coding: utf-8 -*-
"""用 Claude 娘的声音念任意台词（IndexTTS2 克隆参考音 + 温柔情绪 + 放慢到选定语速）。
用法（IndexTTS2 环境的 python，安装见 setup/setup_tts_windows.ps1）：
  python mascot/claude_girl/tools/say.py "台词" 输出.wav [--emo 高兴,愤怒,悲伤,恐惧,反感,低落,惊讶,自然] [--tempo 0.88]
环境变量 V11_INDEXTTS_DIR 指向 index-tts 仓库（默认 .tools/index-tts）。数字建议写成汉字（如「五点五」）读得更准。"""
import os, sys, json, argparse, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(BASE))
P = json.load(open(os.path.join(BASE, 'profile.json'), encoding='utf-8'))['voice']
ap = argparse.ArgumentParser(); ap.add_argument('text'); ap.add_argument('out')
ap.add_argument('--emo', default=','.join(str(x) for x in P['tts']['emo_vector'])); ap.add_argument('--alpha', type=float, default=P['tts']['emo_alpha'])
ap.add_argument('--tempo', type=float, default=P['post']['atempo'])
a = ap.parse_args()
idx = os.environ.get('V11_INDEXTTS_DIR') or os.path.join(ROOT, '.tools', 'index-tts')
if not os.path.isdir(idx) and os.path.isdir(r'D:\ai\index-tts'): idx = r'D:\ai\index-tts'
sys.path.insert(0, idx); out = os.path.abspath(a.out); ref = os.path.join(BASE, P['reference'])
os.chdir(idx)
from indextts.infer_v2 import IndexTTS2
tts = IndexTTS2(cfg_path='checkpoints/config.yaml', model_dir='checkpoints', use_fp16=True, use_cuda_kernel=False, use_qwen_emo=False)
raw = out if abs(a.tempo - 1) < 1e-3 else os.path.join(tempfile.gettempdir(), 'claude_say_raw.wav')
tts.infer(spk_audio_prompt=ref, text=a.text, output_path=raw, emo_vector=[float(x) for x in a.emo.split(',')], emo_alpha=a.alpha, verbose=False)
if raw != out:
    ff = os.environ.get('V11_FFMPEG') or 'ffmpeg'
    subprocess.run([ff, '-v', 'error', '-y', '-i', raw, '-af', 'atempo=%.3f' % a.tempo, out], check=True)
print('SAY OK', out)
