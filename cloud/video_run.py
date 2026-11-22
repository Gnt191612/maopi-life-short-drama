# -*- coding: utf-8 -*-
"""镜头写实化视频（写实化实例上运行）：首帧 = keyframes.py 的写实关键帧，按 video_map.json 指定的 ComfyUI 视频工作流图生视频。
  - 映射表：工作流里「首帧图 / 控制视频 / 正负提示词 / 帧数 / 宽高 / 种子」分别是哪个节点的哪个输入（开机后跑 probe_comfy.py 看，几分钟填好）
  - 长镜头按 max_frames 分段，后一段用前一段的最后一帧接着生成（同一镜头固定种子）
  - 模型原生帧率（如 Wan 16fps）生成，最后统一换算成 24fps、帧号与白模一致：
      /root/v11_out/real/<任务id>/frame_####.png（可直接给本地 run_all.py --previs-only --real= 用）和 <任务id>.mp4
用法：python3 video_run.py <cloud_pack 目录> [--map video_map.json] [--only 前缀,前缀] [--test] [--dry]
  --test 只跑第一个镜头的第一段（先看效果）；--dry 只转换工作流、打印要改的输入，不排队（验证映射表）"""
import os, sys, json, shutil, subprocess, argparse, glob, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from looks import LOOK_EN, STYLE_EN, NEG_EN
INP = '/root/ComfyUI/input'
OUT = '/root/v11_out/real'; KF = '/root/v11_out/kf'; TMP = '/root/v11_out/vtmp'
for d in (OUT, TMP): os.makedirs(d, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument('pack'); ap.add_argument('--map', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_map.json'))
ap.add_argument('--only', default=''); ap.add_argument('--test', action='store_true'); ap.add_argument('--dry', action='store_true')
args = ap.parse_args()
M = json.load(open(args.map, encoding='utf-8'))
FPS = M.get('fps', 16); MAXF = M.get('max_frames', 81); W, H = M.get('size', [832, 480])

def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y'] + list(a), check=True)
def log(*a):
    s = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a); print(s, flush=True)
    open('/root/v11_out/video_progress.log', 'a', encoding='utf-8').write(s + '\n')
def frames4(n): return max(5, min(MAXF, ((n - 1) // 4) * 4 + 1))   # Wan 系列帧数 = 4k+1

def prompt_of(task):
    who = '; '.join(LOOK_EN[c] for c in task.get('characters', []) if c in LOOK_EN)
    desc = task.get('prompt', '').split('. photorealistic')[0]
    return '%s. %s%s. Natural, subtle realistic motion, same people throughout, stable face identity.' % (desc, ('People: ' + who + '. ') if who else '', STYLE_EN)

def run_chunk(tid, k, img, ctl, nfr, task, seed):
    sets = {}
    def put(key, val):
        if M.get(key): sets[M[key]] = val
    put('image', img); put('prompt', prompt_of(task)); put('negative', NEG_EN)
    put('frames', nfr); put('width', W); put('height', H); put('seed', seed)
    if ctl: put('control_video', ctl)
    for kk, vv in M.get('extra', {}).items(): sets[kk] = vv          # 其他固定参数（步数、LoRA 强度等）
    if args.dry:
        api = comfy_run.convert(M['workflow'], tuple(M.get('enable', [])))
        miss = [s for s in sets if s.split('.')[0] not in api]
        print('DRY', tid, k, json.dumps(sets, ensure_ascii=False)[:600], '缺节点:', miss, flush=True); return None
    return comfy_run.run(M['workflow'], 'v_%s_%02d' % (tid, k), sets, timeout=M.get('timeout', 2400), enable=tuple(M.get('enable', [])))

def main():
    man = json.load(open(os.path.join(args.pack, 'manifest.json'), encoding='utf-8'))
    only = [x for x in args.only.split(',') if x]
    for tid in man['tasks']:
        if only and not any(tid.startswith(p) for p in only): continue
        if os.path.exists(os.path.join(OUT, tid + '.mp4')): continue
        td = os.path.join(args.pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
        kf = os.path.join(KF, tid + '.png')
        if not os.path.exists(kf): log('缺关键帧，跳过', tid); continue
        n24 = task['n']; dur = n24 / 24.0; need = max(5, round(dur * FPS) + 1)
        seed = 1234 + sum(map(ord, tid)); t0 = time.time()
        img_name = 'vimg_%s_00.png' % tid; shutil.copy(kf, os.path.join(INP, img_name))
        chunks, done, k = [], 0, 0
        while done < need:
            nfr = frames4(need - done + (1 if k else 0))                 # 续接段的第一帧与上一段最后一帧重合
            ctl = None
            if M.get('control_video'):                                    # 控制视频按这一段的时间裁出来
                src = os.path.join(td, M.get('control_kind', 'depth') + '.mp4')
                if os.path.exists(src):
                    ctl = 'vctl_%s_%02d.mp4' % (tid, k)
                    ff('-ss', '%.3f' % (max(0, done - (1 if k else 0)) / FPS), '-i', src, '-t', '%.3f' % (nfr / FPS),
                       '-vf', 'fps=%d,scale=%d:%d' % (FPS, W, H), '-an', os.path.join(INP, ctl))
            res = run_chunk(tid, k, img_name, ctl, nfr, task, seed)
            if args.dry: break
            if not res: log('生成失败', tid, '段', k); break
            chunks.append(res); done += nfr - (1 if k else 0); k += 1
            if args.test: break
            img_name = 'vimg_%s_%02d.png' % (tid, k)                       # 下一段首帧 = 这一段最后一帧
            ff('-sseof', '-0.1', '-i', res, '-frames:v', '1', '-update', '1', os.path.join(INP, img_name))
        if args.dry or not chunks: continue
        # 拼接（续接段去掉重合的第一帧）→ 24fps → 帧号与白模一致
        parts = []
        for i, c in enumerate(chunks):
            p = os.path.join(TMP, '%s_%02d.mp4' % (tid, i))
            ff('-i', c, '-vf', ('select=gte(n\\,1),' if i else '') + 'setpts=N/%d/TB,scale=%d:%d' % (FPS, W, H), '-an', '-c:v', 'libx264', '-crf', '14', p)
            parts.append(p)
        lst = os.path.join(TMP, tid + '.txt'); open(lst, 'w').write(''.join("file '%s'\n" % p for p in parts))
        mp4 = os.path.join(OUT, tid + '.mp4')
        ff('-f', 'concat', '-safe', '0', '-i', lst, '-vf', 'fps=24', '-frames:v', str(n24), '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', mp4)
        fd = os.path.join(OUT, tid); os.makedirs(fd, exist_ok=True)
        ff('-i', mp4, '-start_number', str(task['frames'][0]), os.path.join(fd, 'frame_%04d.png'))
        got = sorted(glob.glob(os.path.join(fd, 'frame_*.png')))
        for f in range(task['frames'][0] + len(got), task['frames'][1] + 1):  # 不够就用最后一帧补齐
            if got: shutil.copy(got[-1], os.path.join(fd, 'frame_%04d.png' % f))
        log('完成', tid, '%d 段' % len(chunks), '%d 帧' % n24, '%.0f 秒' % (time.time() - t0))
        if args.test: log('试跑结束：先下载 real/ 看效果'); break
    print('VIDEO DONE', flush=True)

if __name__ == '__main__':
    main()
