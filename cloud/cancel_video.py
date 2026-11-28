# -*- coding: utf-8 -*-
"""只取消 ComfyUI 里的视频任务（含 MiniMax H3 主模型的），首帧/尾帧任务不动（11-28）。
先停掉调视频的进程（否则它会再提交），再运行：python3 cancel_video.py --yes（不加 --yes 只列出，不动队列）
踩坑 86：停进程不会取消已提交的任务；/interrupt 只打断正在跑的那个——正在跑的若是首帧就不能 interrupt。
11-28：随手多跑了一次，把刚开跑的新任务也打断了，所以要显式 --yes。"""
import sys, json, urllib.request
U = 'http://127.0.0.1:8188'
def post(p, d): urllib.request.urlopen(urllib.request.Request(U + p, json.dumps(d).encode(), {'Content-Type': 'application/json'})).read()
q = json.load(urllib.request.urlopen(U + '/queue'))
is_vid = lambda item: any('minimax_h3' in str(n.get('inputs', {}).get('unet_name', '')) for n in item[2].values())
shot = lambda item: next((str(n['inputs'].get('image')) for n in item[2].values() if n.get('class_type') == 'LoadImage'), '?')
pend = [it for it in q['queue_pending'] if is_vid(it)]; run = [it for it in q['queue_running'] if is_vid(it)]
print('正在跑的视频任务：', [shot(i) for i in run], '  等待中的视频任务：', [shot(i) for i in pend])
if '--yes' not in sys.argv: sys.exit('（只列出；确认要取消就加 --yes）')
if pend: post('/queue', {'delete': [it[1] for it in pend]})
if run: post('/interrupt', {})
print('删除等待中的视频任务 %d 个，打断正在跑的视频任务 %d 个' % (len(pend), len(run)))
