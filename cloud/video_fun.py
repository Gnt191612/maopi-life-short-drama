# -*- coding: utf-8 -*-
"""白模动作控制视频（写实化实例上运行，2026-11-27 起替代 video_run.py 的图生视频做法，见踩坑记录 58）：
  Wan2.2 Fun Control 14B（高噪/低噪两段 + lightx2v 4 步 LoRA）
  - 控制视频 = 素材包里白模渲染的深度视频 depth.mp4（固定 0.1~40 米映射、近白远黑，全片同一标尺）：人物走位、道具、镜头运动逐帧跟白模
  - 首帧 = keyframes.py 做好的写实关键帧 kf/<任务id>.png：定长相、衣着、场景质感；整个镜头只用这一张，不再用锚点（锚点之间硬过渡是「飘」的根源）
  - 长镜头按 81 帧一段，后一段用前一段最后一帧当首帧、控制视频接着往下走（同一镜头固定种子）
  - 不用「自动反推提示词」，提示词完全由 task.json + 人物库外貌组成
  - 16fps 生成 → RIFE 插到 48fps → 取偶数帧 = 24fps，帧号与白模时间轴一致
节点和输入名在开机后从 /object_info 自动核对，缺节点或缺模型直接报错退出（不会静默跑出错的东西）
用法：python3 video_fun.py <cloud_pack 目录> --only id1,id2 [--res 1024x576] [--steps 4] [--fps 16] [--dry]
输出：/root/v11_out/fun/<任务id>.mp4（24fps）和 fun/<任务id>/frame_####.png"""
import os, sys, json, glob, shutil, subprocess, argparse, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from looks import LOOK_EN, STYLE_EN, NEG_EN
INP = '/root/ComfyUI/input'; OUT = '/root/v11_out/fun'; KF = '/root/v11_out/kf'; TMP = '/root/v11_out/ftmp'
for d in (OUT, TMP): os.makedirs(d, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument('pack'); ap.add_argument('--only', default=''); ap.add_argument('--res', default='1024x576')
ap.add_argument('--steps', type=int, default=4); ap.add_argument('--fps', type=int, default=16); ap.add_argument('--seed', type=int, default=20261127)
ap.add_argument('--control', default='depth'); ap.add_argument('--no-lora', action='store_true'); ap.add_argument('--dry', action='store_true')
args = ap.parse_args()
W, H = [int(v) for v in args.res.split('x')]; FPS = args.fps; MAXF = 81
MODELS = dict(high='wan2.2_fun_control_high_noise_14B_fp8_scaled.safetensors', low='wan2.2_fun_control_low_noise_14B_fp8_scaled.safetensors',
              lora_high='wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', lora_low='wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
              t5='umt5_xxl_fp8_e4m3fn_scaled.safetensors', vae='wan_2.1_vae.safetensors')

def log(*a):
    s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a); print(s, flush=True)
    open('/root/v11_out/fun_progress.log', 'a', encoding='utf-8').write(s + '\n')
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y'] + list(a), check=True)

INFO = comfy_run._get('/object_info')
def need(cls):
    if cls not in INFO: sys.exit('缺少节点 %s：这个 ComfyUI 版本不支持，先更新 ComfyUI 或装对应节点' % cls)
    return INFO[cls]
def choices(cls, inp):
    spec = INFO[cls]['input'].get('required', {}).get(inp) or INFO[cls]['input'].get('optional', {}).get(inp)
    return spec[0] if spec and isinstance(spec[0], list) else []
for c in ('UNETLoader', 'CLIPLoader', 'VAELoader', 'CLIPTextEncode', 'Wan22FunControlToVideo', 'KSamplerAdvanced', 'VAEDecode', 'ModelSamplingSD3', 'LoadImage', 'SaveImage'):
    need(c)
fc_in = {**INFO['Wan22FunControlToVideo']['input'].get('required', {}), **INFO['Wan22FunControlToVideo']['input'].get('optional', {})}
START_KEY = 'ref_image' if 'ref_image' in fc_in else ('start_image' if 'start_image' in fc_in else None)
if not START_KEY or 'control_video' not in fc_in: sys.exit('Wan22FunControlToVideo 的输入和预期不同：%s' % list(fc_in))
for k, f in MODELS.items():
    pool = choices('UNETLoader', 'unet_name') if k in ('high', 'low') else choices('LoraLoaderModelOnly', 'lora_name') if k.startswith('lora') \
        else choices('CLIPLoader', 'clip_name') if k == 't5' else choices('VAELoader', 'vae_name')
    if f not in pool and not (args.no_lora and k.startswith('lora')): sys.exit('缺少模型 %s（%s）：先运行 setup_fun.sh' % (f, k))
VIDEO_LOADER = 'LoadVideo' if 'LoadVideo' in INFO and 'GetVideoComponents' in INFO else ('VHS_LoadVideo' if 'VHS_LoadVideo' in INFO else None)
if not VIDEO_LOADER: sys.exit('没有可用的视频读取节点（LoadVideo+GetVideoComponents 或 VHS_LoadVideo）')
RIFE = 'RIFE VFI' if 'RIFE VFI' in INFO else None
CLIP_TYPE = 'wan' if 'wan' in choices('CLIPLoader', 'type') else choices('CLIPLoader', 'type')[0]
log('节点核对通过', 'start=%s' % START_KEY, 'video=%s' % VIDEO_LOADER, 'rife=%s' % RIFE, '%dx%d' % (W, H))

def prompt_of(task):
    who = '; '.join(LOOK_EN[c] for c in task.get('characters', []) if c in LOOK_EN)
    desc = task.get('prompt', '').split('. photorealistic')[0]
    return '%s. %s%s. Natural realistic motion that exactly follows the scene layout, same people throughout, stable faces and clothing, no flicker.' % (
        desc, ('People: ' + who + '. ') if who else '', STYLE_EN)

def graph(start_img, ctl_video, n, pos, neg, seed):
    A = {}
    def node(i, cls, **inp): A[str(i)] = {'class_type': cls, 'inputs': inp}; return [str(i), 0]
    hi = node(1, 'UNETLoader', unet_name=MODELS['high'], weight_dtype='default')
    lo = node(2, 'UNETLoader', unet_name=MODELS['low'], weight_dtype='default')
    if not args.no_lora:
        hi = node(3, 'LoraLoaderModelOnly', model=hi, lora_name=MODELS['lora_high'], strength_model=1.0)
        lo = node(4, 'LoraLoaderModelOnly', model=lo, lora_name=MODELS['lora_low'], strength_model=1.0)
    hi = node(5, 'ModelSamplingSD3', model=hi, shift=8.0); lo = node(6, 'ModelSamplingSD3', model=lo, shift=8.0)
    clip = node(7, 'CLIPLoader', clip_name=MODELS['t5'], type=CLIP_TYPE, device='default')
    vae = node(8, 'VAELoader', vae_name=MODELS['vae'])
    p = node(9, 'CLIPTextEncode', clip=clip, text=pos); q = node(10, 'CLIPTextEncode', clip=clip, text=neg)
    img = node(11, 'LoadImage', image=start_img)
    if VIDEO_LOADER == 'LoadVideo':
        v = node(12, 'LoadVideo', file=ctl_video); frames = node(13, 'GetVideoComponents', video=v)
    else:
        frames = node(12, 'VHS_LoadVideo', video=ctl_video, force_rate=0, custom_width=0, custom_height=0, frame_load_cap=0, skip_first_frames=0, select_every_nth=1)
    fc = node(14, 'Wan22FunControlToVideo', positive=p, negative=q, vae=vae, width=W, height=H, length=n, batch_size=1, **{START_KEY: img, 'control_video': frames})
    cfg = 1.0 if not args.no_lora else 3.5; mid = args.steps // 2
    s1 = node(15, 'KSamplerAdvanced', model=hi, add_noise='enable', noise_seed=seed, steps=args.steps, cfg=cfg, sampler_name='euler', scheduler='simple',
              positive=['14', 0], negative=['14', 1], latent_image=['14', 2], start_at_step=0, end_at_step=mid, return_with_leftover_noise='enable')
    s2 = node(16, 'KSamplerAdvanced', model=lo, add_noise='disable', noise_seed=seed, steps=args.steps, cfg=cfg, sampler_name='euler', scheduler='simple',
              positive=['14', 0], negative=['14', 1], latent_image=s1, start_at_step=mid, end_at_step=10000, return_with_leftover_noise='disable')
    dec = node(17, 'VAEDecode', samples=s2, vae=vae)
    if RIFE:
        rin = {**INFO[RIFE]['input'].get('required', {})}
        ck = choices(RIFE, 'ckpt_name'); ck = next((c for c in ck if '49' in c), next((c for c in ck if '47' in c), ck[0] if ck else 'rife47.pth'))
        r = dict(ckpt_name=ck, frames=dec, clear_cache_after_n_frames=10, multiplier=3, fast_mode=True, ensemble=True, scale_factor=1.0)
        dec = node(18, RIFE, **{k: v for k, v in r.items() if k in rin or k == 'frames'})
    node(19, 'SaveImage', images=dec, filename_prefix='fun_tmp')
    return A

def run(A, tag):
    if args.dry: print(json.dumps(A, ensure_ascii=False)[:1500]); return []
    r = comfy_run._post('/prompt', {'prompt': A}); pid = r.get('prompt_id')
    if not pid: sys.exit('排队失败 %s' % tag)
    if r.get('node_errors'): sys.exit('节点错误 %s' % json.dumps(r['node_errors'], ensure_ascii=False)[:1500])
    for _ in range(1200):
        time.sleep(3); h = comfy_run._get('/history/' + pid)
        if pid in h and h[pid].get('status', {}).get('completed'): break
        if pid in h and h[pid].get('status', {}).get('status_str') == 'error': sys.exit('生成失败 %s %s' % (tag, json.dumps(h[pid]['status'], ensure_ascii=False)[:1500]))
    else: sys.exit('超时 %s' % tag)
    ims = [im for o in h[pid]['outputs'].values() for im in o.get('images', [])]
    out = []
    for j, im in enumerate(ims):
        q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im.get('subfolder', ''), 'type': im.get('type', 'output')})
        p = os.path.join(TMP, '%s_%04d.png' % (tag, j)); open(p, 'wb').write(urllib.request.urlopen(comfy_run.URL + '/view?' + q).read()); out.append(p)
    return out

pack = args.pack; only = [x for x in args.only.split(',') if x]
man = json.load(open(os.path.join(pack, 'manifest.json'), encoding='utf-8'))
for tid in man['tasks']:
    if only and not any(tid.startswith(x) for x in only): continue
    td = os.path.join(pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
    kf = os.path.join(KF, tid + '.png')
    if not os.path.exists(kf): log('跳过（没有写实首帧）', tid); continue
    ctl_src = os.path.join(td, args.control + '.mp4')
    if not os.path.exists(ctl_src): log('跳过（没有控制视频）', tid); continue
    n24 = task['n']; n16 = max(5, round(n24 / 24.0 * FPS) + 1); t0 = time.time()
    # 控制视频：换算到生成帧率和分辨率，不足的尾帧用最后一帧补齐。素材包里的 832×480 是 16:9 画面横向压缩的（11-27 与 1920×1080 首帧比对：拉伸差 8.7、裁切差 12.7），放大回 16:9 正好与首帧对齐
    full = os.path.join(TMP, '%s_ctl.mp4' % tid)
    ff('-i', ctl_src, '-vf', 'fps=%d,scale=%d:%d:flags=lanczos,tpad=stop_mode=clone:stop_duration=2' % (FPS, W, H), '-frames:v', str(n16), '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', full)
    start = 'funstart_%s.png' % tid; ff('-i', kf, '-vf', 'scale=%d:%d:flags=lanczos' % (W, H), os.path.join(INP, start))
    pos, neg = prompt_of(task), NEG_EN + ', morphing, flickering, sudden camera change, extra people, changing clothes'
    frames, s, k = [], 0, 0
    while s < n16 - 1 or not frames:
        n = min(MAXF, n16 - s); n = max(5, ((n - 1 + 3) // 4) * 4 + 1)          # Wan 帧数 = 4k+1
        seg = 'functl_%s_%02d.mp4' % (tid, k)
        ff('-ss', '%.4f' % (s / FPS), '-i', full, '-vf', 'tpad=stop_mode=clone:stop_duration=6', '-frames:v', str(n), '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', os.path.join(INP, seg))
        imgs = run(graph(start, seg, n, pos, neg, args.seed), '%s_%02d' % (tid, k))
        if args.dry: break
        if k: imgs = imgs[1:]                                                 # 续接段的第一帧就是上一段的最后一帧（插帧后也只重合这一帧）
        frames += imgs; k += 1
        last = imgs[-1]; start = 'funstart_%s_%02d.png' % (tid, k); shutil.copy(last, os.path.join(INP, start))
        s += n - 1
        log(tid, '段 %d 完成' % k, '%d 帧' % len(frames))
    if args.dry: continue
    od = os.path.join(OUT, tid); shutil.rmtree(od, ignore_errors=True); os.makedirs(od)
    rate = FPS * (3 if RIFE else 1)
    lst = os.path.join(TMP, tid + '_list.txt'); open(lst, 'w').write(''.join("file '%s'\nduration %.6f\n" % (f, 1.0 / rate) for f in frames))
    mp4 = os.path.join(OUT, tid + '.mp4')
    ff('-f', 'concat', '-safe', '0', '-i', lst, '-vf', 'fps=24', '-frames:v', str(n24), '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', mp4)
    ff('-i', mp4, '-start_number', str(task['frames'][0]), os.path.join(od, 'frame_%04d.png'))
    for f in glob.glob(os.path.join(TMP, '%s_*' % tid)): os.remove(f)
    log('完成', tid, '%d 帧' % n24, '%.0f 秒' % (time.time() - t0))
print('FUN DONE', flush=True)
