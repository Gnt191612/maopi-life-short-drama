# -*- coding: utf-8 -*-
"""v11 走位表：每场戏的角色初始状态 + 每拍的变化（未列出的角色/属性沿用上一拍，保证连续）。
状态字段：at=场景站位点名（来自 sets.py marks）或 pos=(x,y,z)；face=朝向°（0 面向 -Y，90 面向 +X，180 面向 +Y，-90 面向 -X）；
         base=下半身（stand/sit/sit_bed/lie/crouch/slump/hug_knees）；arms=手臂叠加（见 poses.ARMS）；reach=伸手指向的世界点。
变化：('set', {...}) 拍开头即新状态（换机位的“片刻之后”）；('blend', {...}, 秒) 在若干秒内过渡；('walk', {...}) 走过去（动作捕捉）。
init_<地点>：该场戏中某个地点片段（回忆、电话另一端）的初始状态。phones：手机放下时的位置。
"""
S = lambda **k: ('set', k)
Bl = lambda t=0.8, **k: ('blend', k, t)
Wk = lambda **k: ('walk', k)

SCN = {
 # ---------------- 第一幕 · 清晨宿舍 ----------------
 's01': dict(side=1,
   init={'lin': dict(at='lin_bed', face=180, base='lie', arms='down'),
         'chen': dict(at='chen_desk_seat', base='sit', arms='desk')},
   phones={'lin': (-1.22, -1.40, 1.93), 'chen': (1.35, -0.2, 0.76)},
   beats={
    's01_02': {'lin': Bl(1.6, arms='phone_up')},
    's01_06': {'lin': Bl(0.35, base='sit_bed', arms='phone')},
    's01_07': {'lin': Bl(2.4, at='lin_ladder_foot', base='stand', arms='down')},
    's01_07b': {'lin': S(at='lin_ladder_foot', base='stand', arms='down')},
    's01_08': {'lin': Wk(at='sink', arms='down')},
    's01_09': {'lin': S(at='sink', arms='brush')},
    's01_10': {'lin': Wk(at='window', face=-90, arms='down')},
    's01_11': {'lin': S(at='window', face=-90, arms='selfie')},
    's01_12': {'lin': S(arms='phone2')},
    's01_14': {'chen': Bl(1.0, pos=(0.55, -0.35, 0), face=180, base='stand', arms='backpack')},
    's01_15': {'chen': Wk(at='door', face=180, arms='backpack')},
    's01_16': {'chen': Wk(pos=(1.0, -3.6, 0), face=0, arms='backpack')},
   }),
 # ---------------- 图书馆 ----------------
 's02': dict(side=-1,
   init={'chen': dict(pos=(-2.6, -4.3, 0), face=180, base='sit', arms='desk'),
         'lin': dict(at='entrance', face=180, base='stand', arms='tray'),
         'zhou': dict(pos=(-4.4, 4.3, 0), face=0, base='sit', arms='desk')},          # 角落里埋头刷题的学长
   extras={'lib': ['周明远']},
   phones={'lin': (6.2, -0.2, 0.76)},
   beats={
    's02_01': {'lin': Wk(pos=(-4.2, -2.9, 0), face=150, arms='tray')},
    's02_02': {'chen': S(arms='wave')},
    's02_03': {'lin': S(face=-60, arms='gesture'), 'chen': S(arms='desk')},
    's02_04': {'lin': Wk(pos=(5.6, -0.9, 0), face=150, arms='tray')},
    's02_05': {'lin': S(pos=(5.7, -0.9, 0), face=120, arms='down')},
    's02_06': {'lin': S(pos=(6.0, -0.75, 0), face=180, arms='desk')},
    's02_07': {'lin': S(pos=(5.9, -1.2, 0), face=160, base='crouch', arms='phone')},
    's02_08': {'chen': S(arms='desk')},
    's02_08c': {'lin': S(pos=(-1.95, -4.25, 0), face=-90, base='crouch', arms='down')},
    's02_09': {'lin': S(at='window_seat', face=180, base='sit', arms='phone')},
   }),
 # ---------------- 午后宿舍 / 视频电话 ----------------
 's03': dict(side=1,
   init={'lin': dict(at='lin_bed', face=180, base='lie', arms='phone_up')},
   init_home={'mom': dict(at='sofa_seat', face=180, base='sit', arms='phone')},
   phones={'lin': (-1.30, -0.2, 0.76)},
   beats={
    's03_02': {'lin': Bl(1.2, base='sit_bed', arms='phone')},
    's03_03': {'lin': S(at='lin_desk_seat', base='sit', arms='desk')},
    's03_04': {'lin': Bl(0.8, arms='phone')},
    's03_08': {'lin': Bl(1.2, base='slump', arms='face_hands')},
   }),
 # ---------------- 第二幕 · 图书馆门口 ----------------
 's04': dict(side=1,
   init={'lin': dict(pos=(0.0, -2.0, 0), face=180, base='stand', arms='backpack')},
   phones={'lin': (0, -50, -5)},
   beats={
    's04_01': {'lin': Wk(pos=(0.2, 7.0, 1.2), face=180, arms='backpack')},
    's04_03': {'lin': S(face=180, arms='down')},
    's04_04': {'lin': Wk(pos=(0.8, 5.0, 0.74), face=0, base='sit', arms='phone')},
    's04_05': {'lin': S(arms='phone')},
    's04_06': {'lin': S(arms='phone2')},
   }),
 # ---------------- 食堂 ----------------
 's05': dict(side=-1,
   init={'lin': dict(at='queue', face=180, base='stand', arms='tray'),
         'classA': dict(pos=(-3.0, 3.0, 0), face=60, base='stand', arms='tray'),
         'classB': dict(at='classB_seat', face=180, base='sit', arms='desk'),
         'zhou': dict(pos=(0.15, 3.9, 0), face=180, base='stand', arms='tray')},       # 排在后面，目睹这一幕
   extras={'canteen': ['同学甲', '同学乙', '周明远']},
   phones={'lin': (0, -50, -5)},
   beats={
    's05_01': {'lin': S(arms='phone')},
    's05_03': {'classA': Wk(pos=(-0.6, 5.2, 0), face=90, arms='pat', reach=(0.0, 5.4, 1.45)), 'lin': S(face=-90, arms='phone')},
    's05_04': {'classB': S(arms='cover_face')},
    's05_05': {'lin': S(arms='down')},
    's05_06': {'lin': Wk(at='exit', arms='phone'), 'classA': S(arms='tray', reach=None)},
   }),
 # ---------------- 傍晚宿舍 ----------------
 's06': dict(side=1,
   init={'lin': dict(at='lin_desk_seat', base='slump', arms='face_hands'),
         'chen': dict(pos=(1.0, -2.6, 0), face=180, base='stand', arms='backpack')},
   phones={'lin': (-1.30, -0.1, 0.76)},
   beats={
    's06_02': {'chen': Wk(pos=(0.3, -0.9, 0), face=90, arms='cup')},
    's06_03': {'chen': S(pos=(-0.35, -0.6, 0), face=-90, arms='cup', reach=(-1.25, -0.45, 0.80))},
    's06_04': {'chen': S(pos=(-0.15, -0.05, 0), face=-120, base='sit', arms='gesture', reach=None)},
    's06_05': {'lin': Bl(0.8, base='sit', arms='desk')},
    's06_07': {'lin': S(arms='cover_face'), 'chen': S(arms='pat', reach=(-0.85, -0.35, 1.25))},
    's06_08': {'lin': Bl(1.0, arms='phone'), 'chen': S(arms='down', reach=None)},
   }),
 # ---------------- 第三幕 · 夜晚操场（含回忆） ----------------
 's07': dict(side=1,
   init={'lin': dict(pos=(-12, -2.6, 0), face=90, base='stand', arms='down'),
         'zhou': dict(pos=(-12, -3.4, 0), face=90, base='stand', arms='pocket')},
   init_dorm_nt={'zhou': dict(at='other2_bed', face=180, base='hug_knees', arms='knees')},
   init_dorm_am={'zhou': dict(at='door', face=0, base='stand', arms='cup')},
   phones={'lin': (0, -50, -5), 'zhou': (1.0, 1.0, 1.95)},
   beats={
    's07_01': {'lin': Wk(pos=(-8, -2.6, 0), face=90), 'zhou': Wk(pos=(-8, -3.4, 0), face=90, arms='pocket')},
    's07_02': {'lin': Wk(pos=(-6, -2.6, 0), face=90), 'zhou': Wk(pos=(-6, -3.4, 0), face=90, arms='pocket')},
    's07_04': {'zhou': S(face=180, arms='gesture'), 'lin': S(face=0)},
    's07_10': {'zhou': S(at='other2_bed', face=180, base='sit_bed', arms='phone2')},
    's07_12': {'zhou': S(arms='down')},
    's07_14': {'zhou': S(arms='gesture')},
    's07_17': {'zhou': S(arms='pat', reach=(-6.0, -2.75, 1.45))},
    's07_18': {'zhou': S(arms='pocket', reach=None)},
    's07_19': {'zhou': Wk(pos=(-3.5, -3.4, 0), face=-90, arms='pocket')},
   }),
 # ---------------- 第四幕 · 茶话会 ----------------
 's08': dict(side=-1,
   init={'wang': dict(pos=(0, -0.3, 0), face=0, base='stand', arms='gesture'),
         'lin': dict(at='lin_seat', base='sit', arms='desk'), 'chen': dict(at='chen_seat', base='sit', arms='desk'),
         'zhou': dict(at='zhou_seat', base='sit', arms='desk'), 'classA': dict(at='classA_seat', base='sit', arms='desk'),
         'classB': dict(at='classB_seat', base='sit', arms='desk')},
   extras={'class': ['林晓', '陈瑶', '周明远', '王老师', '同学甲', '同学乙']},
   phones={},
   beats={
    's08_03': {'wang': Wk(at='wang_seat', base='sit', arms='gesture')},
    's08_06': {'classA': S(arms='gesture')},
    's08_07': {'classA': S(arms='desk'), 'classB': S(arms='cover_face')},
    's08_08': {'classB': S(arms='desk'), 'chen': Bl(0.8, base='stand', arms='gesture')},
    's08_13': {'lin': Bl(0.9, base='stand', arms='down')},
    's08_16': {'chen': S(arms='clap'), 'zhou': S(arms='clap'), 'classA': S(arms='clap'), 'classB': S(arms='clap'), 'wang': S(arms='clap')},
   }),
 # ---------------- 第五幕 · 深夜宿舍 / 给妈妈打电话 ----------------
 's09': dict(side=1,
   init={'lin': dict(at='lin_desk_seat', base='sit', arms='selfie'),
         'chen': dict(at='chen_bed', face=180, base='sit_bed', arms='phone')},
   init_home_nt={'mom': dict(at='sofa_seat', face=180, base='sit', arms='phone_ear')},
   phones={'lin': (-1.30, -0.1, 0.76)},
   beats={
    's09_03': {'lin': S(arms='phone2')},
    's09_04': {'lin': Bl(0.5, arms='desk')},
    's09_06': {'lin': S(face=60, arms='phone')},
    's09_08': {'lin': S(face=90, arms='phone')},
    's09_09': {'lin': Bl(1.5, arms='phone_ear')},
   }),
 # ---------------- 尾声 · 草坪 ----------------
 's10': dict(side=1,
   init={'lin': dict(pos=(0, 0, 0), face=0, base='stand', arms='selfie'),
         'chen': dict(pos=(-0.9, 0.3, 0), face=20, base='stand', arms='down'),
         'zhou': dict(pos=(1.0, 0.4, 0), face=-20, base='stand', arms='pocket')},
   phones={},
   beats={
    's10_02': {'chen': S(pos=(-0.55, 0.1, 0), face=60, arms='pat', reach=(-0.1, -0.35, 1.35))},
    's10_03': {'zhou': S(pos=(0.6, 0.15, 0), face=-30, arms='gesture')},
    's10_04b': {'zhou': S(arms='phone')},
    's10_04c': {'zhou': S(arms='down')},
    's10_05': {'chen': S(pos=(-0.45, 0, 0), face=0, arms='down', reach=None), 'lin': S(arms='selfie'), 'zhou': S(pos=(0.45, 0, 0), face=0, arms='down')},
    's10_05b': {'lin': S(arms='phone')},
    's10_06': {'lin': S(arms='down')},
    's10_07': {'lin': Wk(pos=(0, 12, 0), face=180), 'chen': Wk(pos=(-0.5, 12, 0), face=180), 'zhou': Wk(pos=(0.5, 12, 0), face=180)},
   }),
}

def get(scene_id):
    return SCN.get(scene_id, dict(side=1, init={}, beats={}, phones={}))

def resolve(st, marks):
    """把 at/face 换算成 pos/yaw（之后从状态中移除，避免下一拍误继承）"""
    if st.get('at'):
        m = marks[st['at']]; st['pos'] = (m[0], m[1], m[2]); st['yaw'] = m[3]
    if st.get('face') is not None: st['yaw'] = st['face']
    st.pop('at', None); st.pop('face', None)
    st.setdefault('pos', (0, 0, 0)); st.setdefault('yaw', 0); st.setdefault('base', 'stand'); st.setdefault('arms', 'down')
    if 'reach' in st and st['reach'] is None: st.pop('reach')
    return st

def with_look(st, look):
    s = dict(st); s['look'] = look; return s
