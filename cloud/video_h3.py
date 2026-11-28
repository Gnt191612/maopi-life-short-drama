# -*- coding: utf-8 -*-
"""MiniMax H3 白模动作控制视频（写实化实例上运行，2026-11-27 选型：开放权重视频模型里排名第一，见踩坑记录 58、60）
按 ComfyUI 官方模板 video_minimax_h3_fun_controlnet_union.json 的结构直接搭 API 图（cloud/wf_templates 里有原件）：
  UNETLoader(minimax_h3_ref2va) [+ 4 步 turbo LoRA] → MiniMaxH3FunControlNetApply(控制视频, 强度) ×N → BasicGuider
  MiniMaxH3ReferenceToVideo(提示词, 宽高, 帧数, 参考图 = 写实首帧 + 出场角色标准照 [+ 参考音频]) → SamplerCustomAdvanced(res_multistep) → VAEDecode
  - 控制视频：白模姿态骨架 pose.mp4（定人物位置和动作）+ 白模深度 depth.mp4（定场景和镜头运动，按整个镜头统一拉伸对比度：
    素材包里是 0.1～40 米固定刻度，室内几乎全白，直接用控制力很弱）；默认 姿态 0.7 + 深度 0.3（网上实测两路都开满会糊）
  - 参考图：写实首帧定场景、衣着、光线；角色标准照定长相（多个镜头里同一个人长得一样）
  - H3 原生 24fps，帧数取 17n+5，单段最长 362 帧（约 15 秒）；更长的镜头分段，后一段把上一段最后一帧加进参考图
  - 不用任何「自动反推提示词」
节点的控件名开机时从 /object_info 读，按官方模板里的控件顺序填，缺节点/缺模型直接报错退出
用法：python3 video_h3.py <pack> --only id1,id2 [--res 1344x768] [--steps 20 | --turbo] [--pose 0.7 --depth 0.3] [--ref-audio] [--out 目录] [--dry]"""
import os, sys, json, glob, shutil, subprocess, argparse, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from looks import LOOK_EN, STYLE_EN, NEG_EN
INP = '/root/ComfyUI/input'; KF = '/root/v11_out/kf'; TMP = '/root/v11_out/htmp'; os.makedirs(TMP, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument('pack'); ap.add_argument('--only', default=''); ap.add_argument('--res', default='1344x768')
ap.add_argument('--steps', type=int, default=20); ap.add_argument('--turbo', action='store_true')
ap.add_argument('--pose', type=float, default=0.7); ap.add_argument('--depth', type=float, default=0.3)
ap.add_argument('--ref-audio', action='store_true'); ap.add_argument('--speech', action='store_true'); ap.add_argument('--no-canon', action='store_true')
ap.add_argument('--prec', choices=['int8', 'bf16', 'fp8'], default='int8');   # 主模型精度：int8_convrot（官方首推，需 torch cu130）/ bf16（最精细，40GB，48G 卡上较慢）/ fp8_scaled（没有 cu130 时的后备）
ap.add_argument('--mode', choices=['fl', 'ref'], default='fl'); ap.add_argument('--pika', action='store_true'); ap.add_argument('--union', choices=['auto', '1', '2'], default='auto')
ap.add_argument('--seed', type=int, default=20261127); ap.add_argument('--out', default='/root/v11_out/h3')
ap.add_argument('--force', action='store_true'); ap.add_argument('--dry', action='store_true')
ap.add_argument('--hybrid', action='store_true')   # 混合方案（11-27 用户定）：运镜在动的镜头（push/track/arc）用 20 步完整采样拿运镜，手持/固定镜头（hand/static）用 Pika 6 步拿质感和稳定的脸
ap.add_argument('--subset', choices=['all', 'full', 'pika'], default='all')   # --hybrid 时只跑其中一类（先跑完 20 步的再跑 Pika 的，少切换模型）
ap.add_argument('--approved', default='')   # 首帧审批清单（每行/空格分隔的镜头 id）：只跑审过合格的首帧，每个镜头开始前重新读（11-27：没审的首帧被拿去跑视频）
ap.add_argument('--frames', type=int, default=0)   # 只跑前 N 帧（便宜的对比测试用，如 SageAttention 测速；0 = 整个镜头）
args = ap.parse_args()
W, H = [int(v) for v in args.res.split('x')]; OUT = args.out; os.makedirs(OUT, exist_ok=True); MAXF = 362
def log(*a):
    s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a); print(s, flush=True)
    open('/root/v11_out/h3_progress.log', 'a', encoding='utf-8').write(s + '\n')
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y'] + list(a), check=True)
def grid(n): return max(5, n + (5 - n % 17) % 17)   # 17n+5（向上取整，多出的尾帧最后裁掉）

INFO = comfy_run._get('/object_info')
def spec(cls):
    if cls not in INFO: sys.exit('缺少节点 %s：ComfyUI 版本太旧或没装 H3 支持（官方要求 0.35.0+）' % cls)
    s = INFO[cls]['input']; return list(s.get('required', {}).items()) + list(s.get('optional', {}).items())
def pool(cls, name):
    for k, v in spec(cls):
        if k == name and isinstance(v[0], list): return v[0]
    return []
def pick(cls, name, *pats):   # 在下拉框里找文件：按给的关键词依次匹配，找不到就退出
    files = pool(cls, name)
    for p in pats:
        hit = [f for f in files if all(s in f.lower() for s in p.split('*'))]
        if hit: return sorted(hit, key=len)[0]
    sys.exit('缺少模型：%s.%s 里找不到 %s（先运行 setup_h3.sh）' % (cls, name, pats))
WIDGET_T = ('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO')
def widgets(cls, vals):   # 按 object_info 的控件顺序把模板里的控件值配上名字（和 comfy_run.convert 一样跳过「生成后控制」）
    out, vi = {}, 0
    for nm, s in spec(cls):
        typ = s[0]
        if not (isinstance(typ, list) or typ in WIDGET_T): continue
        if vi >= len(vals): break
        out[nm] = vals[vi]; vi += 1
        opt = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
        if typ == 'INT' and (opt.get('control_after_generate') or nm in ('seed', 'noise_seed')): vi += 1
    return out

# fl = 首帧模式（fl2va：写实首帧就是第一帧，构图和场景保持最强，分段时下一段用上一段最后一帧接上；默认）
# ref = 参考图模式（ref2va：首帧和角色标准照只当参考，可加参考音频）
_P = {'int8': 'int8_convrot', 'bf16': 'bf16', 'fp8': 'fp8_scaled'}[args.prec]   # pruned 版只重整了 AdaLN 调制结构，输出与官方等效，不降画质
_M = 'fl2va' if args.mode == 'fl' else 'ref2va'   # 先找 pruned 版（省显存），再找同精度的完整版（镜像自带 minimax_h3_fl2va_bf16），最后才退回 int8
UNET = pick('UNETLoader', 'unet_name', 'minimax_h3_%s_pruned_%s' % (_M, _P), 'minimax_h3_%s_%s' % (_M, _P), 'minimax_h3_%s_pruned_int8' % _M, 'minimax_h3_%s' % _M)
if _P not in UNET: log('注意：没找到 %s 精度的主模型，实际用的是 %s' % (_P, UNET))
TE = pick('CLIPLoader', 'clip_name', 'minimax_h3', 'qwen3vl*h3')
VVAE = pick('VAELoader', 'vae_name', 'h3_video_vae', 'minimax_h3*video')
AVAE = pick('VAELoader', 'vae_name', 'h3_audio_vae', 'minimax_h3*audio')
_u2 = [f for f in pool('ModelPatchLoader', 'name') if 'union_2' in f.lower()]   # Union 2.0（2026-09-22）注入层加倍，ComfyUI 0.38+；没有就用 1.0
PATCH = (sorted(_u2, key=lambda f: ('int8' not in f, len(f)))[0] if _u2 and args.union != '1' else pick('ModelPatchLoader', 'name', 'h3_fun_controlnet_union_pruned_int8', 'h3_fun_controlnet', 'h3*controlnet'))
if args.union == '2' and not _u2: sys.exit('缺少 ControlNet Union 2.0（先运行 setup_h3.sh）')
LORA = (pick('LoraLoaderModelOnly', 'lora_name', 'h3_fl2v_turbo_4step', 'h3_fl2v_turbo') if args.mode == 'fl' else pick('LoraLoaderModelOnly', 'lora_name', 'h3_ref2v_turbo', 'h3*turbo')) if args.turbo else None
PIKA = pick('LoraLoaderModelOnly', 'lora_name', 'pika_h3_flex_%s_v1' % _M, 'pika_h3_flex_%s_comfy' % _M, 'pika_h3_flex_%s' % _M) if (args.pika or args.hybrid) else None   # 不要选 pika_h3_flex_turbo_*（另一种加速版）   # Pika H3 Flex：真实感/清晰度后训练（2026-10-29），叠在 H3 上
CLIP_T = 'minimax' if 'minimax' in pool('CLIPLoader', 'type') else pool('CLIPLoader', 'type')[0]
for c in (('MiniMaxH3ImageToVideo' if args.mode == 'fl' else 'MiniMaxH3ReferenceToVideo'), 'MiniMaxH3FunControlNetApply', 'ModelPatchLoader', 'LoadVideo', 'GetVideoComponents', 'SamplerCustomAdvanced', 'BasicGuider', 'KSamplerSelect', 'BasicScheduler', 'RandomNoise') + (('ManualSigmas',) if (args.pika or args.hybrid) else ()): spec(c)
USE_PIKA = [bool(args.pika)]   # 当前镜头是否用 Pika（--hybrid 时按镜头运镜类型逐个设置）
def pika_for(task): return bool(args.pika) or (args.hybrid and task.get('move', 'static') in ('hand', 'static', 'push'))   # 11-27 余额 74.8 元：推镜头运动轻、也用 Pika，20 步只留给跟拍/环绕（运镜幅度最大的 35 个），省约 11 元留出补拍余量
log('节点和模型核对通过', args.mode, UNET, TE, PATCH, LORA or '（不用 turbo）', PIKA or '（不用 Pika）', '%dx%d' % (W, H), 'steps', 4 if args.turbo else args.steps)

import h3_prompt   # 提示词按 MiniMax 官方写作规范生成（cloud/h3_prompt.py，docs/prompts/）
def prompt_of(task, lines=None):
    return h3_prompt.build(task, 'i2va' if args.mode == 'fl' else 'ref', lines, args.speech)

def graph(refs, controls, n, prompt, seed, audio=None):
    A = {}; k = [0]
    def node(cls, links=None, vals=None, **named):
        k[0] += 1; i = str(k[0]); inp = dict(widgets(cls, vals or [])); inp.update(named); inp.update(links or {})
        A[i] = {'class_type': cls, 'inputs': inp}; return i
    m = node('UNETLoader', vals=[UNET, 'default'])
    if LORA: m = node('LoraLoaderModelOnly', {'model': [m, 0]}, [LORA, 1.0])
    if PIKA and USE_PIKA[0]: m = node('LoraLoaderModelOnly', {'model': [m, 0]}, [PIKA, 1.0])
    clip = node('CLIPLoader', vals=[TE, CLIP_T, 'default']); vv = node('VAELoader', vals=[VVAE]); av = node('VAELoader', vals=[AVAE])
    patch = node('ModelPatchLoader', vals=[PATCH])
    for vid, w in controls:   # 每路控制视频套一层 ControlNet（姿态、深度）
        v = node('LoadVideo', vals=[vid, 'image']); fr = node('GetVideoComponents', {'video': [v, 0]})
        m = node('MiniMaxH3FunControlNetApply', {'model': [m, 0], 'model_patch': [patch, 0], 'vae': [vv, 0], 'control_video': [fr, 0]}, [w, 0.0, 1.0])
    if args.mode == 'fl':   # 首帧模式：refs[0] = 这一段的第一帧（第一段是写实首帧，后面是上一段最后一帧）
        r2v = node('MiniMaxH3ImageToVideo', {'clip': [clip, 0], 'vae': [vv, 0], 'first_frame': [node('LoadImage', vals=[refs[0], 'image']), 0]}, [prompt, W, H, n])
    else:
        links = {'clip': [clip, 0], 'vae': [vv, 0], 'audio_vae': [av, 0]}
        for j, r in enumerate(refs): links['ref_images.ref_image_%d' % j] = [node('LoadImage', vals=[r, 'image']), 0]
        if audio: links['ref_audios.ref_audio_0'] = [node('LoadAudio', vals=[audio]), 0]
        r2v = node('MiniMaxH3ReferenceToVideo', links, [prompt, W, H, n, 'match'])
    g = node('BasicGuider', {'model': [m, 0], 'conditioning': [r2v, 0]})
    if PIKA and USE_PIKA[0]:   # Pika H3 Flex 按 ComfyUI 官方模板 video_pika_h3_flex_fl2va：LCM 采样器 + 作者固定的 6 步 sigma（不是普通 20 步）
        smp = node('KSamplerSelect', vals=['lcm'])
        sig = node('ManualSigmas', vals=['1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0'])
    else:
        smp = node('KSamplerSelect', vals=['res_multistep'])
        sig = node('BasicScheduler', {'model': [m, 0]}, ['simple', 4 if args.turbo else args.steps, 1.0])
    noise = node('RandomNoise', vals=[seed, 'fixed'])
    s = node('SamplerCustomAdvanced', {'noise': [noise, 0], 'guider': [g, 0], 'sampler': [smp, 0], 'sigmas': [sig, 0], 'latent_image': [r2v, 1]})
    dec = node('VAEDecode', {'samples': [s, 0], 'vae': [vv, 0]})
    node('SaveImage', {'images': [dec, 0]}, ['h3_tmp'])
    if args.speech:   # H3 原生音频：人物按提示词里的台词说话、口型同步，音色照参考配音（11-27 用户：现在的配音不够像真人说话）
        au = node('VAEDecodeAudio', {'samples': [s, 0], 'vae': [av, 0]}); node('SaveAudio', {'audio': [au, 0]}, ['h3_audio'])
    return A

def run(A, tag):
    if args.dry: print(json.dumps(A, ensure_ascii=False)[:3000]); return []
    r = comfy_run._post('/prompt', {'prompt': A}); pid = r.get('prompt_id')
    if not pid: sys.exit('排队失败 %s（上面 REJECTED 是 ComfyUI 给的原因）' % tag)
    if r.get('node_errors'): sys.exit('节点错误 %s %s' % (tag, json.dumps(r['node_errors'], ensure_ascii=False)[:2000]))
    for _ in range(2400):
        time.sleep(3); h = comfy_run._get('/history/' + pid)
        if pid in h and h[pid].get('status', {}).get('status_str') == 'error': raise RuntimeError('生成失败 %s %s' % (tag, json.dumps(h[pid]['status'], ensure_ascii=False)[:600]))
        if pid in h and h[pid].get('status', {}).get('completed'): break
    else: raise RuntimeError('超时 %s' % tag)
    for o in h[pid]['outputs'].values():
        for a in o.get('audio', []):
            q = urllib.parse.urlencode({'filename': a['filename'], 'subfolder': a.get('subfolder', ''), 'type': a.get('type', 'output')})
            open(os.path.join(TMP, '%s_audio%s' % (tag, os.path.splitext(a['filename'])[1])), 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read())
    out = []
    for j, im in enumerate(im for o in h[pid]['outputs'].values() for im in o.get('images', [])):
        q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im.get('subfolder', ''), 'type': im.get('type', 'output')})
        p = os.path.join(TMP, '%s_%04d.png' % (tag, j)); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read()); out.append(p)
    return out

def depth_stretch(src, dst, n):   # 整个镜头统一拉伸（逐帧拉伸会闪）：取全镜头 2%～98% 分位
    import numpy as np, cv2
    c = cv2.VideoCapture(src); fr = []
    while True:
        ok, im = c.read()
        if not ok: break
        fr.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    a = np.stack(fr).astype(np.float32); lo, hi = np.percentile(a, 2), np.percentile(a, 98)
    a = np.clip((a - lo) / max(hi - lo, 1) * 255, 0, 255).astype(np.uint8)
    tmp = dst + '.d'; os.makedirs(tmp, exist_ok=True)
    for i, g in enumerate(a): cv2.imwrite(os.path.join(tmp, '%05d.png' % i), cv2.merge([g, g, g]))
    ff('-framerate', '24', '-i', os.path.join(tmp, '%05d.png'), '-vf', 'scale=%d:%d:flags=lanczos,tpad=stop_mode=clone:stop_duration=2' % (W, H), '-frames:v', str(n),
       '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', dst); shutil.rmtree(tmp)

pack = args.pack; only = [x for x in args.only.split(',') if x]
man = json.load(open(os.path.join(pack, 'manifest.json'), encoding='utf-8'))
for tid in man['tasks']:
    if only and not any(tid.startswith(x) for x in only): continue
    if os.path.exists(os.path.join(OUT, tid + '.mp4')) and not args.force: log('已有，跳过', tid); continue
    td = os.path.join(pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
    kf = os.path.join(KF, tid + '.png')
    while os.path.exists('/root/v11_out/PAUSE_VIDEO'): time.sleep(20)   # 暂停开关：首帧重做时先让出显卡（11-27：首帧和视频交替排队，每步首帧都要等一个 20 分钟的视频）
    if not os.path.exists(kf): log('跳过（没有写实首帧）', tid); continue
    if args.approved and tid not in (open(args.approved, encoding='utf-8').read().split() if os.path.exists(args.approved) else []): log('跳过（首帧还没审过）', tid); continue
    n24 = min(task['n'], args.frames) if args.frames else task['n']; t0 = time.time()
    USE_PIKA[0] = pika_for(task)
    if args.subset != 'all' and (args.subset == 'pika') != USE_PIKA[0]: continue   # 不属于这一批
    log(tid, '用 Pika 6 步' if USE_PIKA[0] else '用 20 步完整采样', '运镜', task.get('move'))
    ctl = []   # (完整控制视频, 强度)
    if args.pose > 0 and os.path.exists(os.path.join(td, 'pose.mp4')) and task.get('characters'):
        p = os.path.join(TMP, tid + '_pose.mp4')
        ff('-i', os.path.join(td, 'pose.mp4'), '-vf', 'scale=%d:%d:flags=lanczos,tpad=stop_mode=clone:stop_duration=2' % (W, H), '-frames:v', str(n24 + 2), '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', p)
        ctl.append((p, float(task.get('pose_w', args.pose))))   # task.json 可单独指定（11-27：跟拍镜头露出首帧外的空间时，弱控制会编出新房间、复制出第二个人）
    if args.depth > 0:
        p = os.path.join(TMP, tid + '_depth.mp4'); depth_stretch(os.path.join(td, 'depth.mp4'), p, n24 + 2)
        d0 = max(args.depth, 0.55) if USE_PIKA[0] else args.depth   # Pika 手持/固定特写默认深度 0.55（11-28：0.3 时背景中途换成另一个房间，s03_02_0001 林母连衣服长相都变了）
        ctl.append((p, float(task.get('depth_w', d0 if task.get('characters') else max(d0, 0.8)))))   # 无人空镜只有深度，强度加大
    first = 'h3ref_%s.png' % tid; ff('-i', kf, '-vf', 'scale=%d:%d:flags=lanczos' % (W, H), os.path.join(INP, first))
    canon = [] if args.no_canon else ['canon_%s.jpg' % c for c in task.get('characters', []) if os.path.exists(os.path.join(INP, 'canon_%s.jpg' % c))]
    audio = None
    if args.ref_audio and os.path.exists(os.path.join(td, 'voice.wav')):
        audio = 'h3voice_%s.wav' % tid; shutil.copy(os.path.join(td, 'voice.wav'), os.path.join(INP, audio))
    vlines = h3_prompt.load_lines(td)   # 全部台词（含多人、画外音），不只是口型同步用的 voice.json（11-27 审查）
    prompt = prompt_of(task, vlines)
    if args.speech and vlines and not audio and os.path.exists(os.path.join(td, 'voice.wav')) and args.mode == 'ref':
        audio = 'h3voice_%s.wav' % tid; shutil.copy(os.path.join(td, 'voice.wav'), os.path.join(INP, audio))
    frames, s, k, extra = [], 0, 0, []
    while s < n24 - 1 or not frames:
        n = grid(min(MAXF, n24 - s))
        if n > MAXF: n = MAXF - 17
        segs = []
        for j, (p, w) in enumerate(ctl):
            seg = 'h3ctl_%s_%d_%02d.mp4' % (tid, j, k)
            ff('-ss', '%.4f' % (s / 24.0), '-i', p, '-vf', 'tpad=stop_mode=clone:stop_duration=16', '-frames:v', str(n), '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', os.path.join(INP, seg))
            segs.append((seg, w))
        refs = ([extra[0]] if extra else [first]) if args.mode == 'fl' else [first] + extra + canon   # 首帧模式：续接段的第一帧 = 上一段最后一帧
        try:
            imgs = run(graph(refs, segs, n, prompt, args.seed, audio if k == 0 else None), '%s_%02d' % (tid, k))
        except RuntimeError as e:   # 一个镜头失败只跳过它（下一轮重试），不让整批退出（11-27：取消一个任务后整批 Pika 都停了）
            log(tid, '本轮失败，跳过', str(e)[:200]); frames = None; break
        if args.dry: break
        if k: imgs = imgs[1:]
        frames += imgs; k += 1
        last = 'h3last_%s_%02d.png' % (tid, k); shutil.copy(imgs[-1], os.path.join(INP, last)); extra = [last]   # 续接段：上一段最后一帧也当参考
        s += n - 1
        log(tid, '段 %d' % k, '%d/%d 帧' % (len(frames), n24), '%.0f 秒' % (time.time() - t0))
    if args.dry or frames is None: continue   # frames is None：本轮生成失败，留到下一轮
    od = os.path.join(OUT, tid); shutil.rmtree(od, ignore_errors=True); os.makedirs(od)
    for i, f in enumerate(frames[:n24]): shutil.move(f, os.path.join(od, 'frame_%04d.png' % (task['frames'][0] + i)))
    ff('-framerate', '24', '-start_number', str(task['frames'][0]), '-i', os.path.join(od, 'frame_%04d.png'), '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', os.path.join(OUT, tid + '.mp4'))
    if os.path.exists(os.path.join(OUT, tid + '.mp4')): shutil.rmtree(od, ignore_errors=True)   # 逐帧 PNG 合成 mp4 后即删（每镜约 300MB，全片会塞满 125G 系统盘，11-27）
    for a in sorted(glob.glob(os.path.join(TMP, '%s_*_audio.*' % tid))):   # 原生语音：多段按顺序接起来，存成 <id>.speech.wav
        shutil.copy(a, os.path.join(OUT, '%s.speech%s' % (tid, os.path.splitext(a)[1]))); break
    for f in glob.glob(os.path.join(TMP, '%s_*' % tid)): os.remove(f)
    log('完成', tid, '%d 帧' % n24, '%.0f 秒' % (time.time() - t0), '%.2f 秒/帧' % ((time.time() - t0) / n24))
print('H3 DONE', flush=True)
