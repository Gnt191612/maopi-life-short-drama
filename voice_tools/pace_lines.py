# -*- coding: utf-8 -*-
"""台词语速统一：每秒超过 5.6 个字的句子用 ffmpeg atempo 放慢到约每秒 5 字（最多放慢到 0.85 倍，音高不变）。
2026-11-22 全片检查：中位语速 4.5 字/秒，个别长句接近 6 字/秒，听着赶。
原音备份在 assets/audio/_orig/；改过的句子在 meta.json 里记 atempo，重复运行不会再放慢；对应口型 json 删掉，run_all.py 会重新生成。
运行：python voice_tools/pace_lines.py [--dry]"""
import os, sys, re, json, shutil, subprocess, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import segments as S

FAST, TARGET, MIN_TEMPO = 5.6, 5.0, 0.85   # 5.6：A03「七点五十了」催人起床，急是对的
dry = '--dry' in sys.argv
meta_p = os.path.join(S.AUD, 'meta.json'); meta = json.load(open(meta_p, encoding='utf-8'))
bak = os.path.join(S.AUD, '_orig'); os.makedirs(bak, exist_ok=True)

def chars(txt):
    return len(re.sub(r'[，。！？、…—：；“”‘’\s,.!?~·]', '', txt))

def is_cjk(txt):
    return sum(1 for c in txt if '一' <= c <= '鿿') >= max(1, chars(txt)) * 0.6   # 英文单词（abandon）不按汉字算

for lid, (who, txt) in S.TEXT.items():
    m = meta.get(lid)
    if not m or m.get('atempo') or not is_cjk(txt) or m['dur'] < 1.5: continue
    cps = chars(txt) / m['dur']
    if cps <= FAST: continue
    tempo = max(MIN_TEMPO, TARGET / cps)
    print('%s %s %.2f 字/秒 -> atempo %.3f  %s' % (lid, who, cps, tempo, txt[:24]), flush=True)
    if dry: continue
    src = os.path.join(S.AUD, lid + '.wav'); orig = os.path.join(bak, lid + '.wav')
    if not os.path.exists(orig): shutil.copy2(src, orig)
    subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-i', orig, '-af', 'atempo=%.4f' % tempo, src], check=True)
    with wave.open(src) as w: m['dur'] = round(w.getnframes() / w.getframerate(), 3)
    m['atempo'] = round(tempo, 4)
    vis = os.path.join(config.VISEMES, lid + '.json')
    if os.path.exists(vis): os.remove(vis)
json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('PACE DONE')
