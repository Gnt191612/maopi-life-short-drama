# -*- coding: utf-8 -*-
"""全片提示词自动审查（11-27，用户要求「对全篇提示词做细致全面的检查，保证符合现实和剧情」）。
先跑 cloud/export_prompts.py，再跑本脚本：python cloud/audit_prompts.py → build/review/prompts/审查报告.md
自动查能查的矛盾，人工再按报告逐条看剧情和白模画面。每条规则都来自踩过的坑（见注释）。"""
import os, sys, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import looks, lighting
from h3_prompt import NAME2CID
P = os.path.join(ROOT, 'build', 'review', 'prompts')
rows = json.load(open(os.path.join(P, 'prompts.json'), encoding='utf-8'))

NIGHT = {'dorm_nt', 'ext_dorm_nt', 'track', 'home_nt'}; DUSK = {'dorm_dusk', 'ext_dusk'}
DAY = {'dorm_am', 'dorm_pm', 'ext_dorm_am', 'ext_dorm_pm', 'ext_library', 'lib', 'libdoor', 'ext_canteen', 'canteen', 'ext_corridor', 'class', 'lawn', 'home'}
W_DAY = r'\b(sunny|sunlight|daylight|bright sun|blue sky|midday|noon|morning sun|afternoon sun)\b'
W_NIGHT = r'\b(night|dark sky|moonlight|starry|midnight)\b'
W_DUSK = r'\b(dusk|sunset|evening sky|orange sky|twilight)\b'
FEMALE = r'\b(woman|girl|she|her|lady|female)\b'
MALE_CIDS = {'lin', 'chen', 'zhou', 'wang', 'classA'}
CLOTH = {   # 和人物库定稿冲突的衣着词（踩坑：林晓黑外套、陈瑶领带、三人黑西装）
    'chen': r'\b(tie|necktie|suit|blazer|hoodie|sweater|t-shirt)\b',
    'lin': r'\b(suit|blazer|black jacket|white t-shirt|tie|shirt and tie)\b',
    'zhou': r'\b(suit|blazer|hoodie|white shirt|tie)\b',
}
NEG = r"\b(no|not|without|never|don't|doesn't|isn't|nobody|none)\b"
WORDNUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}

issues = {}
def add(tid, kind, msg): issues.setdefault(tid, []).append((kind, msg))

for r in rows:
    tid, st, desc = r['id'], r['set'], r['beat_en']; d = desc.lower()
    chars, others, extras = r['characters'], r.get('others', []), r.get('extras', 0) or 0
    fv = r.get('face_visible'); onscreen = set(chars) | set(others)
    # 1 时间/光线（踩坑 70）
    if st in NIGHT | DUSK and re.search(W_DAY, d): add(tid, '时间', '场景 %s 是傍晚/夜里，描述里却有白天词：%s' % (st, re.findall(W_DAY, d)))
    if st in DAY and re.search(W_NIGHT, d): add(tid, '时间', '场景 %s 是白天，描述里却有夜晚词：%s' % (st, re.findall(W_NIGHT, d)))
    if st in DAY and re.search(W_DUSK, d): add(tid, '时间', '场景 %s 是白天，描述里却有黄昏词：%s' % (st, re.findall(W_DUSK, d)))
    if not lighting.en(st): add(tid, '时间', '场景 %s 没有光线描述（lighting.py 缺这一项）' % st)
    # 2 首帧模式下描述里写了场景物体（踩坑 65）——只提示，人工确认首帧里有没有
    BG_OK = set(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bg_checked.json'), encoding='utf-8'))) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bg_checked.json')) else set()
    for w in ('window', 'sky', 'sunset', 'loft bed', 'bookshel', 'chalkboard', 'trees', 'quilt', 'blanket', 'takeout', 'mirror', 'sink'):   # 被子/外卖盒/镜子：描述成一直在场、首帧却没有，视频会改场景（s01_01_0348）
        if re.search(r'\b' + w, d) and not re.search(r'\b' + w + r'(ing|ed)\b', d) and tid not in BG_OK:   # 按单词匹配（sinking 不算 sink）
            add(tid, '背景', '描述里提到「%s」，确认白模首帧里真有，否则模型会凭空加' % w)
    # 3 性别（踩坑：男主被画成女生）
    if onscreen and onscreen <= MALE_CIDS and re.search(FEMALE, d): add(tid, '性别', '画面里全是男性，描述却有女性词：%s' % re.findall(FEMALE, d))
    # 4 衣着
    OWN = {'chen': r'glasses|slim young man', 'lin': r'chubby|hoodie', 'zhou': r'curly|olive|thin young man'}   # 按分句认人，只查这句说的那个人（多人描述里别人的衣着不算）
    for c in onscreen:
        hit = [w for cl in re.split(r'[;:]|, (?=on the|in the middle|behind)', d) if c in OWN and re.search(OWN[c], cl) and not any(re.search(OWN[o], cl) for o in OWN if o != c) for w in re.findall(CLOTH.get(c, r'^$'), cl)]
        if hit:
            add(tid, '衣着', '%s 的描述里出现和定稿冲突的衣着词：%s（定稿：%s）' % (looks.NAME[c], hit, looks.LOOK[c].split('穿')[-1][:30]))
    # 5 人数
    n_real = len(chars) + len(others) + extras
    for m in re.finditer(r'exactly (\w+) (?:young men|people|persons|students|men)', d):
        n = WORDNUM.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else None)
        if n is not None and n != n_real: add(tid, '人数', '描述写「exactly %s」，白模实际入画 %d 人（主角%d+边缘%d+路人%d）' % (m.group(1), n_real, len(chars), len(others), extras))
    if 'one person only' in d and n_real > 1: add(tid, '人数', '描述写「one person only」，白模实际入画 %d 人' % n_real)
    # 6 台词：说话人必须在画面里且脸看得见，否则提示词里「嘴唇在动」会让别人张嘴（口型对不上的根源之一）
    for v in r.get('lines', []):
        c = NAME2CID.get(v['speaker'])
        if c and c not in onscreen: add(tid, '台词', '%s 说台词但不在画面里（画外音）：提示词要写成画外音，不能写嘴唇在动' % v['speaker'])
        elif c and fv is not None and c not in fv and c not in r.get('face_hidden', []) and not re.search(r'\bturns\b|lifts his head|looks up|turning his face', d): add(tid, '台词', '%s 说台词但白模第一帧看不到他的脸（背影/低头）：确认中途会转过来，否则按画外音处理' % v['speaker'])
    # 7 否定写法（H3 没有负面分支，否定词常被当成要画的东西）
    for c in onscreen:
        if re.search(NEG, looks.LOOK_EN.get(c, '').lower()): add(tid, '否定', '%s 的英文外貌里有否定词：%s' % (looks.NAME[c], re.findall(NEG, looks.LOOK_EN[c].lower())))
    if re.search(NEG, d): add(tid, '否定', '描述里有否定词：%s' % re.findall(NEG, d))
    # 9 沿用上一镜描述（踩坑 72：节拍没有英文描述就沿用上一条，动作/情绪对不上）
    prev = rows[rows.index(r) - 1] if rows.index(r) > 0 else None
    if prev and prev['segment'] == r['segment'] and prev['beat_en'] == desc and prev['act_zh'] != r['act_zh']:
        add(tid, '沿用', '画面描述和上一镜 %s 完全相同，但剧情动作不同：要按本镜动作重写' % prev['id'])
    # 10 剧情在说话却没有台词（踩坑 72：提示词会写成「没人说话、嘴唇闭着」，口型对不上）
    acts = ' '.join(r['act_zh'])
    if not r.get('lines') and re.search('说话|开口|问|回答|大喊|念|嘀咕|附和|招呼|说了一句|说完', re.sub('没有说话|没说话|说话的|不说话', '', acts)) and onscreen:
        add(tid, '台词', '剧情里有人在说话，但这个镜头没有台词数据（lines.json）：查 shot_audio.py')
    # 11 写了看得见脸，白模第一帧却看不到（背影、肩后、手机特写）
    if fv is not None and chars and not (set(chars) & set(fv)) and re.search(r'face (clearly )?visible|face and mouth', d) and not re.search(r'turns|lifts his head|looks up', d):
        add(tid, '朝向', '描述写了脸看得见，但白模第一帧主角看不到脸，且描述里没有转身/抬头的动作')
    if fv is not None and chars and not fv and re.search(r'\bscreen\b', d) is None and re.search(r'smug grin|smil|grin|laugh', d) and 'from behind' not in d and 'over-the-shoulder' not in d:
        add(tid, '朝向', '白模第一帧看不到任何人的脸，描述却写表情（笑等）：确认是不是背影/手机特写镜头')
    # 8 kf_hint 也查一遍时间
    kh = r.get('kf_prefix_zh', '')
    if st in DAY and re.search('夜|黄昏|傍晚|天黑', kh.replace(lighting.zh(st), '')): add(tid, '时间', '首帧提示（kf_hint）在白天场景里写了夜晚/黄昏')
    if st in NIGHT | DUSK and re.search('阳光|白天|晨光|蓝天', kh.replace(lighting.zh(st), '')): add(tid, '时间', '首帧提示（kf_hint）在傍晚/夜里场景写了白天')

kinds = {}
for tid, L in issues.items():
    for k, _ in L: kinds[k] = kinds.get(k, 0) + 1
md = ['# 全片提示词自动审查报告', '', '共 %d 个镜头，%d 个有提示：' % (len(rows), len(issues)) + '，'.join('%s %d 条' % kv for kv in sorted(kinds.items())), '']
for r in rows:
    if r['id'] not in issues: continue
    md += ['## %s（%s，人物 %s / 边缘 %s / 路人 %d）' % (r['id'], r['set'], ','.join(r['characters']) or '无', ','.join(r.get('others', [])) or '无', r.get('extras', 0) or 0),
           '- 剧情：' + ' / '.join(r['act_zh']), '- 描述：' + r['beat_en']]
    md += ['- **[%s]** %s' % kv for kv in issues[r['id']]] + ['']
open(os.path.join(P, '审查报告.md'), 'w', encoding='utf-8').write('\n'.join(md))
print('有提示的镜头 %d 个：' % len(issues), kinds)
