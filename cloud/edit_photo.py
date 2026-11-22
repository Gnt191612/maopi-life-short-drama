# -*- coding: utf-8 -*-
"""照片编辑（云端，Krea2 编辑模型，二转三工作流换掉指令）：python3 edit_photo.py <输入图> <输出名> <指令> [种子]
例：去掉片头背景里打红伞的人，其余不变（同时放大到约 200 万像素）"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
src, name, inst = sys.argv[1:4]; seed = int(sys.argv[4]) if len(sys.argv) > 4 else 5
api = comfy_run.convert('Krea2-二转三-图生图-新版.json')
for nid, nd in api.items():   # 把「转为真实照片…」那条指令换成编辑指令
    for k, v in nd['inputs'].items():
        if isinstance(v, str) and '真实照片' in v: nd['inputs'][k] = inst; print('指令节点', nid, k, flush=True)
api['10']['inputs']['image'] = src; api['1']['inputs']['seed'] = seed
r = comfy_run._post('/prompt', {'prompt': api}); pid = r.get('prompt_id')
import time, urllib.request, urllib.parse
for _ in range(300):
    time.sleep(3); h = comfy_run._get('/history/' + pid)
    if pid in h and h[pid].get('outputs'):
        for o in h[pid]['outputs'].values():
            for im in o.get('images', []):
                q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im['subfolder'], 'type': im['type']})
                p = os.path.join(comfy_run.OUT, name + '.png'); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read()); print('SAVED', p, flush=True); sys.exit(0)
print('FAIL', flush=True)
