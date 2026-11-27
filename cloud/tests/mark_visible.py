# -*- coding: utf-8 -*-
"""核对 visible_cast 的判断：在白模画面上把某角色「入画且没被挡」的关键点标成红点
用法：python cloud/tests/mark_visible.py <镜头id> <角色> [输出jpg]"""
import os, sys, json, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import config, cv2
CID2ID = {'lin': 1, 'chen': 2, 'zhou': 3, 'wang': 4, 'mom': 5, 'classA': 6, 'classB': 7}
tid, cid = sys.argv[1], sys.argv[2]; out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, 'build', 'review', 'visible', 'mark_%s_%s.jpg' % (tid, cid))
t = json.load(open(os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'task.json'), encoding='utf-8')); seg = t['segment']; f0, f1 = t['frames']
best = None
for f in range(f0, f1 + 1):
    p = os.path.join(config.RENDERS, seg, 'pose_%04d.json' % f)
    if not os.path.exists(p): continue
    for q in json.load(open(p))['people']:
        if q['person_id'] != CID2ID[cid]: continue
        kp, un = q['pose_keypoints_2d'], q.get('unoccluded', [1] * 18)
        pts = [(kp[i * 3], kp[i * 3 + 1]) for i in range(18) if kp[i * 3 + 2] > 0 and un[i]]
        if not best or len(pts) > len(best[1]): best = (f, pts)
if not best: print('没有入画帧'); sys.exit()
f, pts = best; tmp = out + '.png'
subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-ss', '%.3f' % ((f - f0) / 24.0), '-i', os.path.join(ROOT, 'dist', 'cloud_pack', tid, 'beauty.mp4'), '-frames:v', '1', '-vf', 'scale=960:540', tmp])
im = cv2.imread(tmp)
for x, y in pts: cv2.circle(im, (int(x), int(y)), 7, (0, 0, 255), -1)
cv2.putText(im, '%s %s f%d n=%d' % (tid, cid, f, len(pts)), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
cv2.imwrite(out, im); os.remove(tmp); print(out)
