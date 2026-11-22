# -*- coding: utf-8 -*-
"""把 Claude 娘立绘放到纯绿幕上，作为图生视频的首帧（视频生成后抠像叠到任意背景）。
用法：python mascot/claude_girl/tools/green_first.py 输出.png [--size 720x1280] [--height 0.88] [--x 0.5]
竖屏 720x1280 让人物在画面里足够大（横屏 832x480 里只有约 400px 高，放大后会糊）"""
import os, argparse
import numpy as np, cv2
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--size', default='720x1280')
ap.add_argument('--height', type=float, default=0.88); ap.add_argument('--x', type=float, default=0.5)
a = ap.parse_args(); W, H = map(int, a.size.split('x'))
bg = np.zeros((H, W, 3), np.uint8); bg[:] = (64, 177, 0)
g = cv2.imread(os.path.join(BASE, 'image', 'claude_girl.png'), cv2.IMREAD_UNCHANGED)
gh = int(H * a.height); gw = int(g.shape[1] * gh / g.shape[0]); g = cv2.resize(g, (gw, gh), interpolation=cv2.INTER_AREA)
x = int(W * a.x - gw / 2); y = H - gh - int(H * 0.04); al = g[..., 3:4].astype(np.float32) / 255
out = bg.astype(np.float32); out[y:y + gh, x:x + gw] = out[y:y + gh, x:x + gw] * (1 - al) + g[..., :3] * al
cv2.imwrite(a.out, out.astype(np.uint8)); print('GREEN OK', a.out, gw, gh)
