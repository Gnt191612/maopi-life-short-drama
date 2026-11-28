# -*- coding: utf-8 -*-
"""跟拍/环绕镜头的白模尾帧（本地运行，免费；11-28）：按原机位渲镜头最后一帧 1920×1080 → dist/cloud_pack/<id>/end.png，
并按骨架数据算出最后一帧里入画的人、看得见脸的人，写进 task.json 的 end_cast / face_visible_end。
云端 keyframes.py --end 给它出写实尾帧 kf/<id>@end.png，video_h3.py 把它当 last_frame（首尾帧都钉住）。
原因（踩坑 91）：只有首帧时，跟拍镜头一移出首帧范围模型就自己编——s01_01_0577 白模机位几乎不动，视频却一路推进成望不到头的大通铺，
还复制出三个陈瑶；1174 变大通铺，1244 变满屋人的自习室。深度/姿态强度加到 0.6/1.0 也拉不回来。
不覆盖 first.png（首帧已审过）。用法：python cloud/make_endframes.py [id,id,...]（默认全部 track/arc）"""
import os, sys, json, glob, shutil, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import config
from visible_cast import ID2CID, MIN_KP
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
END_FIX = {   # 人工核对尾帧后的修正（骨架判断不准的）
    's01_01_0577': {'end_cast': ['chen'], 'face_visible_end': []},   # 陈瑶坐在后排书桌前，人小、被床梯挡住大半，骨架点数不够
}

def end_people(seg, f1):
    """最后一帧（取镜头结尾最近的一份骨架数据）：入画的人 {cid: 看得见脸}；没有数据返回 None"""
    for f in range(f1, f1 - 9, -1):
        p = os.path.join(config.RENDERS, seg, 'pose_%04d.json' % f)
        if not os.path.exists(p): continue
        out = {}
        for q in json.load(open(p)).get('people', []):
            kp = q['pose_keypoints_2d']; un = q.get('unoccluded', [1] * 18)
            ok = lambda i: kp[i * 3 + 2] > 0 and un[i]
            if sum(ok(i) for i in range(18)) < MIN_KP: continue
            c = ID2CID.get(q['person_id'], 'extra%d' % q['person_id'])
            out[c] = bool(q.get('facing', 1) > -0.35 and ok(0) and (ok(14) or ok(15)))
        return out
    return None

def main():
    ids = [x for x in sys.argv[1].split(',') if x] if len(sys.argv) > 1 else None
    by_seg = {}
    for tj in sorted(glob.glob(os.path.join(PACK, 's*_*_*', 'task.json'))):
        t = json.load(open(tj, encoding='utf-8'))
        if (ids and t['id'] not in ids) or (not ids and t.get('move') not in ('track', 'arc')): continue
        by_seg.setdefault(t['segment'], []).append((tj, t))
    for seg, jobs in by_seg.items():
        blend = os.path.join(config.SHOTS, seg + '.blend')
        if not os.path.exists(blend): print('没有片段工程', seg); continue
        tmp = os.path.join(PACK, '_end_' + seg)
        subprocess.run([config.BLENDER, '-b', blend, '--factory-startup', '-P', os.path.join(ROOT, 'cloud', 'render_first.py'), '--', tmp] + [str(t['frames'][1]) for _, t in jobs],
                       env=config.blender_env(), capture_output=True)
        for tj, t in jobs:
            src = os.path.join(tmp, 'first_%04d.png' % t['frames'][1])
            if not os.path.exists(src): print('尾帧没渲出来', t['id']); continue
            shutil.copy(src, os.path.join(os.path.dirname(tj), 'end.png'))
            ep = end_people(seg, t['frames'][1])
            if ep is not None:
                t['end_cast'] = sorted(c for c in ep if not c.startswith('extra'))
                t['end_extras'] = sum(1 for c in ep if c.startswith('extra'))
                t['face_visible_end'] = sorted(c for c, v in ep.items() if v and not c.startswith('extra'))
            t.update(END_FIX.get(t['id'], {}))
            if ep is not None or t['id'] in END_FIX:
                json.dump(t, open(tj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('END', t['id'], t.get('end_cast'), '脸', t.get('face_visible_end'), flush=True)
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
