# -*- coding: utf-8 -*-
"""MiniMax H3 视频提示词生成器（可复用资产，2026-11-27）。
严格按 MiniMax 官方《Video Prompt Writing Guide (T2VA / I2VA / FL2VA / L2VA)》写（原文存档 docs/prompts/_official/），要点：
  1. 首帧模式（I2VA）第一行固定为对齐句，空一行后写三个字段：integrated_multimodal_description / overall_soundscape / non_diegetic_music
  2. [Shot 1] 开头先交代风格和初始构图（Live-action, cinematic, 景别…），再按「首帧状态 → 动作开始 → 连续发展 → 结果或反应」写动作
  3. 运镜 = 运动类型 + 幅度 + 速度，用官方词表，写成句子里的自然动作，不要堆标签
  4. 说话人用 (S1)(S2) 固定编号，台词放 <d>[语言] 原话</d>，说话人特征和语气写在标签外；不说话的人不编号
  5. 不写负面提示词（H3 用 BasicGuider、cfg 1，没有负面分支），想要什么就正面写出来
  6. 全英文；画面里的中文字原样放英文双引号里
白模动作控制（ControlNet）负责「人在哪、怎么动、镜头怎么走」，提示词负责「这是谁、在做什么、什么情绪、什么质感、什么声音」，两者不能矛盾。
用法：import h3_prompt; h3_prompt.build(task, mode='i2va', lines=voice_json, speech=False) → 字符串"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from looks import LOOK_EN

ALIGN = {   # 官方固定对齐句（逐字照抄）
    'i2va': 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.',
    't2va': '',
}

# 白模机位的运镜类型 → 官方运镜词表（类型 + 幅度 + 速度）。实际轨迹由白模深度控制视频决定，这里只让文字和控制一致
CAMERA = {
    'static': 'The camera holds a static shot',
    'push': 'The camera pushes in with small amplitude at slow speed toward {focus}',
    'arc': 'The camera moves in an arc shot around {focus} with small amplitude at slow speed',
    'track': 'A tracking shot follows {focus} at walking pace, keeping the framing steady',
    'hand': 'The handheld camera shakes slightly, staying close on {focus}',
}

# 景别关键词（从节拍描述里认），没认出来就按 medium shot
SHOT_SIZE = [('extreme close-up', 'an extreme close-up'), ('close-up', 'a close-up'), ('medium close-up', 'a medium close-up'),
             ('medium wide', 'a medium-wide shot'), ('wide establishing', 'a wide establishing shot'), ('wide shot', 'a wide shot'),
             ('medium shot', 'a medium shot'), ('high-angle', 'a high-angle shot'), ('over-the-shoulder', 'an over-the-shoulder shot')]

# 各场景的环境音（overall_soundscape，1～4 句英文）
SOUND = {
    'dorm': 'Quiet dormitory room tone with a faint computer fan and occasional distant footsteps in the corridor. Fabric rustles softly as people move, and chairs creak lightly.',
    'dorm_nt': 'A quiet dormitory at night: low room tone, the faint hum of a desk lamp, distant muffled voices from the corridor, and soft breathing.',
    'lib': 'The hushed room tone of a large library, pages turning nearby, a pen scratching on paper and the soft scrape of a chair on the floor.',
    'canteen': 'A busy university canteen: overlapping distant chatter, trays and chopsticks clinking, food being served at the counter.',
    'class': 'A small meeting room with faint ventilation hum, chairs shifting on the floor and the low murmur of a few students.',
    'outdoor_day': 'An open campus in daylight with light wind through the trees, birds, distant footsteps and bicycles passing.',
    'outdoor_night': 'A campus sports field at night with a light breeze, distant traffic, faint footsteps on the running track and insects chirping.',
    'home': 'A quiet apartment living room with a ticking clock and faint street noise outside the window.',
    'corridor': 'A tiled corridor with echoing footsteps and a distant door closing.',
}
SET_SOUND = {   # 场景（segments.py 的 set_name）→ 环境音
    'dorm_am': 'dorm', 'dorm_pm': 'dorm', 'dorm_dusk': 'dorm_nt', 'dorm_nt': 'dorm_nt', 'lib': 'lib', 'libdoor': 'lib', 'ext_library': 'outdoor_day',
    'canteen': 'canteen', 'ext_canteen': 'outdoor_day', 'class': 'class', 'ext_corridor': 'corridor', 'track': 'outdoor_night', 'ext_dusk': 'outdoor_night',
    'lawn': 'outdoor_day', 'home': 'home', 'home_nt': 'home', 'ext_dorm_am': 'outdoor_day', 'ext_dorm_pm': 'outdoor_day', 'ext_dorm_nt': 'outdoor_night'}
_SEG = None
def sound_of(task):
    global _SEG
    if _SEG is None:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import segments as S
            _SEG = {sid: st for sid, _, st, _ in S.segments()}
        except Exception:
            _SEG = {}
    st = task.get('set') or _SEG.get(task.get('segment', ''), '')
    return SOUND[SET_SOUND.get(st, 'dorm')]

# 说话人的声音特征（官方：第一次出场要交代年龄、性别、音高、音色、语速）
VOICE = {
    'lin': 'a 20-year-old young man with a slightly soft, round voice and a natural conversational pace',
    'chen': 'a calm 21-year-old young man with a clear, steady mid-pitched voice',
    'zhou': 'a gentle 22-year-old young man with a low, warm voice and an unhurried pace',
    'wang': 'a middle-aged male teacher with a warm, measured voice',
    'mom': 'a middle-aged woman with a bright, affectionate voice',
    'classA': 'a lively young man with a quick, bright voice',
    'classB': 'a young woman with a soft, slightly hesitant voice',
}
NAME2CID = {'林晓': 'lin', '陈瑶': 'chen', '周明远': 'zhou', '王老师': 'wang', '林母': 'mom', '同学甲': 'classA', '同学乙': 'classB'}

# 让动作像真人的正面描述（不写「不要什么」）
LIFE = ('Everyone moves with natural human timing: small breathing movements, occasional blinks, subtle weight shifts and relaxed hands; '
        'clothing folds and hair move naturally with each motion.')
QUALITY = 'Natural skin texture, true-to-life colors, soft realistic lighting consistent with the scene, shallow depth of field.'

def who_short(cid):   # 人物身份短语：只取外貌描述的第一小句（性别、年龄、体型），完整外貌由首帧提供（官方：I2VA 不重复描述外貌）
    s = LOOK_EN.get(cid, '')
    return s.split(' with ')[0] if s else ''

def size_of(desc):
    d = desc.lower()
    for k, v in SHOT_SIZE:
        if d.startswith(k) or (', ' + k) in d[:40]: return v
    return 'a medium shot'

def build(task, mode='i2va', lines=None, speech=False):
    desc = task.get('prompt', '').split('. Background:')[0].strip().rstrip('.')
    bg = task.get('prompt', '').split('. Background:')[1].split('.')[0].strip() if '. Background:' in task.get('prompt', '') else ''
    chars = task.get('characters', [])
    people = ', '.join(who_short(c) for c in chars if who_short(c))
    focus = 'the characters' if len(chars) > 1 else ('him' if chars else 'the scene')
    cam = CAMERA.get(task.get('move', 'static'), CAMERA['static']).format(focus=focus)
    if mode == 'i2va':
        keep = ('The people shown in <Picture 1> (%s) remain in the positions and framing established by <Picture 1>, preserving their faces, hairstyles, clothing, body shapes, '
                'the room layout, props and lighting. ' % people) if chars else 'The scene shown in <Picture 1> keeps its layout, objects and lighting. '
    else:
        keep = ('People: %s. ' % people) if people else ''
    shot = '[Shot 1] Live-action, cinematic, %s. %s%s. %s, matching the camera movement of the scene. %s' % (
        size_of(desc), keep, desc[0].upper() + desc[1:], cam, LIFE)
    # 画面里出现但不是主角的人（只露背影、肩膀、画面边缘）也要写清是谁：11-27 试片 0260 林晓背影没写进提示词，被画成长发、像女生
    others = [c for c in task.get('others', []) if c not in chars and LOOK_EN.get(c)]
    if others:
        shot += ' Also in <Picture 1>, partly visible at the edge of the frame: %s; %s the same person, with the same hair and clothing, for the whole shot.' % (
            '; '.join(LOOK_EN[c] for c in others),
            'each stays' if len(others) > 1 else ('she stays' if others[0] in ('mom', 'classB') else 'he stays'))
        shot += ' The shot contains exactly %d people.' % (len(chars) + len(others))
    # 首帧模式：背景只认首帧，不再用文字描述场景（11-27 试片教训：近景首帧只有白墙，文字写了「宿舍、上下铺、黄昏窗户」，模型中途把背景整个换成宿舍还镜像重复）
    if mode == 'i2va':
        shot += (' The background stays exactly as seen in <Picture 1> for the whole shot, softly out of focus, with the same walls, objects and light; '
                 'the space behind %s keeps its look as the camera moves.' % focus)
    elif bg:
        shot += ' Setting: %s.' % bg
    talk = ''
    if lines:
        seen = {}
        for v in lines:
            cid = NAME2CID.get(v.get('speaker'), '')
            if cid not in seen: seen[cid] = 'S%d' % (len(seen) + 1)
            sid = seen[cid]
            first = list(seen).index(cid) == len(seen) - 1 and sum(1 for x in lines[:lines.index(v)] if NAME2CID.get(x.get('speaker')) == cid) == 0
            voice = VOICE.get(cid, 'the speaker')
            if speech:
                talk += ' At about %.1f seconds, %s (%s) says with realistic lip articulation and no exaggerated mouth opening: <d>[Chinese] %s</d>' % (
                    v['start'], voice if first else 'he' if cid not in ('mom', 'classB') else 'she', sid, v['text'])
            else:
                talk += ' At about %.1f seconds %s (%s) starts speaking naturally, lips moving with realistic articulation, for about %.0f seconds.' % (
                    v['start'], voice if first else 'the same speaker', sid, v['dur'])
    elif chars:
        talk = ' Nobody speaks in this shot; lips stay relaxed and closed except for natural breathing.'
    body = 'integrated_multimodal_description: %s%s %s\n\noverall_soundscape: %s\n\nnon_diegetic_music: N/A' % (shot, talk, QUALITY, sound_of(task))
    head = ALIGN.get(mode, '')
    return (head + '\n\n' + body) if head else body

if __name__ == '__main__':   # 本地预览：python cloud/h3_prompt.py <任务id> [--speech]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tid = sys.argv[1]; td = os.path.join(root, 'dist', 'cloud_pack', tid)
    task = json.load(open(os.path.join(td, 'task.json'), encoding='utf-8'))
    vj = os.path.join(td, 'voice.json'); lines = json.load(open(vj, encoding='utf-8')) if os.path.exists(vj) else None
    print(build(task, 'i2va', lines, '--speech' in sys.argv))
