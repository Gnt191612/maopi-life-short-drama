# -*- coding: utf-8 -*-
"""双参考编辑（云端）：用镜像自带的「Krea2-双参考编辑-图生图」工作流改关键帧里的人物。
图1 = 要改的关键帧，图2 = 人物库标准照（给出这个人应有的长相、发型、服装），输出尺寸按原图比例显式设定。
2026-11-25：原来 edit_photo.py 借用「二转三」工作流做编辑，那个工作流没有输出尺寸参数，出来的是左右拼接的半宽图，
关键帧和视频里出现两个林母；多人同框时只靠文字描述也改不对陈瑶。
节点（probe.txt）：66/52 LoadImage（图1/图2）、34 TextEncodeKrea2OstrisEdit（指令）、6 EmptyLatentImage（宽高）、7 KSampler（种子）
用法：python3 edit_ref.py <图1（ComfyUI/input 下）> <图2（ComfyUI/input 下，可与图1相同）> <输出名> <指令> [种子]
输出 /root/v11_out/<输出名>.png；打印 SAVED <路径>，失败打印 FAIL"""
import sys, os, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from PIL import Image
WF = 'Krea2-双参考编辑-图生图.json'
img1, img2, name, inst = sys.argv[1:5]; seed = int(sys.argv[5]) if len(sys.argv) > 5 else 11
w0, h0 = Image.open(os.path.join('/root/ComfyUI/input', img1)).size
W = 1920 if w0 >= h0 else round(1920 * w0 / h0 / 16) * 16
H = round(W * h0 / w0 / 16) * 16                                   # 和原图同比例，16 的倍数
api = comfy_run.convert(WF)
api['66']['inputs']['image'] = img1; api['52']['inputs']['image'] = img2
api['34']['inputs']['text'] = inst
api['6']['inputs']['width'] = W; api['6']['inputs']['height'] = H; api['6']['inputs']['batch_size'] = 1
api['7']['inputs']['seed'] = seed
r = comfy_run._post('/prompt', {'prompt': api}); pid = r.get('prompt_id')
if r.get('node_errors'): print('NODE ERRORS', r['node_errors'], flush=True)
for _ in range(400):
    time.sleep(3); h = comfy_run._get('/history/' + pid)
    if pid in h and h[pid].get('outputs'): break
else:
    print('FAIL timeout', flush=True); sys.exit(1)
cands = []
for nid, o in h[pid]['outputs'].items():
    for j, im in enumerate(o.get('images', [])):
        q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im.get('subfolder', ''), 'type': im.get('type', 'output')})
        p = os.path.join(comfy_run.OUT, '%s_n%s_%d.png' % (name, nid, j)); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read())
        sz = Image.open(p).size; print('输出', nid, im.get('type'), sz, flush=True)
        cands.append((abs(sz[0] / sz[1] - W / H) + (0 if im.get('type') != 'temp' else 0.01), p))   # 比例最接近设定宽高的那张；同比例时优先正式输出
if not cands: print('FAIL no output', flush=True); sys.exit(1)
best = min(cands)[1]; out = os.path.join(comfy_run.OUT, name + '.png'); os.replace(best, out)
print('SAVED', out, Image.open(out).size, flush=True)
