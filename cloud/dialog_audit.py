# -*- coding: utf-8 -*-
"""台词与画面对齐审查（本地）：按 run_all.previs 完全相同的算法，算出每句台词在成片里的时间、所在镜头、说话人、这一拍的白模动作，
标出「说话人不在本镜头出场角色里」「台词跨镜头」等错位；从成片抽出每句台词说到一半时的画面拼成对照图（画面里已烧好字幕）。
2026-11-27：用户指出全片字幕和人物说话、动作对齐得不够好。
用法：python cloud/dialog_audit.py [--at 秒]   （--at：查成片某一时刻落在哪个镜头）
输出：build/review/dialog/dialog_##.jpg（每张 12 句）+ dialog.json"""
import os, sys, json, glob, subprocess, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import config, segments as S
from looks import NAME
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); OUT = os.path.join(ROOT, 'build', 'review', 'dialog'); os.makedirs(OUT, exist_ok=True)
FILM = os.path.join(ROOT, 'build', 'final', '毛坯人生，精装朋友圈_成片.mp4')
FF = config.FFMPEG; FP = FF.replace('ffmpeg.exe', 'ffprobe.exe')
dur = lambda p: float(subprocess.run([FP, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip() or 0)
INTRO = dur(os.path.join(ROOT, 'build', 'intro', 'intro.mp4'))
CID = {v: k for k, v in NAME.items()}
ACT = {}
try:
    from story_scenes import SCENES
    for sc in SCENES:
        for bt in sc['beats']: ACT[bt['id']] = bt
except Exception:
    pass
segs = [s[0] for s in S.segments() if os.path.exists(os.path.join(config.SHOTS, s[0] + '_timeline.json'))]
tasks = {}
for tj in glob.glob(os.path.join(PACK, '*', 'task.json')):
    t = json.load(open(tj, encoding='utf-8')); tasks.setdefault(t['segment'], []).append(t)
rows, t0 = [], 0.0
seg_span = []
for sid in segs:
    tl = json.load(open(os.path.join(config.SHOTS, sid + '_timeline.json'), encoding='utf-8')); n_end = max(b['f1'] for b in tl)
    seg_span.append((sid, t0, n_end))
    for b in tl:
        for fr, lid in b['audio']:
            if lid.startswith('X') or lid not in S.TEXT: continue
            d = S.META[lid]['dur']; spk, txt = S.TEXT[lid]
            f1 = fr + int(d * 24)
            shot = next((t for t in tasks.get(sid, []) if t['frames'][0] <= fr <= t['frames'][1]), None)
            shot_end = next((t for t in tasks.get(sid, []) if t['frames'][0] <= f1 <= t['frames'][1]), None)
            chars = shot['characters'] if shot else []
            cid = CID.get(spk)
            flags = []
            if cid and chars and cid not in chars: flags.append('说话人不在画面角色里')
            if shot and shot_end and shot['id'] != shot_end['id']: flags.append('跨镜头→' + shot_end['id'])
            bt = ACT.get(b['id'], {})
            rows.append(dict(t=round(INTRO + t0 + (fr - 1) / 24.0, 2), dur=round(d, 2), seg=sid, beat=b['id'], frame=fr, shot=shot['id'] if shot else '', chars=chars,
                             speaker=spk, text=txt, act=bt.get('act', '') if isinstance(bt.get('act', ''), str) else '；'.join(bt.get('act')), flags=flags, lid=lid))
    t0 += n_end / 24.0
if '--at' in sys.argv:
    at = float(sys.argv[sys.argv.index('--at') + 1]) - INTRO
    for sid, s0, n in seg_span:
        if s0 <= at < s0 + n / 24.0:
            fr = int((at - s0) * 24) + 1
            shot = next((t for t in tasks.get(sid, []) if t['frames'][0] <= fr <= t['frames'][1]), None)
            print('AT', sid, 'frame', fr, 'shot', shot['id'] if shot else None, shot['characters'] if shot else '', (shot or {}).get('prompt', '')[:200])
    sys.exit()
json.dump(rows, open(os.path.join(OUT, 'dialog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('片头 %.2fs，台词 %d 句，标记 %d 句' % (INTRO, len(rows), sum(1 for r in rows if r['flags'])))
for r in rows:
    if r['flags']: print('%7.1fs %s %s「%s」 %s %s' % (r['t'], r['shot'], r['speaker'], r['text'][:24], r['chars'], r['flags']))
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
cap = cv2.VideoCapture(FILM); W, H = 480, 270
for k in range(0, len(rows), 12):
    sheet = Image.new('RGB', (W * 4, (H + 44) * 3), (25, 25, 25)); dr = ImageDraw.Draw(sheet)
    for j, r in enumerate(rows[k:k + 12]):
        cap.set(cv2.CAP_PROP_POS_MSEC, (r['t'] + min(r['dur'] / 2, 1.2)) * 1000); ok, fr = cap.read()
        if not ok: continue
        im = Image.fromarray(cv2.cvtColor(cv2.resize(fr, (W, H)), cv2.COLOR_BGR2RGB)); x, y = (j % 4) * W, (j // 4) * (H + 44)
        sheet.paste(im, (x, y))
        col = (255, 90, 90) if r['flags'] else (255, 230, 0)
        dr.text((x + 4, y + H + 2), '#%d %.0fs %s 说话:%s 画面:%s' % (k + j + 1, r['t'], r['shot'][4:], r['speaker'], ','.join(NAME.get(c, c) for c in r['chars'])), font=F, fill=col)
        dr.text((x + 4, y + H + 22), ('动作:' + r['act'])[:34], font=F, fill=(200, 200, 200))
    sheet.save(os.path.join(OUT, 'dialog_%02d.jpg' % (k // 12)), quality=85)
print('SHEETS', (len(rows) + 11) // 12)
