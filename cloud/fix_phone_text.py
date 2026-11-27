# -*- coding: utf-8 -*-
"""手机屏幕文字修正（本地）：视频模型画不出汉字（s07_01_0023 来电界面「爸爸」被画成乱码），在原位置盖一块屏幕底色、重新写字；
画面淡出时按和第一帧的差异自动降低叠加强度，跟着一起淡出。
用法：python cloud/fix_phone_text.py <real 帧目录> "<行1>|<行2>" x0,y0,x1,y1 <字号1>,<字号2>   （坐标按帧像素，框住原来的乱码文字）
处理后重新编码 <目录>.mp4；原帧备份到 <目录>/_orig_text/"""
import os, sys, glob, shutil, subprocess, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import config
d, text, box, sizes = sys.argv[1], sys.argv[2].split('|'), [int(v) for v in sys.argv[3].split(',')], [int(v) for v in sys.argv[4].split(',')]
x0, y0, x1, y1 = box
FONT = 'C:/Windows/Fonts/msyh.ttc'
bk = os.path.join(d, '_orig_text'); os.makedirs(bk, exist_ok=True)
fs = sorted(glob.glob(os.path.join(d, 'frame_*.png')))
for p in fs:
    if not os.path.exists(os.path.join(bk, os.path.basename(p))): shutil.copy(p, bk)
src = [cv2.imread(os.path.join(bk, os.path.basename(p))) for p in fs]
ref = src[0][y0:y1, x0:x1].astype(np.float32)
# 屏幕底色：框外上下各取一条
bg = np.median(np.concatenate([src[0][y0 - 6:y0 - 2, x0:x1].reshape(-1, 3), src[0][y1 + 2:y1 + 6, x0:x1].reshape(-1, 3)]), axis=0)
patch = Image.new('RGB', (x1 - x0, y1 - y0), tuple(int(v) for v in bg[::-1])); dr = ImageDraw.Draw(patch)
col = tuple(int(v) for v in np.percentile(ref.reshape(-1, 3), 99, axis=0)[::-1])   # 文字颜色 = 原乱码里最亮的颜色
y = 0; H = y1 - y0
heights = [ImageFont.truetype(FONT, s).getbbox(t)[3] for t, s in zip(text, sizes)]; gap = max(2, (H - sum(heights)) // (len(text) + 1)); y = gap
for t, s in zip(text, sizes):
    f = ImageFont.truetype(FONT, s); bb = f.getbbox(t); dr.text(((x1 - x0 - (bb[2] - bb[0])) // 2 - bb[0], y - bb[1]), t, font=f, fill=col); y += (bb[3] - bb[1]) + gap + s // 4
patch = cv2.GaussianBlur(cv2.cvtColor(np.asarray(patch), cv2.COLOR_RGB2BGR).astype(np.float32), (0, 0), 0.6)
mask = np.ones((H, x1 - x0), np.float32); mask = cv2.GaussianBlur(cv2.copyMakeBorder(mask[4:-4, 4:-4], 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=0), (0, 0), 2)[..., None]
def hp(a): return a - cv2.GaussianBlur(a, (0, 0), 3)
R = hp(ref); RR = float((R * R).sum()) + 1e-6
S = 24   # 每帧在 ±24 像素内找乱码文字的实际位置（淡出时手机画面会轻微移动、缩放）
for p, im in zip(fs, src):
    big = hp(im.astype(np.float32))
    ya, yb, xa, xb = max(0, y0 - S), min(im.shape[0], y1 + S), max(0, x0 - S), min(im.shape[1], x1 + S)
    r = cv2.matchTemplate(big[ya:yb, xa:xb], R, cv2.TM_CCORR); _, _, _, (mx, my) = cv2.minMaxLoc(r)
    X0, Y0 = xa + mx, ya + my
    reg = im[Y0:Y0 + H, X0:X0 + (x1 - x0)].astype(np.float32)
    aa = float(np.clip(2.8 * (hp(reg) * R).sum() / RR, 0, 1))   # 投影会被下一个画面的纹理稀释，乘 2.8 补回（11-26 实测）   # 这一帧里手机画面还占多少（淡出时按比例减掉乱码、加上正确文字）
    out = im.astype(np.float32)
    out[Y0:Y0 + H, X0:X0 + (x1 - x0)] = reg + (patch - ref) * aa * mask
    cv2.imwrite(p, out.clip(0, 255).astype(np.uint8)); print(os.path.basename(p), X0 - x0, Y0 - y0, round(aa, 2))
f0 = int(os.path.basename(fs[0])[6:10])
subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-framerate', '24', '-start_number', str(f0), '-i', os.path.join(d, 'frame_%04d.png'),
                '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', d + '.mp4'], check=True)
print('TEXT FIXED', len(fs))

