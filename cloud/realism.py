# -*- coding: utf-8 -*-
"""云端批量写实化：逐个镜头任务，把白模的深度 + 骨架作为结构控制、角色定妆照作为长相参考，用 Wan2.1-VACE 生成照片级画面。
  - 结构控制：depth.mp4 与 pose.mp4 叠加（骨架画在深度上），保证动作、站位、构图和白模一致
  - 长相参考：task.json 里列出的出场角色定妆照（最多 3 张），保证同一个人始终同一张脸
  - 长镜头按 81 帧（4n+1）一段生成，同一镜头内固定随机种子；可断点续跑（已生成的跳过）
用法（在解压后的 cloud_pack 同级目录）：python realism.py [--model 14B|1.3B] [--only 任务id前缀] [--steps 30] [--test]
  --test：只跑第一个镜头的前 33 帧，先看效果再决定是否整片跑（省钱）
输出 out/<任务id>/frame_####.png 与 out/<任务id>.mp4；进度写 out/progress.log
"""
import os, sys, json, time, argparse
import numpy as np
import torch
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('--model', default='14B'); ap.add_argument('--only', default=''); ap.add_argument('--steps', type=int, default=30)
ap.add_argument('--test', action='store_true'); ap.add_argument('--pack', default='cloud_pack'); ap.add_argument('--out', default='out')
ap.add_argument('--control', default='depth+pose', help='depth / pose / depth+pose')
args = ap.parse_args()
NEG = ('cartoon, anime, 3d render, cgi, video game, doll, plastic skin, blurry, deformed face, extra fingers, text, watermark, '
       'flickering, low quality, oversaturated')
CHUNK = 81

def read_video(p):
    import imageio.v3 as iio
    return [Image.fromarray(f) for f in iio.imiter(p)] if os.path.exists(p) else None

def write_video(frames, p, fps=24):
    import imageio.v3 as iio
    iio.imwrite(p, np.stack([np.asarray(f) for f in frames]), fps=fps, codec='libx264', quality=9)

def log(*a):
    s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a); print(s, flush=True)
    open(os.path.join(args.out, 'progress.log'), 'a', encoding='utf-8').write(s + '\n')

def control_frames(td):
    dep, pose = read_video(os.path.join(td, 'depth.mp4')), read_video(os.path.join(td, 'pose.mp4'))
    if args.control == 'pose' and pose: return pose
    if args.control == 'depth' or not pose: return dep
    out = []
    for d, p in zip(dep, pose):   # 骨架叠在深度图上：深度给空间结构，骨架给精确姿态
        dn, pn = np.asarray(d.convert('RGB')).astype(np.float32), np.asarray(p.convert('RGB').resize(d.size)).astype(np.float32)
        m = pn.max(axis=2, keepdims=True) > 30
        out.append(Image.fromarray(np.where(m, pn, dn * 0.85).astype(np.uint8)))
    return out

def main():
    os.makedirs(args.out, exist_ok=True)
    from diffusers import AutoencoderKLWan, WanVACEPipeline
    from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler
    mdir = os.path.join('models', 'Wan2.1-VACE-%s-diffusers' % args.model)
    vae = AutoencoderKLWan.from_pretrained(mdir, subfolder='vae', torch_dtype=torch.float32)
    pipe = WanVACEPipeline.from_pretrained(mdir, vae=vae, torch_dtype=torch.bfloat16)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)   # 480p 推荐 3.0
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    if vram < 60 and args.model == '14B': pipe.enable_model_cpu_offload(); log('显存 %.0f GB：14B 模型分块放显存（较慢）' % vram)
    else: pipe.to('cuda')
    man = json.load(open(os.path.join(args.pack, 'manifest.json'), encoding='utf-8'))
    W, H = man['size']
    for tid in man['tasks']:
        if args.only and not tid.startswith(args.only): continue
        td = os.path.join(args.pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
        mp4 = os.path.join(args.out, tid + '.mp4')
        if os.path.exists(mp4): continue
        ctrl = control_frames(td)
        if not ctrl: log('缺控制视频，跳过', tid); continue
        if args.test: ctrl = ctrl[:33]
        refs = [Image.open(os.path.join(args.pack, 'refs', r)).convert('RGB') for r in task['refs']][:3] or None
        frames, t0 = [], time.time()
        for s in range(0, len(ctrl), CHUNK):
            part = ctrl[s:s + CHUNK]; n = len(part)
            n4 = max(5, ((n - 1 + 3) // 4) * 4 + 1)                              # Wan 要求帧数 = 4k+1：不够就用最后一帧补齐，生成后再裁掉
            part = part + [part[-1]] * (n4 - n)
            masks = [Image.new('L', (W, H), 255)] * len(part)                  # 全部重新生成（结构由控制视频约束）
            g = torch.Generator('cpu').manual_seed(1234 + sum(map(ord, task['segment'])))
            res = pipe(video=[f.resize((W, H)) for f in part], mask=masks, reference_images=refs, prompt=task['prompt'], negative_prompt=NEG,
                       height=H, width=W, num_frames=len(part), num_inference_steps=args.steps, guidance_scale=5.0, generator=g).frames[0]
            res = [Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)) if isinstance(f, np.ndarray) else f for f in res]
            frames += res[:n]
        os.makedirs(os.path.join(args.out, tid), exist_ok=True)
        for i, f in enumerate(frames): f.save(os.path.join(args.out, tid, 'frame_%04d.png' % (task['frames'][0] + i)))
        write_video(frames, mp4)
        log('完成', tid, '%d 帧' % len(frames), '%.0f 秒' % (time.time() - t0))
        if args.test: log('试跑结束：请下载 out/ 查看效果'); break

if __name__ == '__main__':
    main()
