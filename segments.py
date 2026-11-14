# -*- coding: utf-8 -*-
"""分段与时长（不依赖 Blender，总控和拍摄引擎共用，保证时间轴一致）。"""
import os, json
import config
from story_scenes import SCENES
from lines import LINES

FPS, LEAD = 24, 0.35
AUD = config.AUDIO
META = json.load(open(os.path.join(AUD, 'meta.json'), encoding='utf-8'))
TEXT = {l[0]: (l[1], l[2]) for l in LINES}
CID = {'林晓': 'lin', '陈瑶': 'chen', '周明远': 'zhou', '王老师': 'wang', '林母': 'mom', '同学甲': 'classA', '同学乙': 'classB'}
EST_SET = {'s01': 'ext_dorm_am', 's02': 'ext_library', 's03': 'ext_dorm_pm', 's05': 'ext_canteen', 's06': 'ext_dusk',
           's07': 'track', 's08': 'ext_corridor', 's09': 'ext_dorm_nt', 's10': 'lawn'}

def audio_plan(bt):
    out, t = [], LEAD
    for l in bt['line']: out.append((t, l, True)); t += META[l]['dur'] + 0.3
    for l in bt['os']: out.append((t, l, False)); t += META[l]['dur'] + 0.25
    return out

def beat_dur(bt):
    ap = audio_plan(bt)
    end = max([o + META[l]['dur'] for o, l, _ in ap], default=0) + (0.45 if ap else 0)
    return max(bt['dur'], end)

def beat_frames(bt):
    return max(2, round(beat_dur(bt) * FPS))

def loc_of(bt, scene):
    if bt['cam'] == 'est': return EST_SET.get(scene['id'], scene['sc'])
    return bt.get('sc') or scene['sc']

def segments():
    """[(seg_id, scene, set_name, beats)]：每场戏按地点切段，seg_id 如 s03_02"""
    out = []
    for s in SCENES:
        cur, cur_loc, k = [], None, 0
        for bt in s['beats']:
            L = loc_of(bt, s)
            if cur and L != cur_loc:
                out.append(('%s_%02d' % (s['id'], k), s, cur_loc, cur)); cur = []; k += 1
            cur.append(bt); cur_loc = L
        if cur: out.append(('%s_%02d' % (s['id'], k), s, cur_loc, cur))
    return out
