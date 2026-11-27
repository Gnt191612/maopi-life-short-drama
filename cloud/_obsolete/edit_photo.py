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
        # 工作流同时输出「前后对比图」（两张并排）和结果图：原来取第一张，取到的是对比图，视频里出现两个林母（2026-11-25）。
        # 现在把所有输出都下载下来，挑宽高比最接近原图的那张（结果图）
        from PIL import Image   # 云端系统 python 不一定有 cv2，用 PIL
        w0, h0 = Image.open(os.path.join('/root/ComfyUI/input', src)).size; r0 = w0 / h0
        cands = []
        for k, o in enumerate(h[pid]['outputs'].values()):
            for j, im in enumerate(o.get('images', [])):
                if im.get('type') == 'temp' and any(x.get('type') != 'temp' for oo in h[pid]['outputs'].values() for x in oo.get('images', [])): continue
                q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im['subfolder'], 'type': im['type']})
                p = os.path.join(comfy_run.OUT, '%s_c%d%d.png' % (name, k, j)); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read())
                w1, h1 = Image.open(p).size; cands.append((abs(w1 / h1 - r0), p))
        if cands:
            best = min(cands)[1]; p = os.path.join(comfy_run.OUT, name + '.png'); os.replace(best, p); print('SAVED', p, 'from', len(cands), 'outputs', flush=True); sys.exit(0)
print('FAIL', flush=True)
