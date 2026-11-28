# -*- coding: utf-8 -*-
"""多人全景首帧里只有一个人画错（性别/发型），而 Qwen 换脸会换错人时：把这个人那一块裁出来放大，单独用二转三重画，再羽化贴回（11-27 s08_01_0001 陈瑶被画成长发女生）。
裁出来的小图里只有他一个人，提示词只描述他，模型不会认错人。原图留 kf_bad/。
用法（云端）：python crop_regen.py <镜头id> <x0,y0,x1,y1（0~1 比例）> "<这个人的中文描述>" [重绘起始步，默认 4]"""
import os, sys, shutil
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run, keyframes as K
tid, box, desc = sys.argv[1:4]; start = int(sys.argv[4]) if len(sys.argv) > 4 else 4
src = os.path.join(K.OUTK, tid + '.png'); im = cv2.imread(src); h, w = im.shape[:2]
x0, y0, x1, y1 = [float(v) for v in box.split(',')]; X0, Y0, X1, Y1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
os.makedirs('/root/v11_out/kf_bad', exist_ok=True); cv2.imwrite('/root/v11_out/kf_bad/%s.before_crop.png' % tid, im)
crop = im[Y0:Y1, X0:X1]; s = 1024.0 / max(crop.shape[:2]); big = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4)
cv2.imwrite(os.path.join(K.INP, 'kfcrop_%s.png' % tid), big)
pre = '画面里只有这一个人：%s。真实照片质感，保持姿势、构图和光线不变。' % desc
res = comfy_run.run(K.WF_REAL, 'kfcrop_' + tid, {'10.image': 'kfcrop_%s.png' % tid, '21.start_at_step': start}, prefix=pre)
if not res: print('重画失败'); sys.exit(1)
new = cv2.resize(cv2.imread(res), (X1 - X0, Y1 - Y0), interpolation=cv2.INTER_AREA)
m = np.zeros((Y1 - Y0, X1 - X0), np.float32); pad = int(0.12 * min(m.shape)); m[pad:-pad, pad:-pad] = 1
m = cv2.GaussianBlur(m, (0, 0), pad / 2.0)[..., None]   # 羽化边缘，贴回不留缝
im[Y0:Y1, X0:X1] = (im[Y0:Y1, X0:X1] * (1 - m) + new * m).astype(np.uint8)
cv2.imwrite(src, im); print('局部重画完成', tid, (X0, Y0, X1, Y1))
