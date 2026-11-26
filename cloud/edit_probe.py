# -*- coding: utf-8 -*-
"""编辑工作流输出探查（云端）：跑一次编辑，把所有输出图（含预览类 temp）都下载下来，打印节点号、节点类型、尺寸、类型，
用来确认哪一张才是真正的编辑结果（2026-11-25：edit_photo 存下来的总是左右拼起来的对比图）。
用法：python3 edit_probe.py <输入图（ComfyUI/input 下的文件名）> <指令>"""
import sys, os, json, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from PIL import Image
src, inst = sys.argv[1], sys.argv[2]
api = comfy_run.convert('Krea2-二转三-图生图-新版.json')
for nid, nd in api.items():
    for k, v in nd['inputs'].items():
        if isinstance(v, str) and '真实照片' in v: nd['inputs'][k] = inst; print('指令节点', nid, k, flush=True)
api['10']['inputs']['image'] = src; api['1']['inputs']['seed'] = 11
for nid, nd in sorted(api.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
    print('节点', nid, nd['class_type'], {k: (v if not isinstance(v, str) or len(v) < 40 else v[:40]) for k, v in nd['inputs'].items()}, flush=True)
pid = comfy_run._post('/prompt', {'prompt': api}).get('prompt_id')
for _ in range(400):
    time.sleep(3); h = comfy_run._get('/history/' + pid)
    if pid in h and h[pid].get('outputs'): break
os.makedirs('/root/v11_out/probe_edit', exist_ok=True)
for nid, o in h[pid]['outputs'].items():
    for j, im in enumerate(o.get('images', [])):
        q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im.get('subfolder', ''), 'type': im.get('type', 'output')})
        p = '/root/v11_out/probe_edit/n%s_%d_%s.png' % (nid, j, im.get('type'))
        open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read())
        print('输出', nid, api.get(nid, {}).get('class_type'), im.get('type'), Image.open(p).size, p, flush=True)
print('PROBE DONE', flush=True)
