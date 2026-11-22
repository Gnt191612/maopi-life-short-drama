# -*- coding: utf-8 -*-
"""片头合成（本地）：背景 = 大工官网「校园风光」雪中雕像照（已去掉打伞的人）；中间露出雕像；
Claude 娘（绿幕讲解视频抠像）站右侧；左上角大工校徽（官网 SVG 染成大工蓝）；她伸手示意左侧时浮现 GitHub 卡片；
配音 = Claude 娘 6 号音色（3.6 秒版）。
用法：python blender/intro_compose.py [--preview]   → build/intro/intro.mp4（--preview 只出一张版式图）"""
import os, sys, subprocess
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
A = os.path.join(config.ROOT, 'assets', 'intro')
OUT = os.path.join(config.ROOT, 'build', 'intro'); os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1920, 1080, 24
BG = os.path.join(A, 'dlut_dl', 'snow_clean.png')
LOGO = os.path.join(A, 'dlut_dl', 'logo_blue_big.png')
GIRL = os.path.join(A, 'green_v', 'intro_talk2.mp4')
VOICE = os.path.join(A, 'voice', 'claude_line_final.wav')
REPO = 'github.com/Gnt191612/maopi-life-short-drama'

def background():
    im = cv2.imread(BG); h, w = im.shape[:2]
    s = W / w; im = cv2.resize(im, (W, int(h * s + 0.5)), interpolation=cv2.INTER_CUBIC)
    y0 = int((im.shape[0] - H) * 0.30)                       # 少裁上面（雕像头顶留空间）
    im = im[y0:y0 + H]
    return cv2.GaussianBlur(im, (0, 0), 1.2)                  # 放大后的锯齿柔一下，也像浅景深

def key_green(fr):
    """绿幕抠像：按「绿色比红蓝多多少」算透明度，边缘去绿溢色"""
    f = fr.astype(np.float32); b, g, r = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)
    a = 1 - np.clip((d - 25) / 45, 0, 1)
    a = cv2.GaussianBlur(a, (0, 0), 0.8)
    spill = np.clip(g - np.maximum(r, b), 0, None) * (1 - a) * 0 + np.clip(g - (r + b) / 2, 0, None)
    f[..., 1] = np.where(a < 0.999, g - spill * 0.8, g)
    return np.clip(f, 0, 255).astype(np.uint8), a

def logo_layer():
    lg = cv2.imread(LOGO, cv2.IMREAD_UNCHANGED); lw = int(W * 0.24); lh = int(lg.shape[0] * lw / lg.shape[1])
    lg = cv2.resize(lg, (lw, lh), interpolation=cv2.INTER_AREA)
    return lg, int(W * 0.035), int(H * 0.05)

def card(t):
    """场记板（用户 11-22：白框不美观，换成场记板）：t∈[0,0.45] 渐显、拍杆张开；0.45→0.65 拍杆合上（打板）"""
    from PIL import Image, ImageDraw, ImageFont
    fz = os.path.join(config.FONTS_DIR, next(f for f in os.listdir(config.FONTS_DIR) if f.lower().endswith(('.otf', '.ttf'))))
    F = lambda n: ImageFont.truetype(fz, n)
    bw, bh, sh_ = 640, 360, 74
    sh_two = 2                                    # 板身、拍杆高度
    cw, chh = bw + 60, bh + 2 * sh_ + 140
    img = Image.new('RGBA', (cw, chh), (0, 0, 0, 0))
    def stripes(w, h):
        st = Image.new('RGBA', (w, h), (20, 20, 20, 255)); d = ImageDraw.Draw(st); k = 70
        for x in range(-h, w + h, k * 2): d.polygon([(x, h), (x + h * 0.6, 0), (x + h * 0.6 + k, 0), (x + k, h)], fill=(245, 245, 240, 255))
        d.rectangle([0, 0, w - 1, h - 1], outline=(20, 20, 20, 255), width=4); return st
    bx, by = 30, 2 * sh_ + 70
    # 板身
    body = Image.new('RGBA', (bw, bh), (28, 30, 32, 255)); d = ImageDraw.Draw(body)
    d.rectangle([0, 0, bw - 1, bh - 1], outline=(235, 235, 230, 255), width=3)
    for y in (118, 238): d.line([(14, y), (bw - 14, y)], fill=(200, 200, 195, 255), width=2)
    d.line([(bw // 2, 238), (bw // 2, bh - 14)], fill=(200, 200, 195, 255), width=2)
    chalk = (242, 240, 232, 255)
    d.text((bw // 2, 62), '代码已开源', font=F(64), fill=chalk, anchor='mm')
    d.text((24, 132), 'GitHub', font=F(26), fill=(170, 170, 165, 255))
    d.text((bw // 2 + 30, 200), 'github.com/Gnt191612', font=F(40), fill=chalk, anchor='mm')
    d.text((24, 252), '片名', font=F(24), fill=(170, 170, 165, 255)); d.text((bw // 4, 306), '毛坯人生，精装朋友圈', font=F(28), fill=chalk, anchor='mm')
    d.text((bw // 2 + 18, 252), '仓库', font=F(24), fill=(170, 170, 165, 255)); d.text((bw * 3 // 4, 306), 'maopi-life-short-drama', font=F(24), fill=chalk, anchor='mm')
    img.alpha_composite(body, (bx, by))
    img.alpha_composite(stripes(bw, sh_ - 14), (bx, by - sh_ + 14))                        # 下拍杆（固定）
    ang = 24 * (1 - float(np.clip((t - 0.45) / 0.2, 0, 1)) ** 2)                            # 上拍杆：张开 24° → 合上
    top = stripes(bw, sh_ - 14).rotate(ang, resample=Image.BICUBIC, expand=True, center=(0, sh_ - 14), fillcolor=(0, 0, 0, 0))
    img.alpha_composite(top, (bx, max(0, by - 2 * (sh_ - 14) - 4 - (top.height - (sh_ - 14)))))
    a = np.asarray(img).astype(np.float32); a[..., 3] *= float(np.clip(t / 0.3, 0, 1))
    return cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGBA2BGRA)

def over(dst, src_bgr, alpha, x, y):
    h, w = src_bgr.shape[:2]; x0, y0 = max(0, x), max(0, y); x1, y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0: return
    s = src_bgr[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); a = alpha[y0 - y:y1 - y, x0 - x:x1 - x, None]
    dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - a) + s * a

def frame(bg, girl_fr, t_card):
    out = bg.astype(np.float32).copy()
    lg, lx, ly = logo_layer(); over(out, lg[..., :3], lg[..., 3] / 255.0, lx, ly)
    rgb, a = key_green(girl_fr)
    ys, xs = np.nonzero(a > 0.5)
    if len(ys):
        y0, y1 = ys.min(), ys.max(); x0, x1 = xs.min(), xs.max()
        # 第一帧定比例：人物高 = 画面 82%，站在右侧（中心 x≈73%），脚落在画面底部上方 4%
        s = H * 0.82 / (y1 - y0) if not hasattr(frame, 's') else frame.s
        frame.s = s; frame.cx = getattr(frame, 'cx', (x0 + x1) / 2); frame.fy = getattr(frame, 'fy', y1)
        big = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC); ba = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
        gx = int(W * 0.73 - frame.cx * s); gy = int(H * 0.96 - frame.fy * s)
        sh = np.zeros((H, W), np.float32); cv2.ellipse(sh, (int(W * 0.73), int(H * 0.965)), (int(150), 18), 0, 0, 360, 1, -1)
        out *= 1 - 0.25 * cv2.GaussianBlur(sh, (0, 0), 14)[..., None]
        over(out, big, ba, gx, gy)
    if t_card > 0:
        c = card(t_card); over(out, c[..., :3], c[..., 3] / 255.0, int(W * 0.03), int(H * 0.40))
    return np.clip(out, 0, 255).astype(np.uint8)

def main():
    bg = background(); cap = cv2.VideoCapture(GIRL); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if '--preview' in sys.argv:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * 0.85)); ok, fr = cap.read()
        cv2.imwrite(os.path.join(OUT, 'intro_preview.png'), frame(bg, fr, 1.0)); print('PREVIEW OK'); return
    tmp = os.path.join(OUT, 'frames'); os.makedirs(tmp, exist_ok=True)
    t_in = 0.62   # 视频进度到 62%（她转身伸手示意左侧）时卡片开始浮现
    for i in range(n):
        ok, fr = cap.read()
        if not ok: i -= 1; break
        p = i / max(1, n - 1); tc = float(np.clip((p - t_in) / 0.30, 0, 1))
        cv2.imwrite(os.path.join(tmp, 'f_%04d.png' % i), frame(bg, fr, tc))
    last = frame(bg, fr_last, 1.0) if 'fr_last' in dir() else None
    import shutil
    for j in range(int(FPS * 1.5)):   # 末尾定格 1.5 秒，场记板上的字看得清
        shutil.copy(os.path.join(tmp, 'f_%04d.png' % (i)), os.path.join(tmp, 'f_%04d.png' % (i + 1 + j)))
    mp4 = os.path.join(OUT, 'intro.mp4')
    subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f_%04d.png'), '-itsoffset', '0.4', '-i', VOICE,
                    '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-af', 'apad', '-shortest', mp4], check=True)
    print('INTRO OK', mp4, n, 'frames')

if __name__ == '__main__':
    main()
