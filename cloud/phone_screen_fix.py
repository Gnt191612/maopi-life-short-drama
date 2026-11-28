# -*- coding: utf-8 -*-
"""手机屏幕文字修正（11-27，通用版）：AI 写实化画不准汉字（「晓哥好自律」→「傍高好自信佳」），用白模渲染的正确屏幕文字逐帧贴回去。
每帧：①白模帧里找屏幕（大块平整的亮色区域）并提取文字像素（和屏幕底色反差大的）②ECC 对齐算白模→写实的透视变换（手机移动、倾斜都跟得上）
③写实屏幕上用底色盖掉乱码（肤色像素跳过，拇指保持原样）④按透视贴上正确文字，亮度跟写实画面的屏幕亮度走。
用法：python cloud/phone_screen_fix.py <写实视频.mp4|图片> <白模 beauty.mp4|first.png> <输出>"""
import os, sys, subprocess, tempfile, glob
import cv2, numpy as np

def screen_mask(g, bright=False):
    """白模帧里的屏幕：低梯度（平整）且不暗的最大连通区，取凸包"""
    gray = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8))
    flat = ((grad < 12) & (gray > (max(150, np.percentile(gray, 85)) if bright else 90))).astype(np.uint8)   # 白纸模式先按亮度筛（否则闭运算把墙和纸连成一块）
    flat = cv2.morphologyEx(flat, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))   # 把文字行的空洞补上
    n, lab, st, _ = cv2.connectedComponentsWithStats(flat)
    if n < 2: return None
    h, w = gray.shape; best = None
    for i in range(1, n):
        x, y, ww, hh, a = st[i]
        cx = x + ww / 2
        if a < 0.04 * h * w: continue
        score = a * (1.5 if abs(cx - w / 2) < w * 0.3 else 1)
        if bright: score = gray[lab == i].mean() ** 4 * np.sqrt(a)   # 白纸模式：挑最亮的平整区域（墙比纸大，但纸更亮）
        if best is None or score > best[0]: best = (score, i)
    if best is None: return None
    m = (lab == best[1]).astype(np.uint8)
    cnt = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    hull = np.zeros_like(m); cv2.fillConvexPoly(hull, cv2.convexHull(cnt), 1)
    return hull

def text_mask(g, scr):
    """屏幕里和底色反差大的像素 = 文字（头像占位灰块反差小，不算）"""
    lab = cv2.cvtColor(g, cv2.COLOR_BGR2LAB).astype(np.float32)
    inner = cv2.erode(scr, np.ones((9, 9), np.uint8))
    bg = np.median(lab[inner > 0], axis=0)
    diff = np.abs(lab[..., 0] - bg[0])
    t = ((diff > 55) & (inner > 0)).astype(np.uint8)
    return t, bg

def align(g, r, scr):
    """ECC：白模屏幕区域 → 写实帧的透视变换"""
    gg = cv2.GaussianBlur(cv2.cvtColor(g, cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32) / 255
    rr = cv2.GaussianBlur(cv2.cvtColor(r, cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32) / 255
    M = np.eye(3, dtype=np.float32)
    try:
        _, M = cv2.findTransformECC(gg, rr, M, cv2.MOTION_HOMOGRAPHY, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5),
                                    cv2.dilate(scr, np.ones((15, 15), np.uint8)) * 255, 5)
    except cv2.error:
        pass
    return M

def fix(r, g, prevM=None, bright=False):
    h, w = r.shape[:2]; g = cv2.resize(g, (w, h))
    scr = screen_mask(g, bright)
    if scr is None: return r, prevM
    t, bg = text_mask(g, scr)
    if t.sum() < 50: return r, prevM
    M = align(g, r, scr)
    if prevM is not None and np.abs(M - np.eye(3)).sum() < 1e-6: M = prevM   # 对齐失败沿用上一帧
    warp = lambda a, inter=cv2.INTER_NEAREST: cv2.warpPerspective(a, M, (w, h), flags=inter | cv2.WARP_INVERSE_MAP)
    scr_r = warp(scr); t_soft = warp(t.astype(np.float32), cv2.INTER_LINEAR)
    out = r.copy(); rlab = cv2.cvtColor(r, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV)
    skin = ((hsv[..., 0] < 25) | (hsv[..., 0] > 165)) & (hsv[..., 1] > 45)   # 拇指/手指
    rin = cv2.erode(scr_r, np.ones((9, 9), np.uint8)) > 0
    if rin.sum() < 100: return r, prevM
    # 写实屏幕底色（中位数，避开乱码：取亮度最接近众数的一半像素）
    L = rlab[..., 0][rin & ~skin]
    if L.size < 100: return r, prevM
    Lb = np.median(L); keep = rin & ~skin & (np.abs(rlab[..., 0] - Lb) < 12)
    rbg = np.median(r[keep], axis=0) if keep.sum() > 50 else np.median(r[rin], axis=0)
    # 文字所在的行：膨胀后的文字区，盖底色（跳过皮肤）
    lines = cv2.dilate((t_soft > 0.2).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_RECT, (25, 9))) > 0
    # 乱码和白模文字位置会差几个像素：文字区外扩一圈，圈里比屏幕底色暗（或亮，蓝底白字的来电界面）的笔画全擦掉
    ys, xs = np.nonzero(t_soft > 0.2); box = np.zeros((h, w), bool)
    if len(xs): box[max(0, ys.min() - 22):ys.max() + 22, max(0, xs.min() - 40):xs.max() + 40] = True
    stroke = np.abs(rlab[..., 0] - Lb) > 10
    clean = ((lines | (box & stroke)) & rin & ~skin)
    clean = cv2.dilate(clean.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    clean &= rin & ~skin
    out[clean] = rbg
    # 正确文字：颜色按白模文字相对底色的明暗换算到写实屏幕亮度
    gtxt = np.median(g[t > 0], axis=0); gbg = cv2.cvtColor(np.uint8([[bg]]), cv2.COLOR_LAB2BGR)[0, 0].astype(np.float32)
    ratio = (rbg.astype(np.float32) + 1) / (gbg + 1)
    tcol = np.clip(gtxt * ratio, 0, 255)
    a = (np.clip(t_soft, 0, 1) * (clean | (lines & rin)) * (~skin))[..., None]
    out = (out * (1 - a) + tcol[None, None, :] * a).astype(np.uint8)
    return out, M

def notice_on_real(r, lines, prev=None):
    """白纸文字直接画在写实帧上（11-27：白模渲染有颗粒，梯度法找不到纸）：画面里最亮、最白的大块 = 纸；
    按纸的外接四边形透视排版，只画在纸露出来的像素上（人挡住的地方自然被遮住）"""
    from PIL import Image, ImageDraw, ImageFont
    h, w = r.shape[:2]
    hsv = cv2.cvtColor(cv2.GaussianBlur(r, (7, 7), 0), cv2.COLOR_BGR2HSV)
    v = hsv[..., 2]; paper = ((v > max(150, np.percentile(v, 80))) & (hsv[..., 1] < 40)).astype(np.uint8)
    paper = cv2.morphologyEx(paper, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(paper)
    if n < 2: return r, prev
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    if st[i, cv2.CC_STAT_AREA] < 0.03 * h * w: return r, prev
    m = (lab == i).astype(np.uint8)
    cnt = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    x0, y0, bw, bh = cv2.boundingRect(cnt); grow = int(bw * 0.12)   # 亮度阈值常只抓到纸偏亮的一半：横向放宽
    box = cv2.boxPoints(cv2.minAreaRect(cnt)) + np.float32([[0, 0]]); q = sorted(box.tolist(), key=lambda p: p[1]); top = sorted(q[:2]); bot = sorted(q[2:])
    dst = np.float32([top[0], top[1], bot[1], bot[0]])
    if prev is not None and np.shape(prev) == (4, 2): dst = (0.7 * prev + 0.3 * dst).astype(np.float32)   # 平滑，防抖
    W, H = 760, 1000; img = Image.new('L', (W, H), 0); d = ImageDraw.Draw(img); font = 'C:/Windows/Fonts/msyh.ttc'
    sizes = [110] + [56] * (len(lines) - 2) + [50]; y = 90   # 特写里的通知要大到能读
    for k, (t, s) in enumerate(zip(lines, sizes)):
        f = ImageFont.truetype(font, s); tw = d.textbbox((0, 0), t, font=f)[2]
        x = (W - tw) // 2 if k == 0 else (W - tw - 40 if k == len(lines) - 1 else 30)
        d.text((x, y), t, font=f, fill=255); y += int(s * (1.9 if k == 0 else 1.6)) + (70 if k == len(lines) - 2 else 0)
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [W, 0], [W, H], [0, H]]), dst)
    ink = cv2.warpPerspective(np.asarray(img), M, (w, h), flags=cv2.INTER_LINEAR).astype(np.float32) / 255
    quadm = np.zeros((h, w), np.uint8); cv2.fillConvexPoly(quadm, dst.astype(np.int32), 1)
    vis = (quadm > 0) & (v > 0.6 * np.median(v[m > 0]))   # 纸的范围里不暗的像素（右半边偏暗也算纸）；人挡住的地方暗，不画
    ink *= cv2.erode(vis.astype(np.uint8), np.ones((3, 3), np.uint8))   # 只画在纸露出来的地方
    paper_col = np.median(r[m > 0], axis=0).astype(np.float32); ink_col = paper_col * 0.18   # 黑字，跟着纸的明暗
    out = r.astype(np.float32) * (1 - ink[..., None]) + ink_col[None, None, :] * ink[..., None]
    return out.astype(np.uint8), dst

def frames_of(p):
    if p.lower().endswith(('.png', '.jpg')): return [cv2.imread(p)]
    cap = cv2.VideoCapture(p); fs = []
    while True:
        ok, f = cap.read()
        if not ok: break
        fs.append(f)
    return fs

if __name__ == '__main__':
    real, grey, out = sys.argv[1:4]
    R = frames_of(real); G = frames_of(grey)
    NOTICE = sys.argv[4].split('|') if len(sys.argv) > 4 else None   # 第 4 个参数 "行1|行2|…"：白纸排版模式（闭馆通知），直接画在写实帧上
    res, M = [], None
    for i, r in enumerate(R):
        o, M = notice_on_real(r, NOTICE, M) if NOTICE else fix(r, G[min(i, len(G) - 1)], M); res.append(o)
    if out.lower().endswith(('.png', '.jpg')): cv2.imwrite(out, res[0])
    else:
        tmp = tempfile.mkdtemp()
        for i, f in enumerate(res): cv2.imwrite(os.path.join(tmp, '%05d.png' % i), f)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import config
        subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-framerate', '24', '-i', os.path.join(tmp, '%05d.png'), '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', out], check=True)
    print('手机屏幕文字修正完成：', out, len(res), '帧')
