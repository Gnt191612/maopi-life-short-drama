# -*- coding: utf-8 -*-
"""首帧里某个角色的上衣颜色不对、提示词多次拉不回来时（白模衣服本身太暗），在首帧上局部调色（11-27 s05_01_0001 周明远三次都画成深灰上衣）。
用白模骨架（pose json，固定角色编号）定位这个人的躯干（肩到胯），只改其中低饱和度的布料像素，保留明暗和褶皱。
用法：python cloud/recolor_top.py <首帧.png> <镜头id> <角色> <目标色 B,G,R> <输出.png>"""
import os, sys, json, glob
import cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import config
ID = {'lin': 1, 'chen': 2, 'zhou': 3, 'wang': 4, 'mom': 5, 'classA': 6, 'classB': 7}
kp_path, tid, cid, col, out = sys.argv[1:6]
seg, f0 = tid.rsplit('_', 1)[0], int(tid.rsplit('_', 1)[1])
js = sorted(glob.glob(os.path.join(config.RENDERS, seg, 'pose_*.json')), key=lambda p: abs(int(p[-9:-5]) - f0))[0]
person = next(p for p in json.load(open(js))['people'] if p['person_id'] == ID[cid])
k = np.array(person['pose_keypoints_2d']).reshape(-1, 3)
im = cv2.imread(kp_path); h, w = im.shape[:2]; sx, sy = w / 960, h / 540
def hull_of(kk, grow):
    pp = [(kk[i, 0] * sx, kk[i, 1] * sy) for i in range(18) if kk[i, 2] > 0]
    hm = np.zeros((h, w), np.uint8)
    if len(pp) >= 3: cv2.fillConvexPoly(hm, cv2.convexHull(np.float32(pp)).astype(np.int32), 1)
    return cv2.dilate(hm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
m = hull_of(k, int(0.09 * w))   # 这个人全部关键点外扩（白模和首帧位置有偏差，11-27 只外扩躯干时只染到肩膀）
for q in json.load(open(js))['people']:   # 扣掉别人（林晓也是灰卫衣，不能染到他）
    if q['person_id'] != ID[cid]: m[hull_of(np.array(q['pose_keypoints_2d']).reshape(-1, 3), int(0.02 * w)) > 0] = 0
hip_y = max(k[i, 1] for i in (8, 11) if k[i, 2] > 0) * sy if any(k[i, 2] > 0 for i in (8, 11)) else h
m[int(hip_y + 0.12 * h):, :] = 0   # 只改胯部以上（裤子不动）；首帧里人常比白模低一些，放宽 12%
# 白模深度图把这个人单独分出来（前后站的人深度不同；11-27 只用骨架区域时染到了林晓和桌子）
import subprocess
dp = os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'depth.mp4'); dpng = os.path.join(os.path.dirname(os.path.abspath(out)), '_depth0.png')
subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-i', dp, '-frames:v', '1', dpng], check=True)
dep = cv2.resize(cv2.cvtColor(cv2.imread(dpng), cv2.COLOR_BGR2GRAY), (w, h)).astype(np.float32)
ref = np.median([dep[int(k[i, 1] * sy), int(k[i, 0] * sx)] for i in (1, 2, 5, 8, 11) if k[i, 2] > 0 and 0 <= int(k[i, 1] * sy) < h and 0 <= int(k[i, 0] * sx) < w])
m = (m > 0) & (np.abs(dep - ref) < 10)
m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
cloth = (m > 0) & (hsv[..., 1] < 70) & (hsv[..., 2] < 170)   # 低饱和、不太亮的布料（避开皮肤和背景高光）
cloth = cv2.morphologyEx(cloth.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
tgt = np.uint8([[[int(c) for c in col.split(',')]]]); th = cv2.cvtColor(tgt, cv2.COLOR_BGR2HSV)[0, 0]
hsv2 = hsv.copy(); hsv2[..., 0][cloth] = th[0]; hsv2[..., 1][cloth] = np.clip(th[1] * 0.75, 0, 255)
hsv2[..., 2][cloth] = np.clip(hsv[..., 2][cloth].astype(np.float32) * 1.15, 0, 255).astype(np.uint8)
res = cv2.cvtColor(hsv2, cv2.COLOR_HSV2BGR)
a = cv2.GaussianBlur(cloth.astype(np.float32), (7, 7), 0)[..., None]
cv2.imwrite(out, (im * (1 - a) + res * a).astype(np.uint8)); print('调色完成', out, '像素', int(cloth.sum()))
