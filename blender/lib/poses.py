# -*- coding: utf-8 -*-
"""姿态库：用「骨骼在身体坐标系中指向的方向」定义姿态，与骨骼局部轴无关。
身体坐标系：前 = -Y，角色左侧 = +X，上 = +Z（MPFB 角色静止时面朝 -Y）。
姿态 = 下半身基础（stand/sit/lie/sit_bed/crouch/slump/hug_knees）+ 手臂叠加（arms）+ 视线（look）。
apply_state() 把一个状态摆到骨架上并打关键帧；状态之间由 Blender 插值（或在 blocking 里插入走路动作捕捉）。
"""
import math
import bpy
from mathutils import Matrix, Quaternion, Vector, Euler

Y = Vector((0, 1, 0))
BODY = ['root', 'spine05', 'spine04', 'spine03', 'spine02', 'spine01', 'neck01', 'neck02', 'neck03', 'head',
        'pelvis.L', 'pelvis.R', 'upperleg01.L', 'upperleg02.L', 'lowerleg01.L', 'lowerleg02.L', 'foot.L',
        'upperleg01.R', 'upperleg02.R', 'lowerleg01.R', 'lowerleg02.R', 'foot.R',
        'clavicle.L', 'shoulder01.L', 'upperarm01.L', 'upperarm02.L', 'lowerarm01.L', 'lowerarm02.L', 'wrist.L',
        'clavicle.R', 'shoulder01.R', 'upperarm01.R', 'upperarm02.R', 'lowerarm01.R', 'lowerarm02.R', 'wrist.R']
SPINE = ['spine05', 'spine04', 'spine03', 'spine02', 'spine01']
NECK = ['neck01', 'neck02', 'neck03']

def V(x, y, z): return Vector((x, y, z)).normalized()
def mirror(d): return Vector((-d.x, d.y, d.z))

# ---- 下半身基础：根骨高度偏移(相对站立髋高, 米)、躯干俯仰(°, 正 = 身体向后仰倒)、各骨方向 ----
BASE = {
 'stand':  dict(dz=0.0, pitch=0, spine=V(0, 0, 1), uleg=V(0, 0, -1), lleg=V(0, 0, -1), foot=V(0, -1, -0.5)),
 'sit':    dict(dz=-0.42, pitch=0, spine=V(0, -0.08, 1), uleg=V(0.05, -1, 0.04), lleg=V(0, 0.12, -1), foot=V(0, -1, -0.3), seat=True),
 'sit_bed': dict(dz=-0.85, pitch=0, spine=V(0, 0.15, 1), uleg=V(0.06, -1, 0), lleg=V(0.03, -1, -0.05), foot=V(0, -0.2, 1)),
 'hug_knees': dict(dz=-0.85, pitch=0, spine=V(0, -0.35, 1), uleg=V(0.12, -0.6, 0.8), lleg=V(0.05, 0.25, -1), foot=V(0, -1, -0.2)),
 'lie':    dict(dz=-0.80, pitch=-90, spine=V(0, 0, 1), uleg=V(0, 0, -1), lleg=V(0, 0, -1), foot=V(0, -1, -0.3)),
 'crouch': dict(dz=-0.42, pitch=0, spine=V(0, -0.35, 1), uleg=V(0.12, -1, 0.35), lleg=V(0.04, 0.5, -1), foot=V(0, -1, -0.2)),
 'slump':  dict(dz=-0.42, pitch=0, spine=V(0, -1, 0.55), uleg=V(0.05, -1, 0.04), lleg=V(0, 0.12, -1), foot=V(0, -1, -0.3), head=V(0, -0.6, -0.8)),
}
# ---- 手臂叠加：右臂 (上臂, 前臂) 方向；左臂缺省 = 右臂镜像；None = 自然下垂 ----
DOWN_R = (V(-0.12, 0.02, -1), V(-0.05, -0.15, -1))
ARMS = {
 'down':       dict(R=DOWN_R),
 'phone':      dict(R=(V(-0.15, -0.35, -0.92), V(0.25, -0.75, 0.6)), L=DOWN_R, head=V(0, -0.4, 0.92), prop='hand'),          # 单手拿手机看
 'phone2':     dict(R=(V(-0.12, -0.3, -0.94), V(0.3, -0.85, 0.42)), head=V(0, -0.45, 0.9), prop='hand'),                       # 双手打字
 'phone_up':   dict(R=(V(-0.1, -0.45, 0.2), V(0.2, 0.1, 1)), L=(V(0.1, -0.45, 0.2), V(-0.2, 0.1, 1)), prop='hand'),          # 躺着举在脸上方
 'selfie':     dict(R=(V(-0.35, -0.85, 0.3), V(-0.15, -0.95, 0.25)), L=DOWN_R, prop='hand'),
 'phone_ear':  dict(R=(V(-0.55, -0.15, -0.8), V(0.25, 0.05, 1)), L=DOWN_R, prop='ear'),
 'brush':      dict(R=(V(-0.2, -0.5, -0.85), V(0.45, -0.45, 0.75)), L=(V(0.55, -0.15, 0.6), V(-0.35, 0.2, 0.9)), head=V(0, -0.25, 0.97)),
 'cover_face': dict(R=(V(-0.1, -0.55, -0.83), V(0.25, -0.35, 0.9)), head=V(0, -0.45, 0.89)),
 'wave':       dict(R=(V(-0.75, -0.1, 0.55), V(-0.15, -0.1, 1)), L=DOWN_R),
 'clap':       dict(R=(V(-0.1, -0.45, -0.88), V(0.55, -0.8, 0.25))),
 'desk':       dict(R=(V(-0.05, -0.5, -0.86), V(0.15, -1, 0.0))),                                                                 # 手放桌上
 'tray':       dict(R=(V(-0.08, -0.25, -0.96), V(0.12, -1, 0.05)), prop='tray'),
 'pocket':     dict(R=(V(-0.15, 0.15, -1), V(0.25, -0.25, -1))),
 'gesture':    dict(R=(V(-0.2, -0.3, -0.93), V(-0.05, -0.9, 0.45)), L=DOWN_R),                                                  # 说话时比划
 'pat':        dict(R=(V(-0.95, -0.15, -0.1), V(-0.98, -0.15, 0.1)), L=DOWN_R),                                                 # 拍旁边人肩膀（方向在 blocking 里按目标修正）
 'cup':        dict(R=(V(-0.1, -0.5, -0.86), V(0.1, -1, 0.1)), L=DOWN_R, prop='hand'),
 'backpack':   dict(R=(V(-0.05, 0.25, -0.97), V(-0.1, -0.3, 0.95)), L=DOWN_R),                                                  # 一手拽书包带
 'knees':      dict(R=(V(-0.2, -0.75, -0.6), V(0.6, -0.4, -0.2))),                                                              # 抱膝
 'face_hands': dict(R=(V(-0.15, -0.7, -0.7), V(0.35, -0.25, 0.9)), head=V(0, -0.6, 0.8)),                                       # 趴着/捂脸
}

def body_rot(yaw, pitch):
    return Euler((math.radians(pitch), 0, math.radians(yaw)), 'ZXY').to_quaternion()

def reset(rig):
    for n in BODY:
        pb = rig.pose.bones.get(n)
        if pb: pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    bpy.context.view_layer.update()

def aim(rig, name, wdir):
    """让骨骼 Y 轴指向世界方向 wdir（最小扭转）"""
    pb = rig.pose.bones.get(name)
    if pb is None: return
    W = rig.matrix_world @ pb.matrix
    q = (W.to_quaternion() @ Y).rotation_difference(wdir) @ W.to_quaternion()
    pb.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(W.translation, q, W.to_scale())
    bpy.context.view_layer.update()

def apply_state(rig, st, frame=None):
    """st: dict(pos=(x,y,z地面), yaw=°, base='stand', arms='down', look=Vector世界目标点或None, look_w=0.6)"""
    reset(rig)
    b = BASE[st.get('base', 'stand')]; a = ARMS[st.get('arms', 'down')]
    Rb = body_rot(st.get('yaw', 0), b['pitch'])
    root = rig.pose.bones['root']
    R0 = rig.matrix_world @ root.bone.matrix_local
    x, y, z = st.get('pos', (0, 0, 0))
    hip = R0.translation.z + b['dz'] + z
    root.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(Vector((x, y, hip)), Rb @ R0.to_quaternion(), R0.to_scale())
    bpy.context.view_layer.update()
    W = lambda d: Rb @ d
    for n in SPINE: aim(rig, n, W(b['spine']))
    head_d = a.get('head') or b.get('head') or V(0, -0.05, 1)
    for n in NECK: aim(rig, n, W((b['spine'] + head_d).normalized()))
    look = st.get('look')
    hd = W(head_d)
    if look is not None:   # 视线：头部转向目标点（按权重与姿态方向混合）
        hpos = (rig.matrix_world @ rig.pose.bones['head'].matrix).translation
        to = (Vector(look) - hpos).normalized(); w = st.get('look_w', 0.6)
        hd = (hd * (1 - w) + (to + Vector((0, 0, 0.9))).normalized() * w).normalized()
    aim(rig, 'head', hd)
    for side, mir in (('L', True), ('R', False)):
        aim(rig, 'upperleg01.' + side, W(mirror(b['uleg']) if mir else b['uleg'])); aim(rig, 'upperleg02.' + side, W(mirror(b['uleg']) if mir else b['uleg']))
        aim(rig, 'lowerleg01.' + side, W(mirror(b['lleg']) if mir else b['lleg'])); aim(rig, 'lowerleg02.' + side, W(mirror(b['lleg']) if mir else b['lleg']))
        aim(rig, 'foot.' + side, W(b['foot']))
        arm = a.get(side) or (tuple(mirror(d) for d in a['R']) if side == 'L' else a['R'])
        if side == 'L' and 'L' not in a: arm = tuple(mirror(d) for d in a['R'])
        ua, la = arm
        if st.get('reach') is not None and side == 'R':   # 伸手指向某个世界点（拍肩、放水杯）
            sp = (rig.matrix_world @ rig.pose.bones['upperarm01.R'].matrix).translation
            d = (Vector(st['reach']) - sp).normalized(); ua_w, la_w = d, d
        else:
            ua_w, la_w = W(ua), W(la)
        aim(rig, 'upperarm01.' + side, ua_w); aim(rig, 'upperarm02.' + side, ua_w)
        aim(rig, 'lowerarm01.' + side, la_w); aim(rig, 'lowerarm02.' + side, la_w)
    if frame is not None: key(rig, frame)

def key(rig, frame):
    for n in BODY:
        pb = rig.pose.bones.get(n)
        if pb is None: continue
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)
        if n == 'root': pb.keyframe_insert('location', frame=frame, group=n)

def head_pos(rig):
    return (rig.matrix_world @ rig.pose.bones['head'].matrix).translation.copy()

def hand_matrix(rig, side='R'):
    return rig.matrix_world @ rig.pose.bones['wrist.' + side].matrix
