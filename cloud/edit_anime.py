# -*- coding: utf-8 -*-
"""动漫图编辑（云端，Krea2 编辑模型，关掉写实化 LoRA 以保持 2D 画风）：python3 edit_anime.py <输入图> <输出名> <指令> [种子 ...]
例：把 Claude 娘手里半开的折扇合上（片头要扇子全程合着）"""
import sys, os, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
src, name, inst = sys.argv[1:4]; seeds = [int(x) for x in sys.argv[4:]] or [5]
for k, seed in enumerate(seeds, 1):
    api = comfy_run.convert('Krea2-二转三-图生图-新版.json')
    for nid, nd in api.items():
        for key, v in list(nd['inputs'].items()):
            if isinstance(v, str) and '真实照片' in v: nd['inputs'][key] = inst
            if isinstance(v, dict) and 'lora' in v: v['on'] = False          # 关掉写实化 LoRA
    api['10']['inputs']['image'] = src; api['1']['inputs']['seed'] = seed
    pid = comfy_run._post('/prompt', {'prompt': api}).get('prompt_id')
    for _ in range(200):
        time.sleep(3); h = comfy_run._get('/history/' + pid)
        if pid in h and h[pid].get('outputs'):
            for o in h[pid]['outputs'].values():
                for im in o.get('images', []):
                    q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im['subfolder'], 'type': im['type']})
                    p = os.path.join(comfy_run.OUT, '%s_%d.png' % (name, k)); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read())
                    print('SAVED', p, flush=True)
            break
print('EDIT DONE', flush=True)
