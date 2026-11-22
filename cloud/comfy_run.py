# 在仙宫云实例上运行：把 ComfyUI 界面格式的工作流转成 API 格式，按需改输入（图片、提示词、种子），排队出图，结果存 /root/v11_out
# 命令行：python3 comfy_run.py <工作流文件名> <输出名> [节点号.输入名=值 ...]
#   例（白模 → 照片级）：python3 comfy_run.py Krea2-二转三-图生图-新版.json canon_classB 10.image=classB_face_front.png
# 也可作为模块：import comfy_run; comfy_run.run(工作流, 输出名, {'66.image': 'a.png'}, prefix='一位…，')
# 已验证：RTX 4090D 上约 1 分钟/张（2026-11-19）
import json, sys, time, urllib.request, urllib.parse, os
URL = 'http://127.0.0.1:8188'
WFDIR = '/root/ComfyUI/user/default/workflows/'
OUT = '/root/v11_out'; os.makedirs(OUT, exist_ok=True)
WIDGET_T = ('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO')
_info = None

def _get(path): return json.loads(urllib.request.urlopen(URL + path, timeout=60).read())
def _post(path, data):
    req = urllib.request.Request(URL + path, json.dumps(data).encode(), {'Content-Type': 'application/json'})
    try: return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:   # 工作流校验失败：把 ComfyUI 给的原因打出来
        print('REJECTED', e.read().decode('utf-8', 'replace')[:2000], flush=True); return {}

def convert(name, enable=()):
    """界面格式 → API 格式。界面专用节点（分组开关、注释）跳过；连到被跳过节点的输入改用控件值。
    enable：强制启用的节点号（作者用分组开关默认关掉的，如「第二参考」）；直通（bypass）节点按原样把输入接给下游"""
    global _info
    _info = _info or _get('/object_info')
    w = json.load(open(WFDIR + name, encoding='utf-8'))
    links = {l[0]: l for l in w['links']}
    nodes = {n['id']: n for n in w['nodes']}
    mode = lambda n: 0 if n['id'] in enable else n.get('mode', 0)
    keep = {n['id'] for n in w['nodes'] if n['type'] in _info and mode(n) == 0}
    def src(l):   # 沿直通节点往上找真正的来源：[节点号, 输出口]
        while l and nodes[l[1]].get('mode') == 4 and l[1] not in enable:
            up = next((links.get(i.get('link')) for i in nodes[l[1]].get('inputs', []) if i.get('type') == l[5] and i.get('link') is not None), None)
            l = up
        return l
    api = {}
    for n in w['nodes']:
        if n['id'] not in keep: continue
        t = n['type']; spec = _info[t]; ins = {}
        for i in n.get('inputs', []):
            l = src(links.get(i.get('link')))
            if l and l[1] in keep: ins[i['name']] = [str(l[1]), l[2]]
        vals = n.get('widgets_values') if isinstance(n.get('widgets_values'), list) else []
        if t.startswith('Power Lora Loader'):
            k = 0
            for v in vals:
                if isinstance(v, dict) and 'lora' in v: k += 1; ins['lora_%d' % k] = v
            ins['➕ Add Lora'] = ''
        else:
            vi = 0
            for nm, s in list(spec['input'].get('required', {}).items()) + list(spec['input'].get('optional', {}).items()):
                typ = s[0]
                if not (isinstance(typ, list) or typ in WIDGET_T): continue
                if vi >= len(vals): break
                v = vals[vi]; vi += 1
                ins.setdefault(nm, v)
                opt = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
                if typ == 'INT' and (opt.get('control_after_generate') or nm in ('seed', 'noise_seed')): vi += 1   # 跳过「生成后控制」
            for nm, s in spec['input'].get('required', {}).items():   # 工作流里没存的控件值：用节点默认值（下拉框取第一项）
                if nm in ins: continue
                opt = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
                if 'default' in opt: ins[nm] = opt['default']
                elif isinstance(s[0], list) and s[0]: ins[nm] = s[0][0]
        api[str(n['id'])] = {'class_type': t, 'inputs': ins}
    for nid, nd in list(api.items()):   # 依赖被跳过节点输出的展示类节点（对比图等）一并去掉
        if any(isinstance(v, list) and v[0] not in api for v in nd['inputs'].values()): api.pop(nid)
    return api

def run(name, out_name, sets=None, prefix='', timeout=900, enable=()):
    api = convert(name, enable)
    for key, val in (sets or {}).items():
        nid, inp = key.split('.', 1); api[nid]['inputs'][inp] = val
    if prefix:   # 加在「转为真实照片」那条提示词前面（二转三工作流用）
        for nd in api.values():
            for k in ('prompt', 'text'):
                if '真实照片' in str(nd['inputs'].get(k, '')): nd['inputs'][k] = prefix + nd['inputs'][k]
    r = _post('/prompt', {'prompt': api}); pid = r.get('prompt_id')
    if not pid: return None
    if r.get('node_errors'): print('NODE ERRORS', json.dumps(r['node_errors'], ensure_ascii=False)[:1500], flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3); h = _get('/history/' + pid)
        if pid not in h: continue
        if h[pid].get('status', {}).get('status_str') == 'error':
            print('ERROR', out_name, json.dumps(h[pid]['status'], ensure_ascii=False)[:1500], flush=True); return None
        saved = []   # 图片在 images，视频（VHS 合成节点等）在 gifs / videos；预览类（temp）不要
        for o in h[pid].get('outputs', {}).values():
            for key in ('gifs', 'videos', 'images'):
                for im in o.get(key, []):
                    if im.get('type') == 'temp' and any(x.get('type') != 'temp' for oo in h[pid]['outputs'].values() for kk in ('gifs', 'videos', 'images') for x in oo.get(kk, [])): continue   # 有正式输出时跳过预览图
                    ext = os.path.splitext(im['filename'])[1] or '.png'
                    q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im.get('subfolder', ''), 'type': im.get('type', 'output')})
                    p = os.path.join(OUT, out_name + ('' if not saved else '_%d' % len(saved)) + ext)
                    open(p, 'wb').write(urllib.request.urlopen(URL + '/view?' + q).read()); saved.append(p)
        if saved:
            print('SAVED', ' '.join(saved), '%.0fs' % (time.time() - t0), flush=True)
            vids = [p for p in saved if p.lower().endswith(('.mp4', '.webm', '.mov', '.gif'))]
            return (vids or saved)[0]
        return None
    print('TIMEOUT', out_name, flush=True)

if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], dict(a.split('=', 1) for a in sys.argv[3:]))
