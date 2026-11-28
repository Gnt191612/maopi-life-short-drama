# -*- coding: utf-8 -*-
"""只取消 ComfyUI 里的视频任务（含 MiniMax H3 主模型的），首帧/尾帧任务不动（11-28）。
先停掉调视频的进程（否则它会再提交），再运行本脚本：python3 cancel_video.py
踩坑 86：停进程不会取消已提交的任务；/interrupt 只打断正在跑的那个——正在跑的若是首帧就不能 interrupt。"""
import json, urllib.request
U = 'http://127.0.0.1:8188'
def post(p, d): urllib.request.urlopen(urllib.request.Request(U + p, json.dumps(d).encode(), {'Content-Type': 'application/json'})).read()
q = json.load(urllib.request.urlopen(U + '/queue'))
is_vid = lambda item: any('minimax_h3' in str(n.get('inputs', {}).get('unet_name', '')) for n in item[2].values())
pend = [it[1] for it in q['queue_pending'] if is_vid(it)]
if pend: post('/queue', {'delete': pend})
run = [it for it in q['queue_running'] if is_vid(it)]
if run: post('/interrupt', {})
print('删除等待中的视频任务 %d 个，打断正在跑的视频任务 %d 个' % (len(pend), len(run)))
