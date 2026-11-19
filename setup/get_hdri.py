# -*- coding: utf-8 -*-
"""下载环境光 HDRI（Poly Haven，全部 CC0），放 assets/hdri/<用途>.hdr。每个用途列几个候选，取第一个可用的。
运行：python setup/get_hdri.py   （需要联网；有代理就设 HTTPS_PROXY）"""
import os, sys, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
OUT = os.path.join(config.ROOT, 'assets', 'hdri'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'maopi-life-short-drama/1.0 (https://github.com/Gnt191612/maopi-life-short-drama)'}
WANT = {   # 用途: 候选（Poly Haven 资产 id）
    'day':      ['kloofendal_48d_partly_cloudy_puresky', 'kloofendal_43d_clear_puresky', 'sunflowers_puresky'],   # 白天户外：晴间多云
    'morning':  ['kiara_1_dawn', 'spruit_sunrise', 'qwantani_dawn'],                                            # 清晨低角度暖光
    'dusk':     ['qwantani_dusk_2', 'kloppenheim_06', 'venice_sunset'],                                         # 傍晚
    'night':    ['moonless_golf', 'satara_night', 'kloppenheim_02'],                                            # 夜晚
    'interior': ['small_empty_room_3', 'brown_photostudio_02', 'studio_small_09'],                              # 室内补光与反射
}

def get(url):
    for i in range(6):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e: print('  重试', i + 1, e); time.sleep(min(60, 5 * 2 ** i))
    raise RuntimeError(url)

lic = []
for use, cands in WANT.items():
    dst = os.path.join(OUT, use + '.hdr')
    for aid in cands:
        try:
            info = json.loads(get('https://api.polyhaven.com/info/' + aid))
            files = json.loads(get('https://api.polyhaven.com/files/' + aid))
        except Exception: continue
        url = files['hdri']['2k']['hdr']['url']
        if not os.path.exists(dst): open(dst, 'wb').write(get(url))
        lic.append('%s.hdr\t%s\tCC0\thttps://polyhaven.com/a/%s\t%s' % (use, info.get('name', aid), aid, ', '.join(info.get('authors', {}).keys())))
        print('OK', use, aid, round(os.path.getsize(dst) / 1e6, 1), 'MB'); break
open(os.path.join(OUT, 'LICENSES.txt'), 'w', encoding='utf-8').write('文件\t名称\t许可\t来源\t作者\n' + '\n'.join(lic) + '\n')
