# -*- coding: utf-8 -*-
"""「活人感」层：叠加在姿态/动捕动画之上的细微运动，解决白模动作僵硬。
  - 呼吸：胸椎、锁骨随 ~4 秒一次的呼吸轻微起伏
  - 微动：躯干、头颈、上臂的低频噪声（真人站着/坐着从不完全静止）
  - 眨眼：每 2~6 秒一次，偶尔连眨两下；眼球不时轻微扫视
  - 手指：放松时自然微屈，拿手机时握住（白模原本五指笔直，最显僵硬）
骨骼轴向由 tests 实测：上眼睑 orbicularis03 绕局部 X 负向转 = 闭眼；手指绕局部 X 正向转 = 向掌心弯曲。
"""
import math, random
import bpy

FPS = 24
FINGERS = ['finger%d-%d.%s' % (i, j, s) for s in 'LR' for i in range(2, 6) for j in range(1, 4)]
THUMB = ['finger1-%d.%s' % (j, s) for s in 'LR' for j in range(1, 4)]
# (骨骼, 噪声强度[四元数分量], 噪声周期[帧]) —— 强度 0.01 ≈ 1.1°
# 2026-11-23 幅度整体加大约一倍：原来 ±1° 左右，白模几乎是定住的，看着僵（云端按骨架图生成，僵硬会带进成片）
SWAY = [('spine04', 0.012, 75), ('spine02', 0.015, 64), ('neck02', 0.018, 52), ('head', 0.028, 44),
        ('clavicle.L', 0.010, 58), ('clavicle.R', 0.010, 58), ('upperarm01.L', 0.020, 68), ('upperarm01.R', 0.020, 68),
        ('lowerarm01.L', 0.016, 60), ('lowerarm01.R', 0.016, 60)]
BREATH = [('spine03', 0.010), ('spine01', 0.006), ('clavicle.L', 0.005), ('clavicle.R', 0.005)]

def _fcurves(rig, bone, path='rotation_quaternion'):
    act = rig.animation_data.action
    dp = 'pose.bones["%s"].%s' % (bone, path)
    return [fc for fc in act.fcurves if fc.data_path == dp]

def add_idle(rig, seed):
    """给已有关键帧的骨骼叠加呼吸与微动（F 曲线修改器：不改动原关键帧，任何姿态/走路都适用）"""
    rnd = random.Random(seed)
    for bone, strength, scale in SWAY:
        for fc in _fcurves(rig, bone):
            if fc.array_index == 0: continue          # 只扰动 x/y/z 分量（w 分量保持，Blender 会自动归一化）
            m = fc.modifiers.new('NOISE'); m.blend_type = 'ADD'
            m.scale = scale * rnd.uniform(0.8, 1.25); m.strength = strength * 2; m.phase = rnd.uniform(0, 1000)
    period = FPS * rnd.uniform(3.6, 4.6)               # 每人呼吸节奏略有不同
    for bone, amp in BREATH:
        for fc in _fcurves(rig, bone):
            if fc.array_index != 1: continue           # 绕局部 X：挺胸/含胸
            m = fc.modifiers.new('FNGENERATOR'); m.function_type = 'SIN'; m.use_additive = True
            m.amplitude = amp; m.phase_multiplier = 2 * math.pi / period; m.phase_offset = rnd.uniform(0, 6.28)
    ph_shift = rnd.uniform(0, 6.28); per = FPS * rnd.uniform(7.0, 10.0)
    for bone, amp, idx in (('spine05', 0.012, 3), ('spine03', 0.008, 3), ('neck01', -0.008, 3)):   # 重心慢慢左右移：腰以上 7~10 秒一次轻微侧摆、头反向一点保持平衡（原来上身始终笔直对称，2026-11-23）
        for fc in _fcurves(rig, bone):
            if fc.array_index != idx: continue
            m = fc.modifiers.new('FNGENERATOR'); m.function_type = 'SIN'; m.use_additive = True
            m.amplitude = amp; m.phase_multiplier = 2 * math.pi / per; m.phase_offset = ph_shift

def inertia(rig):
    """惯性：手臂、头颈的每段过渡用「回弹」缓动——到位时略冲过头再回来（幅度与动作大小成正比，静止段不受影响）。
    逐帧的动捕走路关键帧每段只有 1 帧，整数帧上取值不变，不会抖。"""
    act = rig.animation_data.action
    for fc in act.fcurves:
        if not fc.data_path.endswith('rotation_quaternion'): continue
        bn = fc.data_path.split('"')[1]
        if any(k in bn for k in ('arm', 'clavicle', 'shoulder')): back = 1.4
        elif bn in ('head', 'neck01', 'neck02', 'neck03'): back = 0.9
        else: continue
        for kp in fc.keyframe_points:
            kp.interpolation = 'BACK'; kp.easing = 'EASE_OUT'; kp.back = back

def _key_rot(pb, frame, euler):
    pb.rotation_mode = 'XYZ'; pb.rotation_euler = euler
    if frame is not None: pb.keyframe_insert('rotation_euler', frame=frame, group=pb.name)   # frame=None：只摆姿势（静态展示图）

def blinks(rig, f0, f1, seed):
    """眨眼：闭 2 帧、睁 3 帧（约 0.2 秒，真人眨眼时长）"""
    rnd = random.Random(seed * 7 + 1); pb = rig.pose.bones
    lids = [pb[n] for n in ('orbicularis03.L', 'orbicularis03.R') if n in pb]
    if not lids: return
    for l in lids: _key_rot(l, f0, (0, 0, 0))
    f = f0 + rnd.randint(10, 60)
    while f < f1 - 6:
        for l in lids:
            _key_rot(l, f, (0, 0, 0)); _key_rot(l, f + 2, (math.radians(-27), 0, 0)); _key_rot(l, f + 5, (0, 0, 0))
        f += 6 if rnd.random() < 0.15 else rnd.randint(int(2.2 * FPS), int(5.5 * FPS))   # 偶尔连眨两下
    eyes = [pb[n] for n in ('eye.L', 'eye.R') if n in pb]
    f = f0
    while f < f1:                                       # 眼球扫视：每 1~3 秒换一个注视点，跳变 2 帧完成
        ex, ez = math.radians(rnd.uniform(-2.5, 2.5)), math.radians(rnd.uniform(-4, 4))
        for e in eyes:
            _key_rot(e, f, e.rotation_euler[:] if f > f0 else (0, 0, 0)); _key_rot(e, f + 2, (ex, 0, ez))
        f += rnd.randint(int(1.0 * FPS), int(3.0 * FPS))

def hands(rig, frame, grip_R=False, grip_L=False):
    """手指：放松微屈；拿手机的手握住"""
    pb = rig.pose.bones
    for n in FINGERS:
        if n not in pb: continue
        grip = grip_R if n.endswith('.R') else grip_L
        j = int(n.split('-')[1][0])
        deg = (48, 55, 35)[j - 1] if grip else (14, 20, 12)[j - 1]
        _key_rot(pb[n], frame, (math.radians(deg), 0, 0))
    for n in THUMB:
        if n not in pb: continue
        grip = grip_R if n.endswith('.R') else grip_L
        _key_rot(pb[n], frame, (math.radians(25 if grip else 8), 0, 0))

def talk_motion(rig, spans, seed):
    """说话时头和上身跟着动：每句台词期间叠加轻微点头（头、颈）和上身起伏（胸椎），句首稍重、句尾收住。
    原来说话只有嘴动，头和身子纹丝不动，看着像念稿（2026-11-23）。spans：[(起始帧, 结束帧), ...]"""
    rnd = random.Random(seed)
    for f0, f1 in spans:
        if f1 - f0 < 10: continue
        period = FPS * rnd.uniform(0.7, 1.1)             # 点头节奏约每秒一下，像说话的重音
        for bone, amp, idx in (('head', rnd.uniform(0.034, 0.052), 1), ('neck02', 0.018, 1), ('spine03', 0.012, 1),   # 点头约 4~6°（实测 0.022 时只有 2~3°，看不出来）
                                   ('head', rnd.uniform(0.008, 0.015), 2)):
            for fc in _fcurves(rig, bone):
                if fc.array_index != idx: continue      # 1 = 绕局部 X 点头/挺胸；2 = 绕骨骼自身 Y 轻微转头
                m = fc.modifiers.new('NOISE'); m.blend_type = 'ADD'   # 噪声而不是正弦：点头幅度、间隔都不规律（正弦像节拍器，2026-11-23 规则审查）
                m.scale = period * (1.6 if idx == 2 else 1.0) * 0.55; m.strength = amp * 2.4; m.phase = rnd.uniform(0, 1000)
                m.use_restricted_range = True; m.frame_start = f0; m.frame_end = f1
                m.blend_in = min(8, (f1 - f0) // 3); m.blend_out = min(10, (f1 - f0) // 3)

def phone_motion(rig, hand_events, f_end, seed):
    """拿着手机时手不完全定住：手腕缓慢转动（看屏幕、划动）、前臂偶尔挪一下。原来躺着举手机看 7 秒一动不动（s03 林晓，2026-11-23）。
    hand_events：[(帧, (右手握, 左手握)), ...]（shoot 里的 hand_ev），握着的时段就是拿手机的时段"""
    rnd = random.Random(seed)
    ev = sorted(hand_events)
    for side_i, side in ((0, 'R'), (1, 'L')):
        spans, start = [], None
        for fr, grips in ev:
            g = grips[side_i]
            if g and start is None: start = fr
            elif not g and start is not None: spans.append((start, fr)); start = None
        if start is not None: spans.append((start, f_end))
        for f0, f1 in spans:
            if f1 - f0 < 24: continue
            for bone, amp, per, idx in (('wrist.' + side, rnd.uniform(0.03, 0.045), rnd.uniform(1.8, 2.6), 1), ('wrist.' + side, 0.02, rnd.uniform(2.6, 3.4), 3),
                                        ('lowerarm01.' + side, rnd.uniform(0.015, 0.025), rnd.uniform(3.0, 4.2), 1)):
                for fc in _fcurves(rig, bone):
                    if fc.array_index != idx: continue
                    m = fc.modifiers.new('NOISE'); m.blend_type = 'ADD'   # 不规律的小动作（看屏幕、划一下）
                    m.scale = per * FPS * 0.5; m.strength = amp * 2.4; m.phase = rnd.uniform(0, 1000)
                    m.use_restricted_range = True; m.frame_start = f0; m.frame_end = f1; m.blend_in = 10; m.blend_out = 10

def wave(rig, f0, f1, seed, side='R'):
    """挥手：举起的前臂和手腕左右来回摆（约半秒一个来回）。原来手举起来定在那里 3 秒，像举手回答问题（s02 陈瑶，2026-11-23）"""
    if f1 - f0 < 12: return
    rnd = random.Random(seed); per = FPS * rnd.uniform(0.5, 0.65); ph = rnd.uniform(0, 6.28)
    for bone, amp, idx in (('lowerarm01.' + side, 0.16, 3), ('wrist.' + side, 0.10, 3)):
        for fc in _fcurves(rig, bone):
            if fc.array_index != idx: continue
            m = fc.modifiers.new('FNGENERATOR'); m.function_type = 'SIN'; m.use_additive = True
            m.amplitude = amp; m.phase_multiplier = 2 * math.pi / per; m.phase_offset = ph
            m.use_restricted_range = True; m.frame_start = f0; m.frame_end = f1; m.blend_in = 6; m.blend_out = 6
