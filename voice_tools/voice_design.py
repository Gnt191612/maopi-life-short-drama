# -*- coding: utf-8 -*-
"""Spark-TTS 音色设计：按性别/音高/语速直接生成全新的自然人声（不克隆任何真人、不用合成机器音作参考）。
每个角色生成 4 个候选，输出 v10/voices/{角色}_{k}.wav，供试听挑选；选定后作为 CosyVoice2 零样本克隆的参考。
运行：<Spark-TTS 环境的 python> voice_tools/voice_design.py   （安装见 setup/setup_tts_*）
"""
import os, sys, json
import numpy as np, soundfile as sf, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
sys.path.insert(0, config.SPARK_DIR)
from cli.SparkTTS import SparkTTS

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'voices'); os.makedirs(OUT, exist_ok=True)
# 角色: (性别, [(音高, 语速) x4], 参考句——口语化、语气平稳，作为克隆参考时情绪可迁移性最好)
ROLES = {
 '林晓':  ('male',   [('moderate', 'moderate'), ('moderate', 'moderate'), ('high', 'moderate'), ('moderate', 'high')],
           '哎，你们别笑我啊，我就是想让大家觉得，我过得还挺不错的嘛。'),
 '陈瑶':  ('male',   [('low', 'moderate'), ('low', 'moderate'), ('moderate', 'moderate'), ('low', 'low')],
           '我觉得这件事没那么复杂，你先别急，坐下来，我们慢慢说。'),
 '周明远': ('male',   [('low', 'low'), ('low', 'low'), ('very_low', 'low'), ('low', 'moderate')],
           '那段时间我谁也不想见，后来才慢慢明白，朋友其实一直都在。'),
 '王老师': ('male',   [('low', 'moderate'), ('low', 'moderate'), ('moderate', 'moderate'), ('very_low', 'moderate'),
            ('moderate', 'low'), ('moderate', 'low'), ('low', 'low'), ('moderate', 'moderate'), ('high', 'low'), ('low', 'moderate')],
           '今天咱们不讲大道理，就随便聊聊，说说大家最近过得怎么样。'),
 '林母':  ('female', [('moderate', 'moderate'), ('moderate', 'moderate'), ('low', 'moderate'), ('moderate', 'low')],
           '晓晓啊，最近吃得好不好？天冷了，记得多穿件衣服，别熬夜。'),
 '同学甲': ('male',   [('high', 'high'), ('high', 'moderate'), ('moderate', 'high'), ('high', 'high')],
           '哟，这不是咱们的学霸晓哥嘛，今天又去图书馆打卡啦？'),
 '同学乙': ('female', [('high', 'moderate'), ('high', 'moderate'), ('moderate', 'moderate'), ('very_high', 'moderate')],
           '其实我也经常这样，发之前要修好久的图，想想也挺累的。'),
 '网友':  ('female', [('high', 'high'), ('moderate', 'high')], '哈哈哈，这也太真实了吧，我也是这样的。'),
 '网友2': ('male',   [('moderate', 'high'), ('high', 'high')], '哈哈哈，这也太真实了吧，我也是这样的。'),
 '网友3': ('female', [('very_high', 'high'), ('moderate', 'moderate')], '哈哈哈，这也太真实了吧，我也是这样的。'),
 'VO':   ('male',   [('low', 'low'), ('very_low', 'low')], '每个人都在努力地生活，也都值得被温柔地对待。'),
}

def main():
    model = SparkTTS(os.path.join(config.SPARK_DIR, 'pretrained_models', 'Spark-TTS-0.5B'), torch.device(os.environ.get('SPARK_DEVICE', 'cuda:0')))
    meta_p = os.path.join(OUT, 'voices.json')
    meta = json.load(open(meta_p, encoding='utf-8')) if os.path.exists(meta_p) else {}
    for role, (g, opts, text) in ROLES.items():
        for k, (pitch, speed) in enumerate(opts):
            name = '%s_%d' % (role, k + 1); p = os.path.join(OUT, name + '.wav')
            if os.path.exists(p): continue
            torch.manual_seed(7 + k * 101 + sum(map(ord, role)))
            with torch.no_grad():
                wav = model.inference(text, gender=g, pitch=pitch, speed=speed, temperature=0.8, top_k=50, top_p=0.95)
            wav = np.asarray(wav, np.float32)
            wav = wav / (np.abs(wav).max() + 1e-9) * 0.9
            sf.write(p, wav, model.sample_rate)
            meta[name] = dict(role=role, gender=g, pitch=pitch, speed=speed, text=text, dur=round(len(wav) / model.sample_rate, 2))
            json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('OK', name, pitch, speed, meta[name]['dur'], flush=True)

if __name__ == '__main__':
    main()
