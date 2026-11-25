# -*- coding: utf-8 -*-
"""每个镜头的写实关键帧（写实化实例上运行，用的是 11-19 已验证的做法）：
  镜头首帧白模 →「Krea2 二转三」写实化（保构图、姿势、服装，提示词带出场角色外貌）
            →「Qwen2.1 人物替换」逐个角色换成标准长相（图1 = assets/identity/<cid>.png，图2 = 上一步照片）
结果 /root/v11_out/kf/<任务id>.png，后面 video_run.py 用它当图生视频的首帧。约 1~2 分钟/镜头（4090D）。
用法：python3 keyframes.py <cloud_pack 目录> [任务id前缀 ...]"""
import os, sys, json, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run, shard
from looks import LOOK
INP = '/root/ComfyUI/input'
OUTK = '/root/v11_out/kf'; os.makedirs(OUTK, exist_ok=True)
WF_REAL = os.environ.get('V11_WF_REAL', 'Krea2-二转三-图生图-新版.json')
WF_SWAP = os.environ.get('V11_WF_SWAP', '【推荐】Qwen2.1-人物替换.json')
# 只换脸（2026-11-22 试片：图1 用整张标准照时，整人替换模型把长发、毛衣一起搬过来，和定稿造型不符）
SWAP = ('把图2中{who}的脸换成图1这张脸：五官、脸型、眉眼、肤色与图1一致，是同一个人。'
        '只换脸，图2的发型、发色、服装、饰品、姿势、表情、构图、景别和光影全部保持不变，其他人物和背景不变。')

NOFACE = ('extreme close-up of a smartphone', 'close-up of a smartphone', 'phone screen', "hands holding the phone", 'hands set', 'hands holding',
          'bare feet', 'feet landing', 'from behind', 'over the shoulder', 'notice taped', 'close-up of a white a4', 'close-up of the wooden')

def plan(task):
    """按镜头内容定重绘力度和要不要换脸（2026-11-22 试片：外景树仍是卡通；手机特写被贴了一张脸）"""
    en = task.get('prompt', '').lower(); chars = task.get('characters', [])
    start = int(os.environ.get('V11_KF_START', 3))
    if not chars: start = int(os.environ.get('V11_KF_START_EMPTY', 1))      # 无人外景/空镜：几乎从头重画，去掉卡通树和方块楼
    swap = [] if any(k in en for k in NOFACE) else chars                     # 看不到脸的镜头不换脸
    return start, swap

def first_frame(td, tid, src_name='first.png'):
    src = os.path.join(td, src_name)
    dst = os.path.join(INP, 'kfsrc_%s.png' % tid)
    if os.path.exists(src): shutil.copy(src, dst)
    else: subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(td, 'beauty.mp4'), '-frames:v', '1', dst], check=True)
    flatten_dark(dst)
    return os.path.basename(dst)

def flatten_dark(path, radius=6, lo=70, hi=100):
    """深色区域（黑裤子、深色卫衣）的褶皱明暗抹平：白模布料的褶皱暗纹会被二转三画成斑马纹/迷彩（2026-11-24 试跑：陈瑶黑裤子变斑马裤）。
    只动亮度低于 hi 的像素，越暗越平；褶皱和布纹交给写实化重画。"""
    try:
        from PIL import Image, ImageFilter
        import numpy as np
        im = Image.open(path).convert('RGB'); a = np.asarray(im).astype(np.float32)
        b = np.asarray(im.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32)
        m = np.clip((hi - a.mean(2)) / (hi - lo), 0, 1)[..., None]
        Image.fromarray((a * (1 - m) + b * m).astype(np.uint8)).save(path)
    except Exception as e:
        print('flatten_dark skip', e, flush=True)

def main():
    pack = sys.argv[1]; pre = sys.argv[2:]
    man = json.load(open(os.path.join(pack, 'manifest.json'), encoding='utf-8'))
    for f in os.listdir(os.path.join(pack, 'refs')):   # 标准长相照片放进 ComfyUI 输入目录
        shutil.copy(os.path.join(pack, 'refs', f), os.path.join(INP, f))
    my = shard.mine(pack)   # 多实例并行：只做分给本实例的镜头
    for tid in man['tasks']:
        if pre and not any(tid.startswith(p) for p in pre): continue
        if my is not None and tid not in my: continue
        td = os.path.join(pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
        jobs = [(tid, 'first.png', os.path.join(OUTK, tid + '.png'))]
        ap_ = os.path.join(td, 'anchors.json')   # 锚点模式：每个锚点帧（白模 anchor_####.png）也出一张写实图 kf/<id>@####.png（2026-11-25）
        if os.path.exists(ap_):
            jobs += [('%s@%04d' % (tid, a), 'anchor_%04d.png' % a, os.path.join(OUTK, '%s@%04d.png' % (tid, a)))
                     for a in json.load(open(ap_))[1:] if os.path.exists(os.path.join(td, 'anchor_%04d.png' % a))]
        for jid, src_name, out in jobs:
            make_kf(td, jid, task, src_name, out)
    print('KEYFRAMES DONE', flush=True)

def make_kf(td, tid, task, src_name, out):
    if True:
        if os.path.exists(out): return
        chars = task.get('characters', [])
        look = '；'.join(LOOK[c] for c in chars if c in LOOK)
        # 图生图：8 步采样从第 3 步开始（保留白模构图，只重绘质感）；不加人物描述——从头重画时会拉远镜头、多画出一个人（2026-11-22 试片）
        start, swap = plan(task)
        base = comfy_run.run(WF_REAL, 'kfbase_' + tid, {'10.image': first_frame(td, tid, src_name), '21.start_at_step': start})
        if not base: print('KF FAIL base', tid, flush=True); return
        cur = base
        for c in swap:   # 逐个角色换脸（多人镜头：用外貌描述指明换的是哪一个）
            ref = 'canonface_%s.jpg' % c if os.path.exists(os.path.join(INP, 'canonface_%s.jpg' % c)) else 'canon_%s.jpg' % c
            if not os.path.exists(os.path.join(INP, ref)): continue
            shutil.copy(cur, os.path.join(INP, 'kfcur_%s.png' % tid))
            who = '那个人' if len(chars) == 1 else '这个人：' + LOOK[c].split('，')[0]
            nxt = comfy_run.run(WF_SWAP, 'kfswap_%s_%s' % (tid, c), {'3.image': ref, '10.image': 'kfcur_%s.png' % tid, '39.text': SWAP.format(who=who)})
            if nxt: cur = nxt
        shutil.copy(cur, out); print('KF OK', tid, chars, flush=True)

if __name__ == '__main__':
    main()
