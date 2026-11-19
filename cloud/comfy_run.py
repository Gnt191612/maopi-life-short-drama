# 在仙宫云实例上运行：把 ComfyUI 界面格式的工作流转成 API 格式，替换输入图和提示词，逐张出图，结果存 /root/v11_out
# 用法：python3 comfy_run.py <工作流文件名> <输入图1,输入图2,...> [附加在「转为真实照片」提示词前面的描述]
# 例（白模 → 照片级，镜像「Moss/Krea2 超写实人像」）：python3 comfy_run.py Krea2-二转三-图生图-新版.json classB_face_front.png "一位20岁的中国女大学生，"
# 已验证：RTX 4090D 上约 1 分钟/张（2026-11-19）
import json, sys, time, urllib.request, urllib.parse, os
URL = 'http://127.0.0.1:8188'
WF = '/root/ComfyUI/user/default/workflows/' + sys.argv[1]
IMAGES = sys.argv[2].split(',')
EXTRA = sys.argv[3] if len(sys.argv) > 3 else ''
OUT = '/root/v11_out'; os.makedirs(OUT, exist_ok=True)

def get(path): return json.loads(urllib.request.urlopen(URL + path, timeout=60).read())
def post(path, data):
    req = urllib.request.Request(URL + path, json.dumps(data).encode(), {'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

info = get('/object_info')
w = json.load(open(WF, encoding='utf-8'))
links = {l[0]: l for l in w['links']}
WIDGET_T = ('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO')

def convert():
    api = {}
    for n in w['nodes']:
        t = n['type']
        if t in ('Note', 'MarkdownNote', 'Reroute') or n.get('mode') in (2, 4): continue
        spec = info.get(t)
        if spec is None: print('UNKNOWN NODE', t); continue
        ins = {}
        linked = {i['name']: i['link'] for i in n.get('inputs', []) if i.get('link') is not None}
        for name, lid in linked.items():
            l = links[lid]; ins[name] = [str(l[1]), l[2]]
        vals = list(n.get('widgets_values') or [])
        if isinstance(n.get('widgets_values'), dict): vals = []
        if t.startswith('Power Lora Loader'):
            k = 0
            for v in vals:
                if isinstance(v, dict) and 'lora' in v:
                    k += 1; ins['lora_%d' % k] = v
            ins['➕ Add Lora'] = ''
            api[str(n['id'])] = {'class_type': t, 'inputs': ins}; continue
        order = list(spec['input'].get('required', {}).items()) + list(spec['input'].get('optional', {}).items())
        vi = 0
        for name, s in order:
            typ = s[0]
            is_widget = isinstance(typ, list) or typ in WIDGET_T
            if not is_widget: continue
            if vi >= len(vals): break
            v = vals[vi]; vi += 1
            if name not in ins: ins[name] = v
            opt = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
            if typ == 'INT' and (opt.get('control_after_generate') or name in ('seed', 'noise_seed')): vi += 1   # 跳过「生成后控制」
        api[str(n['id'])] = {'class_type': t, 'inputs': ins}
    return api

base = convert()
for img in IMAGES:
    api = json.loads(json.dumps(base))
    for nid, nd in api.items():
        if nd['class_type'] == 'LoadImage': nd['inputs']['image'] = img
        if EXTRA and nd['class_type'].startswith('TextEncode') and '真实照片' in str(nd['inputs'].get('prompt', nd['inputs'].get('text', ''))):
            key = 'prompt' if 'prompt' in nd['inputs'] else 'text'
            nd['inputs'][key] = EXTRA + nd['inputs'][key]
    r = post('/prompt', {'prompt': api})
    pid = r.get('prompt_id'); print('QUEUED', img, pid, r.get('node_errors') or '', flush=True)
    t0 = time.time()
    while True:
        time.sleep(3)
        h = get('/history/' + pid)
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error': print('ERROR', json.dumps(st)[:1500]); break
            for nid, o in h[pid].get('outputs', {}).items():
                for im in o.get('images', []):
                    q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im['subfolder'], 'type': im['type']})
                    data = urllib.request.urlopen(URL + '/view?' + q).read()
                    p = os.path.join(OUT, 'real_' + img.rsplit('.', 1)[0] + '.png'); open(p, 'wb').write(data)
                    print('SAVED', p, '%.0fs' % (time.time() - t0), flush=True)
            break
        if time.time() - t0 > 600: print('TIMEOUT', img); break
