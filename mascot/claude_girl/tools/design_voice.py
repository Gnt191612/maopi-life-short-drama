# -*- coding: utf-8 -*-
"""片头 Claude 娘的音色（Spark-TTS 设计全新人声，不克隆任何真人）：知书达理、温柔体贴的年轻女声。
输出 voices_v2/Claude娘_<k>.wav + voices.json 记录；之后用 claude_line.py（IndexTTS2）念片头台词。
运行：<Spark-TTS 环境的 python> mascot/claude_girl/tools/design_voice.py（选定的是 6 号：seed 2026+6*131=2812，见 profile.json）"""
import os, sys, json
import numpy as np, soundfile as sf, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))   # 仓库根目录
import config
SPARK = os.environ.get('V11_SPARK_DIR') or (config.SPARK_DIR if os.path.isdir(config.SPARK_DIR) else r'D:\ai\Spark-TTS')
sys.path.insert(0, SPARK)
from cli.SparkTTS import SparkTTS
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'voice', 'candidates')
# 参考句：语气平和、亲切、有礼貌（作为 IndexTTS2 克隆参考时，温柔的气质会迁移过去）
TEXT = '大家好，我是Claude。很高兴能陪大家一起看这个故事，如果有哪里没看明白，随时都可以来问我哦。'
OPTS = [('moderate', 'low'), ('moderate', 'moderate'), ('high', 'low'), ('high', 'moderate')]

def main():
    model = SparkTTS(os.path.join(SPARK, 'pretrained_models', 'Spark-TTS-0.5B'), torch.device('cuda:0'))
    os.makedirs(OUT, exist_ok=True); meta_p = os.path.join(OUT, 'voices.json'); meta = json.load(open(meta_p, encoding='utf-8')) if os.path.exists(meta_p) else {}
    k = 0
    for rnd in range(2):
        for pitch, speed in OPTS:
            k += 1; name = 'Claude娘_%d' % k; p = os.path.join(OUT, name + '.wav')
            if os.path.exists(p): continue
            torch.manual_seed(2026 + k * 131)
            with torch.no_grad():
                wav = model.inference(TEXT, gender='female', pitch=pitch, speed=speed, temperature=0.75, top_k=50, top_p=0.95)
            wav = np.asarray(wav, np.float32); wav = wav / (np.abs(wav).max() + 1e-9) * 0.9
            sf.write(p, wav, model.sample_rate)
            meta[name] = dict(role='Claude娘', gender='female', pitch=pitch, speed=speed, text=TEXT, dur=round(len(wav) / model.sample_rate, 2))
            json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('OK', name, pitch, speed, meta[name]['dur'], flush=True)

if __name__ == '__main__':
    main()
