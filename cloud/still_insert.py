# -*- coding: utf-8 -*-
"""手机屏幕之类的「静物特写」不用模型生成：用审过的写实首帧做轻微推近 + 手持晃动的视频（11-28，踩坑 95）。
s05_01_0090 手机屏幕特写长 321 帧，画面里没有人物骨架可约束，Pika 生成到四分之一就变成两个林晓坐在食堂吃饭（深度 0.9 也拦不住）。
屏幕上的字本来就由 postfix_apply.py 逐帧按白模贴回（跟着画面移动对齐），所以只要底图稳定就行。
task.json 写 "still_insert": true（可选 "tremor": 结尾手抖幅度，像素）→ video_h3.py 直接调这里，不走模型。
用法：python still_insert.py <首帧.png> <输出.mp4> <帧数> [--res 1344x768] [--tremor 3]"""
import sys, os, subprocess, tempfile, shutil
import cv2, numpy as np

def make(kf, out, n, res=(1344, 768), tremor=3.0, seed=7):
    W, H = res; src = cv2.resize(cv2.imread(kf), (W, H), interpolation=cv2.INTER_LANCZOS4)
    rng = np.random.default_rng(seed)
    def smooth(k):   # 低频随机游走（手持的慢漂移），k 帧一个控制点再插值
        pts = rng.normal(0, 1, n // k + 3); return np.interp(np.arange(n) / k, np.arange(len(pts)), pts)
    dx, dy, rot = smooth(36) * 4, smooth(40) * 3, smooth(48) * 0.25
    t = np.linspace(0, 1, n); shake = tremor * np.clip((t - 0.5) / 0.5, 0, 1)   # 后半段手越来越抖
    tx, ty = rng.normal(0, 1, n) * shake, rng.normal(0, 1, n) * shake
    tmp = tempfile.mkdtemp()
    for i in range(n):
        s = 1.04 + 0.03 * t[i]   # 留边防黑边 + 缓慢推近
        M = cv2.getRotationMatrix2D((W / 2, H / 2), rot[i], s); M[0, 2] += dx[i] + tx[i]; M[1, 2] += dy[i] + ty[i]
        cv2.imwrite(os.path.join(tmp, '%05d.png' % i), cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT))
    ffm = 'ffmpeg'   # 云端在 PATH 里；本地用 config.FFMPEG（tools/ffmpeg）
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import config; ffm = config.FFMPEG
    except Exception: pass
    subprocess.run([ffm, '-y', '-loglevel', 'error', '-framerate', '24', '-i', os.path.join(tmp, '%05d.png'), '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', out], check=True)
    shutil.rmtree(tmp)

if __name__ == '__main__':
    a = sys.argv[1:]; res = tuple(int(v) for v in (a[a.index('--res') + 1] if '--res' in a else '1344x768').split('x'))
    make(a[0], a[1], int(a[2]), res, float(a[a.index('--tremor') + 1]) if '--tremor' in a else 3.0)
    print('STILL OK', a[1])
