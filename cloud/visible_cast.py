# -*- coding: utf-8 -*-
"""每个镜头实际入画的角色 → task.json 的 others 字段（11-27，踩坑记录 68）。
画面里出现但不是主角的人（背影、肩膀、画面边缘）也要写进提示词，否则模型会随意补（男生背影被画成长发女生）。
数据来自白模：blender/export_pose.py 导出的 build/renders/<段>/pose_####.json（每人固定角色编号 + 18 个关键点，第三位 1=在画面内）。
先导出（只做投影，不渲染，每段约 10 秒）：blender -b --factory-startup -P blender/export_pose.py -- <段> --step 4
用法：python cloud/visible_cast.py [打包目录，默认 dist/cloud_pack] [--write]   不加 --write 只出报告"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import config
ID2CID = {1: 'lin', 2: 'chen', 3: 'zhou', 4: 'wang', 5: 'mom', 6: 'classA', 7: 'classB'}   # 和 export_pose.py 的 FIXED 一致
MIN_KP = 4        # 一帧里至少 4 个关键点在画面内才算「入画」（只露一只手不算）
MIN_SHARE = 0.3   # 至少 30% 的采样帧入画才算这个镜头里有他
_OV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'visible_overrides.json')
OVERRIDES = {k: v for k, v in json.load(open(_OV, encoding='utf-8')).items() if not k.startswith('_')} if os.path.exists(_OV) else {}

def _pose_frames(pose_mp4):
    """读打包里的骨架控制视频（云端实际用的那份），返回 帧序号 → 图像"""
    import cv2
    cap = cv2.VideoCapture(pose_mp4); out = []
    while True:
        ok, im = cap.read()
        if not ok: break
        out.append(im)
    return out

def visible(seg, f0, f1, pose_mp4=None):
    """返回 {角色: 入画帧占比}；没有骨架数据返回 None。
    给了 pose_mp4（打包里的骨架视频）就逐点核对：该位置确实画着骨架才算——.blend 打包后可能又改过（11-27：s02_01 打包后才加进同学甲乙，按新工程算会误判入画）"""
    fs = [f for f in range(f0, f1 + 1) if os.path.exists(os.path.join(config.RENDERS, seg, 'pose_%04d.json' % f))]
    if not fs: return None
    pv = _pose_frames(pose_mp4) if pose_mp4 and os.path.exists(pose_mp4) else None
    cnt = {}
    for f in fs:
        im = pv[f - f0] if pv and 0 <= f - f0 < len(pv) else None
        for p in json.load(open(os.path.join(config.RENDERS, seg, 'pose_%04d.json' % f))).get('people', []):
            kp = p['pose_keypoints_2d']; un = p.get('unoccluded')   # 新版 export_pose 带遮挡检测；旧数据没有就只看是否在画面内（会把被挡住的人也算进来）
            n = 0
            for i in range(0, len(kp), 3):
                if kp[i + 2] <= 0 or (un is not None and not un[i // 3]): continue
                if im is not None:
                    h, w = im.shape[:2]; x, y = int(kp[i] * w / 960), int(kp[i + 1] * h / 540)
                    if im[max(0, y - 6):y + 7, max(0, x - 6):x + 7].max() < 60: continue   # 打包的骨架图这里是黑的 → 当时这里没人
                n += 1
            if n >= MIN_KP:
                c = ID2CID.get(p['person_id'], 'extra%d' % p['person_id']); cnt[c] = cnt.get(c, 0) + 1
    return {c: n / len(fs) for c, n in cnt.items()}

def face_visible(seg, f0, f1):
    """白模第一帧（取镜头开头最近的一份骨架数据）里脸看得见的角色：脸朝向相机（facing > -0.35）且鼻子和至少一只眼没被挡。
    首帧换脸只对这些人做（11-27 s06_01_0446：低头只露头顶，被硬换上一张正脸）。没有 facing 数据返回 None（keyframes 按老规则）"""
    for f in range(f0, min(f1, f0 + 8) + 1):
        p = os.path.join(config.RENDERS, seg, 'pose_%04d.json' % f)
        if not os.path.exists(p): continue
        out = []
        for q in json.load(open(p)).get('people', []):
            if 'facing' not in q: return None
            un = q.get('unoccluded', [1] * 18); kp = q['pose_keypoints_2d']
            ok = lambda i: kp[i * 3 + 2] > 0 and un[i]
            if q['facing'] > -0.35 and ok(0) and (ok(14) or ok(15)):
                c = ID2CID.get(q['person_id'])
                if c: out.append(c)
        return sorted(out)
    return None

def others_for(task, pose_mp4=None):
    v = visible(task['segment'], *task['frames'], pose_mp4=pose_mp4)
    if v is None: return None
    return sorted(c for c, s in v.items() if s >= MIN_SHARE and c not in task.get('characters', []) and not c.startswith('extra'))

if __name__ == '__main__':
    pack = next((a for a in sys.argv[1:] if not a.startswith('--')), os.path.join(ROOT, 'dist', 'cloud_pack'))
    nodata, changed = [], 0
    for tp in sorted(glob.glob(os.path.join(pack, 's*_*_*', 'task.json'))):
        t = json.load(open(tp, encoding='utf-8')); pm = os.path.join(os.path.dirname(tp), 'pose.mp4'); v = visible(t['segment'], *t['frames'], pose_mp4=pm)
        if v is None: nodata.append(t['id']); continue
        o = sorted(c for c, s in v.items() if s >= MIN_SHARE and c not in t.get('characters', []) and not c.startswith('extra'))
        ov = OVERRIDES.get(t['id'], {}); o = sorted((set(o) - set(ov.get('remove', []))) | set(ov.get('add', [])))   # 人工核对过的修正
        extras = sorted(c for c, s in v.items() if c.startswith('extra') and s >= MIN_SHARE)
        if o or extras or v.keys() - set(t.get('characters', [])):
            print('%s 主角=%s 入画=%s → others=%s%s' % (t['id'], ','.join(t.get('characters', [])) or '无',
                  ' '.join('%s:%.0f%%' % (c, s * 100) for c, s in sorted(v.items())), o, ('  路人 %s' % extras) if extras else ''))
        fv = face_visible(t['segment'], *t['frames'])
        if '--write' in sys.argv and (o != t.get('others', []) or len(extras) != t.get('extras', 0) or fv != t.get('face_visible')):
            t['others'] = o; t['extras'] = len(extras)   # extras = 白模里的无名路人数（提示词写成「另有 N 名同学」）
            if fv is not None: t['face_visible'] = fv
            json.dump(t, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); changed += 1
    if nodata: print('没有骨架数据（先跑 export_pose.py）：', ' '.join(nodata))
    print('写入 %d 个 task.json' % changed if '--write' in sys.argv else '（只出报告，加 --write 写入）')
