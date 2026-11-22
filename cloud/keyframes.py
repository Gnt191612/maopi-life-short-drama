# -*- coding: utf-8 -*-
"""每个镜头的写实关键帧（写实化实例上运行，用的是 11-19 已验证的做法）：
  镜头首帧白模 →「Krea2 二转三」写实化（保构图、姿势、服装，提示词带出场角色外貌）
            →「Qwen2.1 人物替换」逐个角色换成标准长相（图1 = assets/identity/<cid>.png，图2 = 上一步照片）
结果 /root/v11_out/kf/<任务id>.png，后面 video_run.py 用它当图生视频的首帧。约 1~2 分钟/镜头（4090D）。
用法：python3 keyframes.py <cloud_pack 目录> [任务id前缀 ...]"""
import os, sys, json, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
from looks import LOOK
INP = '/root/ComfyUI/input'
OUTK = '/root/v11_out/kf'; os.makedirs(OUTK, exist_ok=True)
WF_REAL = os.environ.get('V11_WF_REAL', 'Krea2-二转三-图生图-新版.json')
WF_SWAP = os.environ.get('V11_WF_SWAP', '【推荐】Qwen2.1-人物替换.json')
SWAP = ('使用图1中的人物替换图2中的{who}，置于同一画面位置。长相与图1完全相同，是同一个人（五官、脸型、眉眼、发型、肤色一致）。'
        '保持图2的姿势、表情、构图、景别、服装和光影不变，其他人物和背景不变。')

def first_frame(td, tid):
    src = os.path.join(td, 'first.png')
    dst = os.path.join(INP, 'kfsrc_%s.png' % tid)
    if os.path.exists(src): shutil.copy(src, dst)
    else: subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(td, 'beauty.mp4'), '-frames:v', '1', dst], check=True)
    return os.path.basename(dst)

def main():
    pack = sys.argv[1]; pre = sys.argv[2:]
    man = json.load(open(os.path.join(pack, 'manifest.json'), encoding='utf-8'))
    for f in os.listdir(os.path.join(pack, 'refs')):   # 标准长相照片放进 ComfyUI 输入目录
        shutil.copy(os.path.join(pack, 'refs', f), os.path.join(INP, f))
    for tid in man['tasks']:
        if pre and not any(tid.startswith(p) for p in pre): continue
        out = os.path.join(OUTK, tid + '.png')
        if os.path.exists(out): continue
        td = os.path.join(pack, tid); task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
        chars = task.get('characters', [])
        look = '；'.join(LOOK[c] for c in chars if c in LOOK)
        base = comfy_run.run(WF_REAL, 'kfbase_' + tid, {'10.image': first_frame(td, tid)}, prefix=(look + '。') if look else '')
        if not base: print('KF FAIL base', tid, flush=True); continue
        cur = base
        for c in chars:   # 逐个角色换脸（多人镜头：用外貌描述指明换的是哪一个）
            ref = 'canon_%s.jpg' % c
            if not os.path.exists(os.path.join(INP, ref)): continue
            shutil.copy(cur, os.path.join(INP, 'kfcur_%s.png' % tid))
            who = '那个人' if len(chars) == 1 else '这个人：' + LOOK[c].split('，')[0]
            nxt = comfy_run.run(WF_SWAP, 'kfswap_%s_%s' % (tid, c), {'3.image': ref, '10.image': 'kfcur_%s.png' % tid, '39.text': SWAP.format(who=who)})
            if nxt: cur = nxt
        shutil.copy(cur, out); print('KF OK', tid, chars, flush=True)
    print('KEYFRAMES DONE', flush=True)

if __name__ == '__main__':
    main()
