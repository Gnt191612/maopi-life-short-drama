# -*- coding: utf-8 -*-
"""ComfyUI 队列管理（云端）：python3 qctl.py status | clear（清掉排队中的，不动正在跑的）| interrupt（打断正在跑的）"""
import sys, json, urllib.request
U = 'http://127.0.0.1:8188'
def post(p, d):
    r = urllib.request.Request(U + p, json.dumps(d).encode(), {'Content-Type': 'application/json'}); return urllib.request.urlopen(r, timeout=30).read()
q = json.loads(urllib.request.urlopen(U + '/queue', timeout=30).read())
cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
if cmd == 'clear': post('/queue', {'delete': [x[1] for x in q['queue_pending']]})
if cmd == 'interrupt': post('/interrupt', {})
q = json.loads(urllib.request.urlopen(U + '/queue', timeout=30).read())
print('running', len(q['queue_running']), 'pending', len(q['queue_pending']), flush=True)
