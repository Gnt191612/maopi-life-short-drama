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
 'climbA': dict(dz=0.0, pitch=0, spine=V(0, -0.15, 1), uleg=V(0.05, -0.75, -0.65), lleg=V(0, 0.15, -1), foot=V(0, -1, -0.3),
                 ulegL=V(-0.04, -0.05, -1), llegL=V(0, 0.05, -1)),   # 爬梯：右膝抬到上一级横档，左腿伸直
 'climbB': dict(dz=0.0, pitch=0, spine=V(0, -0.15, 1), uleg=V(0.04, -0.05, -1), lleg=V(0, 0.05, -1), foot=V(0, -1, -0.3),
                 ulegL=V(-0.05, -0.75, -0.65), llegL=V(0, 0.15, -1)),
 'sit_lean':  dict(dz=-0.42, pitch=0, spine=V(0, -0.45, 1), uleg=V(0.12, -1, 0.04), lleg=V(0.04, 0.05, -1), foot=V(0, -1, -0.3), seat=True),   # 前倾坐（专注地听）
 'sit_back':  dict(dz=-0.42, pitch=0, spine=V(0, 0.22, 1), uleg=V(0.10, -1, 0.06), lleg=V(0.03, -0.35, -1), foot=V(0, -1, -0.2), seat=True),   # 后靠、腿往前伸（放松）
 'sit_tight': dict(dz=-0.42, pitch=0, spine=V(0, -0.12, 1), uleg=V(0.0, -1, 0.04), lleg=V(-0.02, 0.18, -1), foot=V(0, -1, -0.4), seat=True),  # 并腿拘谨坐
 # ---- 腿部变化 ----
 'sit_cross':  dict(dz=-0.42, pitch=0, spine=V(0, 0.05, 1), uleg=V(0.32, -1, 0.30), lleg=V(0.10, 0.30, -1), foot=V(0, -1, -0.1),
                    ulegL=V(-0.06, -1, 0.04), llegL=V(0, 0.10, -1), seat=True),   # 二郎腿：右腿搭在左腿上
 'sit_wide':   dict(dz=-0.42, pitch=0, spine=V(0, -0.05, 1), uleg=V(-0.38, -1, 0.04), lleg=V(-0.12, 0.10, -1), foot=V(0, -1, -0.3), seat=True),   # 分腿坐
 'sit_ankles': dict(dz=-0.42, pitch=0, spine=V(0, 0.08, 1), uleg=V(0.02, -1, 0.02), lleg=V(0.16, -0.45, -1), foot=V(0, -1, -0.2), seat=True),   # 腿前伸、脚踝交叉
 'stand_rest': dict(dz=-0.01, pitch=0, spine=V(0.03, 0, 1), uleg=V(0.03, 0.0, -1), lleg=V(0, 0, -1), foot=V(0, -1, -0.5),
                    ulegL=V(-0.07, -0.13, -1), llegL=V(0, 0.14, -1)),   # 重心落在一条腿上的放松站姿
 'rise':   dict(dz=-0.30, pitch=0, spine=V(0, -0.75, 1), uleg=V(0.08, -0.85, -0.4), lleg=V(0.03, 0.25, -1), foot=V(0, -1, -0.3),
               head=V(0, -0.2, 1)),   # 起身/坐下的中间姿态：上身前倾把重心移到脚上方、膝盖弯着发力
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
 'desk':       dict(R=(V(-0.05, -0.5, -0.86), V(0.15, -1, 0.0)), ik='desk'),                                                      # 手放桌上（IK：前臂实际落在桌面）
 'tray':       dict(R=(V(-0.08, -0.25, -0.96), V(0.12, -1, 0.05)), prop='tray'),
 'pocket':     dict(R=(V(-0.15, 0.15, -1), V(0.25, -0.25, -1))),
 'gesture':    dict(R=(V(-0.2, -0.3, -0.93), V(-0.05, -0.9, 0.45)), L=DOWN_R),                                                  # 说话时比划
 'pat':        dict(R=(V(-0.95, -0.15, -0.1), V(-0.98, -0.15, 0.1)), L=DOWN_R),                                                 # 拍旁边人肩膀（方向在 blocking 里按目标修正）
 'cup':        dict(R=(V(-0.1, -0.5, -0.86), V(0.1, -1, 0.1)), L=DOWN_R, prop='hand'),
 'backpack':   dict(R=(V(-0.05, 0.25, -0.97), V(-0.1, -0.3, 0.95)), L=DOWN_R),                                                  # 一手拽书包带
 'knees':      dict(R=(V(-0.2, -0.75, -0.6), V(0.6, -0.4, -0.2))),                                                              # 抱膝
 'lap':        dict(R=DOWN_R, ik='lap'),          # 坐着：双手交叠放在腿上（IK 落在大腿根部上方）
 'thighs':     dict(R=DOWN_R, ik='thighs'),       # 坐着：两手各搭在自己大腿上
 'push':       dict(R=DOWN_R, ik='push'),         # 起身发力：双手按在膝盖上方撑住
 'elbows_knees': dict(R=DOWN_R, ik='knees_fwd', head=V(0, -0.35, 0.94)),   # 身体前倾，手肘撑膝、双手相握
 # ---- 生活化手部动作：hand=手腕落点（身体部位 + 前/左/上 偏移，米），由 IK 摆臂；没写的那只手保持 R/L 方向姿态 ----
 'cross_arms':  dict(R=DOWN_R, hand={'R': ('chest', (0.17, 0.10, -0.13)), 'L': ('chest', (0.13, -0.12, -0.10))}),   # 抱臂
 'chin':        dict(R=DOWN_R, hand={'R': ('chin', (0.04, 0.0, -0.04)), 'L': ('chest', (0.15, -0.04, -0.17))}),    # 托下巴思考（另一只手托着手肘）
 'glasses':     dict(R=DOWN_R, hand={'R': ('eyes', (0.06, 0.0, 0.0))}),                                            # 推眼镜
 'scratch_head': dict(R=DOWN_R, hand={'R': ('crown', (-0.02, -0.07, 0.0))}),                                       # 挠头
 'neck_rub':    dict(R=DOWN_R, hand={'R': ('neck', (-0.08, -0.03, 0.03))}),                                        # 摸后脖颈（尴尬）
 'hands_back':  dict(R=DOWN_R, hand={'R': ('hip', (-0.19, -0.04, 0.03)), 'L': ('hip', (-0.19, 0.04, 0.05))}),      # 背着手
 'pockets':     dict(R=DOWN_R, hand={'R': ('hip', (0.06, -0.17, -0.09)), 'L': ('hip', (0.06, 0.17, -0.09))}),      # 双手插兜
 'pocket1':     dict(R=DOWN_R, hand={'R': ('hip', (0.06, -0.17, -0.09))}),                                          # 单手插兜
 'hip_hand':    dict(R=DOWN_R, hand={'R': ('hip', (0.0, -0.21, 0.07))}, pole='out'),                               # 单手叉腰
 'sleeves':     dict(R=DOWN_R, hand={'R': ('belly', (0.22, 0.03, 0.0)), 'L': ('belly', (0.22, -0.03, 0.02))}),     # 缩着袖子两手拢在身前
 'rub_hands':   dict(R=DOWN_R, hand={'R': ('chest', (0.26, 0.02, -0.12)), 'L': ('chest', (0.26, -0.02, -0.12))}), # 搓手
 'hand_chest':  dict(R=DOWN_R, hand={'R': ('chest', (0.11, 0.03, 0.0))}),                                         # 手按胸口（真诚）
 'open_palms':  dict(R=DOWN_R, hand={'R': ('belly', (0.30, -0.22, 0.06)), 'L': ('belly', (0.30, 0.22, 0.06))}),    # 摊开双手说话
 'hair_tuck':   dict(R=DOWN_R, hand={'R': ('ear', (0.0, 0.0, 0.01))}),                                             # 把头发别到耳后
 'strap':       dict(R=DOWN_R, hand={'R': ('chest', (0.06, -0.13, 0.08))}),                                        # 抓着书包带
 'climb':      dict(R=(V(-0.15, -0.55, 0.8), V(-0.05, -0.35, 1))),                                                             # 双手握梯子扶手
 'face_hands': dict(R=(V(-0.15, -0.7, -0.7), V(0.35, -0.25, 0.9)), head=V(0, -0.6, 0.8)),                                       # 趴着/捂脸
}

# ---- 支撑面：坐/躺时用射线找到真实的椅面/床面，按各人体型把臀部/后背放在面上（防止陷进床板、悬空） ----
SUPPORTED = {'sit': 'seat', 'slump': 'seat', 'sit_lean': 'seat', 'sit_back': 'seat', 'sit_tight': 'seat',
             'sit_cross': 'seat', 'sit_wide': 'seat', 'sit_ankles': 'seat', 'sit_bed': 'seat', 'hug_knees': 'seat', 'lie': 'back'}
SUPPORT_ON = True
LAST_SUPPORT = {}          # 角色 -> 正在坐/躺的家具名（机位避让时不许移走它）

SOFT = ('furn_quilt', 'furn_pillow', 'furn_blanket', 'furn_cushion')   # 软的：人会压进去/盖在身上，不当支撑面

def _is_person(obj):
    return (obj.type != 'MESH' or (obj.parent is not None and obj.parent.type == 'ARMATURE')
            or obj.name.startswith(SOFT))

def support_height(rig, x, y, z_hint):
    """从髋部上方往下打射线，跳过人物，返回 (支撑面高度, 家具名)；找不到返回 None"""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    o = Vector((x, y, z_hint + 0.6)); d = Vector((0, 0, -1)); t = 0
    while t < 2.5:
        hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + d * t, d, distance=2.5 - t)
        if not hit: return None
        if _is_person(obj) or obj.name.startswith('prop_'): t = (o - loc).length + 0.01; continue
        return loc.z, obj.name
    return None

def body_rot(yaw, pitch):
    # 先在身体坐标系里俯仰（躺下），再绕世界竖轴转朝向。原来用 'ZXY' 顺序会先转朝向再绕世界 X 轴倒下，
    # 朝向 180° 的人就变成脸朝下趴着（手脚穿过床板），已修正为 'YXZ'
    return Euler((math.radians(pitch), 0, math.radians(yaw)), 'YXZ').to_quaternion()

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

def apply_state(rig, st, frame=None, lag=0):
    """st: dict(pos=(x,y,z地面), yaw=°, base='stand', arms='down', look=Vector世界目标点或None, look_w=0.6)"""
    reset(rig)
    b = BASE[st.get('base', 'stand')]; a = ARMS[st.get('arms', 'down')]
    Rb = body_rot(st.get('yaw', 0), b['pitch'])
    root = rig.pose.bones['root']
    R0 = rig.matrix_world @ root.bone.matrix_local
    x, y, z = st.get('pos', (0, 0, 0))
    hip = R0.translation.z + b['dz'] + z
    kind = SUPPORTED.get(st.get('base', 'stand'))
    support = support_height(rig, x, y, hip) if (kind and SUPPORT_ON) else None
    if support is not None and abs(support[0] - (hip - 0.1)) > 0.6: support = None   # 离得太远：不是它坐/躺的那件家具
    root.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(Vector((x, y, hip)), Rb @ R0.to_quaternion(), R0.to_scale())
    bpy.context.view_layer.update()
    W = lambda d: Rb @ d
    spine_d = b['spine']
    if st.get('lean'):   # 额外前倾(+)/后仰(-)，用于起身后的晃动、急停时的惯性
        spine_d = Quaternion(Vector((1, 0, 0)), math.radians(st['lean'])) @ spine_d   # 绕身体 X 轴正转 = 向 -Y（前方）倾
    for n in SPINE: aim(rig, n, W(spine_d))
    head_d = a.get('head') or b.get('head') or V(0, -0.05, 1)
    for n in NECK: aim(rig, n, W((spine_d + head_d).normalized()))
    look = st.get('look')
    hd = W(head_d)
    if look is not None:   # 视线：头部转向目标点（按权重与姿态方向混合）
        hpos = (rig.matrix_world @ rig.pose.bones['head'].matrix).translation
        to = (Vector(look) - hpos).normalized(); w = st.get('look_w', 0.6)
        hd = (hd * (1 - w) + (to + Vector((0, 0, 0.9))).normalized() * w).normalized()
    aim(rig, 'head', hd)
    for side, mir in (('L', True), ('R', False)):
        ul = b['ulegL'] if (mir and 'ulegL' in b) else (mirror(b['uleg']) if mir else b['uleg'])   # 左右腿不对称的姿态（爬梯）
        ll = b['llegL'] if (mir and 'llegL' in b) else (mirror(b['lleg']) if mir else b['lleg'])
        if rig.get('v11_female') and st.get('base', 'stand') in ('stand', 'stand_rest'):   # 女性站姿：双腿略向内收（髋宽，直着站会显得腿分得太开）
            inward = Vector((-0.075 if mir else 0.075, 0, 0))
            ul = (ul + inward).normalized(); ll = (ll + inward * 0.4).normalized()
        aim(rig, 'upperleg01.' + side, W(ul)); aim(rig, 'upperleg02.' + side, W(ul))
        aim(rig, 'lowerleg01.' + side, W(ll)); aim(rig, 'lowerleg02.' + side, W(ll))
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
    def place_hands():
        ik = a.get('ik')
        if not ik or not SUPPORT_ON: return
        if ik == 'desk' and hands_on_surface(rig, Rb): return
        if SUPPORTED.get(st.get('base', 'stand')) == 'seat' or ik != 'desk':
            hands_on_lap(rig, Rb, {'desk': 'thighs'}.get(ik, ik))   # 面前没桌子（茶话会围坐）：手放腿上，绝不悬空
    place_hands()
    if support is not None:
        settle_on(rig, support, kind)
        place_hands()                                                 # 坐稳后高度变了，再落一次手
        if kind == 'seat' and SUPPORT_ON: clear_space(rig, zmin_rel=0.25, radius=0.34)   # 坐着：上身/头别钻进书架、桌上隔板
    elif st.get('base', 'stand') in ('stand', 'crouch', 'stand_rest') and SUPPORT_ON: clear_space(rig)
    if a.get('hand'): body_hands(rig, Rb, a['hand'], a.get('pole'))   # 身体定位以后再摆手（坐稳/推开之后身体位置才确定）
    if frame is not None: key(rig, frame, lag)

def body_anchor(rig, name, Rb):
    """身体部位的世界坐标（随当前姿势）：头顶、眼睛、下巴、耳朵、后颈、胸口、小腹、胯部"""
    M = rig.matrix_world; pb = rig.pose.bones
    up = Rb @ Vector((0, 0, 1)); fwd = Rb @ Vector((0, -1, 0)); left = Rb @ Vector((1, 0, 0))
    hd = M @ pb['head'].head; ht = M @ pb['head'].tail
    hc = hd.lerp(ht, 0.45)
    return {'crown': ht + up * 0.02, 'eyes': hc + fwd * 0.05 + up * 0.02, 'chin': hd + fwd * 0.07 - up * 0.02,
            'ear': hc - left * 0.075, 'neck': M @ pb['neck01'].head, 'chest': M @ pb['spine01'].head,
            'belly': M @ pb['spine04'].head, 'hip': M @ pb['root'].head}[name]

def body_hands(rig, Rb, spec, pole_kind=None):
    fwd = Rb @ Vector((0, -1, 0)); left = Rb @ Vector((1, 0, 0)); up = Rb @ Vector((0, 0, 1))
    for side, sgn in (('L', 1), ('R', -1)):
        if side not in spec: continue
        anchor, (df, dl, du) = spec[side]
        t = body_anchor(rig, anchor, Rb) + fwd * df + left * dl + up * du
        if pole_kind == 'out': pole = left * sgn * 1.5 - fwd * 0.4
        elif anchor in ('hip',) and df < 0: pole = left * sgn * 1.0 - fwd * 0.6 - up * 0.3   # 背手：手肘朝外后
        else: pole = -up * 0.8 + left * sgn * 0.7 - fwd * 0.25                               # 一般：手肘朝下、略向外
        _two_bone(rig, side, t, pole)

def _two_bone(rig, side, target, pole):
    """解析两骨 IK：肩 -> 肘 -> 腕，肘部朝 pole 方向弯"""
    pb = rig.pose.bones; M = rig.matrix_world
    S = M @ pb['upperarm01.' + side].head
    E0 = M @ pb['lowerarm01.' + side].head; W0 = M @ pb['wrist.' + side].head
    a, b = (E0 - S).length, (W0 - E0).length
    d = target - S; dist = min(d.length, (a + b) * 0.97); dn = d.normalized()
    ca = max(-1, min(1, (a * a + dist * dist - b * b) / (2 * a * dist)))
    perp = pole - dn * pole.dot(dn)
    perp = perp.normalized() if perp.length > 1e-5 else Vector((0, 0, -1))
    elbow = S + dn * (a * ca) + perp * (a * math.sqrt(1 - ca * ca))
    wrist = S + dn * dist
    aim(rig, 'upperarm01.' + side, (elbow - S).normalized()); aim(rig, 'upperarm02.' + side, (elbow - S).normalized())
    aim(rig, 'lowerarm01.' + side, (wrist - elbow).normalized()); aim(rig, 'lowerarm02.' + side, (wrist - elbow).normalized())

def hands_on_surface(rig, Rb):
    """前臂搭在面前的桌面上：射线找桌面高度，手腕落在桌沿内侧约 15 cm、身体两侧略向内收"""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get(); M = rig.matrix_world
    fwd = Rb @ Vector((0, -1, 0)); fwd.z = 0; fwd.normalize(); left = Rb @ Vector((1, 0, 0)); left.z = 0; left.normalize()
    for side, sgn in (('L', 1), ('R', -1)):
        S = M @ rig.pose.bones['upperarm01.' + side].head
        surf = None
        for reach in (0.30, 0.40, 0.22):                     # 在手前方几处找桌面
            p = S + fwd * reach + left * (-sgn * 0.08); o = Vector((p.x, p.y, S.z + 0.1)); t = 0
            while t < 1.0:
                hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + Vector((0, 0, -t)), Vector((0, 0, -1)), distance=1.0 - t)
                if not hit: break
                if _is_person(obj) or obj.name.startswith('prop_'): t = o.z - loc.z + 0.005; continue
                if S.z - 0.55 < loc.z < S.z - 0.12: surf = (p, loc.z)
                break
            if surf: break
        if surf is None: return False                        # 面前没有合适高度的桌面
        p, z = surf
        _two_bone(rig, side, Vector((p.x, p.y, z + 0.035)), Vector((0, 0, -1)) + left * sgn * 0.6 - fwd * 0.2)
    return True

def hands_on_lap(rig, Rb, mode):
    """坐姿手部：thighs=各搭在同侧大腿中段；lap=双手交叠在两腿之间靠近小腹；knees_fwd=前倾、双手在两膝之间相握"""
    M = rig.matrix_world; pb = rig.pose.bones
    fwd = Rb @ Vector((0, -1, 0)); fwd.z = 0; fwd.normalize(); left = Rb @ Vector((1, 0, 0)); left.z = 0; left.normalize()
    th = {s: (M @ pb['upperleg02.' + s].head, M @ pb['lowerleg01.' + s].head) for s in 'LR'}   # 大腿：中段、膝盖
    mid = (th['L'][0] + th['R'][0]) / 2; knee = (th['L'][1] + th['R'][1]) / 2
    for side, sgn in (('L', 1), ('R', -1)):
        hip_mid, kn = th[side]
        if mode == 'thighs':
            t = hip_mid.lerp(kn, 0.55) + Vector((0, 0, 0.075))
        elif mode == 'push':     # 膝盖上方、略偏外侧，手掌压在腿上
            t = hip_mid.lerp(kn, 0.85) + Vector((0, 0, 0.07)) + left * sgn * 0.02
        elif mode == 'lap':
            t = mid.lerp(knee, 0.30) + Vector((0, 0, 0.085)) + left * sgn * 0.03
        else:   # knees_fwd
            t = knee + fwd * 0.10 + Vector((0, 0, 0.02)) + left * sgn * 0.02
        _two_bone(rig, side, t, Vector((0, 0, -0.4)) + left * sgn * 1.0 - fwd * 0.6)

def _body_points(rig):
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in rig.children:
        if o.type != 'MESH' or not any(k in o.name for k in ('_body', 'suit')): continue
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); ev.to_mesh_clear()
        M = np.array(o.matrix_world, np.float32); pts.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(pts) if pts else None

WALLISH = ('wall', 'mirror', 'glass', 'facade', 'curtain')

def clear_space(rig, iters=4, zmin_rel=None, radius=0.27):
    """躯干/腿钻进家具或墙：沿水平方向把人推出来（标记点离家具太近、胖角色肚子顶进柜子等）。
    手臂只和墙/镜子/玻璃比较——手搭在桌上是正常的，伸进墙里不正常。zmin_rel：只看髋部以上多高的部分（坐着时用）"""
    import numpy as np
    root = rig.pose.bones['root']
    for _ in range(iters):
        allp = _body_points(rig)
        if allp is None: return
        rh = rig.matrix_world @ root.head
        zmin = rh.z + zmin_rel if zmin_rel is not None else 0.08
        core = allp[(np.hypot(allp[:, 0] - rh.x, allp[:, 1] - rh.y) < radius) & (allp[:, 2] > zmin)]
        arms = allp[allp[:, 2] > zmin]
        if not len(core): return
        push = Vector((0, 0, 0))
        for o in bpy.context.scene.objects:
            if o.type != 'MESH' or _is_person(o) or o.hide_render or o.name.startswith(('prop_', 'cam_')): continue
            w = arms if any(k in o.name for k in WALLISH) else core
            lo, hi = w.min(0), w.max(0)
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            olo = Vector([min(c[i] for c in bb) for i in range(3)]); ohi = Vector([max(c[i] for c in bb) for i in range(3)])
            if ohi.z < 0.06 or olo.z > 2.3: continue                    # 地面、天花板
            if olo.x > hi[0] or ohi.x < lo[0] or olo.y > hi[1] or ohi.y < lo[1] or olo.z > hi[2] or ohi.z < lo[2]: continue
            inv = np.array(o.matrix_world.inverted(), np.float32); q = w @ inv[:3, :3].T + inv[:3, 3]
            blo = np.array([min(c[i] for c in o.bound_box) for i in range(3)], np.float32)
            bhi = np.array([max(c[i] for c in o.bound_box) for i in range(3)], np.float32)
            inside = np.all((q > blo + 0.005) & (q < bhi - 0.005), axis=1)
            if not inside.any(): continue
            qi = q[inside]; sx = np.array(o.matrix_world.to_scale(), np.float32)
            best = None                                                  # 沿局部 x 或 y 推出去最短的那个方向
            for ax in (0, 1):
                d_neg = float((qi[:, ax] - blo[ax]).max() * sx[ax]); d_pos = float((bhi[ax] - qi[:, ax]).max() * sx[ax])
                for dist, sgn in ((d_neg, -1), (d_pos, 1)):
                    if best is None or dist < best[0]: best = (dist, ax, sgn)
            dist, ax, sgn = best
            dirv = o.matrix_world.to_3x3() @ Vector([sgn if i == ax else 0 for i in range(3)]); dirv.z = 0
            if dirv.length < 1e-6: continue
            push += dirv.normalized() * (dist + 0.01)
        if push.length < 0.004: return
        if push.length > 0.6: push = push.normalized() * 0.6
        M = rig.matrix_world @ root.matrix; M.translation += push
        root.matrix = rig.matrix_world.inverted() @ M
        bpy.context.view_layer.update()

def settle_on(rig, support, kind):
    """实测：摆好姿势后找出落在家具上方的身体/衣服最低点，整个人上下平移到正好压在面上（软垫允许陷 1 cm）"""
    import numpy as np
    surf, name = support; LAST_SUPPORT[rig.name] = name
    root = rig.pose.bones['root']; rh = rig.matrix_world @ root.head
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in rig.children:
        if o.type != 'MESH' or not any(k in o.name for k in ('_body', 'suit')): continue
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); ev.to_mesh_clear()
        co = co.reshape(-1, 3); M = np.array(o.matrix_world, np.float32)
        pts.append(co @ M[:3, :3].T + M[:3, 3])
    if not pts: return
    w = np.concatenate(pts)
    reach = 0.35 if kind == 'seat' else 1.2           # 坐：只看臀部/大腿（小腿垂到地上不算）；躺：整个身体
    w = w[(np.hypot(w[:, 0] - rh.x, w[:, 1] - rh.y) < reach) & (w[:, 2] < rh.z + 0.3)]
    if not len(w): return
    cell = np.floor(w[:, :2] / 0.06).astype(np.int64)  # 6 cm 网格，每格取最低点，逐点往下打射线找它正下方的面
    key = cell[:, 0] * 100003 + cell[:, 1]
    order = np.lexsort((w[:, 2], key)); first = np.ones(len(order), bool); first[1:] = key[order][1:] != key[order][:-1]
    sc = bpy.context.scene; gap = None
    for p in w[order][first]:
        o = Vector((float(p[0]), float(p[1]), float(p[2]) + 0.35)); t = 0.0
        while t < 1.2:
            hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + Vector((0, 0, -t)), Vector((0, 0, -1)), distance=1.2 - t)
            if not hit: break
            if _is_person(obj) or obj.name.startswith('prop_') or obj.hide_render: t = o.z - loc.z + 0.005; continue
            g = float(p[2]) - loc.z; gap = g if gap is None else min(gap, g); break
    if gap is None: return
    dz = -0.01 - gap                                     # 最贴近的那一处压在面上（软垫陷 1 cm）
    M = rig.matrix_world @ root.matrix; M.translation.z += dz
    root.matrix = rig.matrix_world.inverted() @ M
    bpy.context.view_layer.update()

# 两个状态之间真人需要的过渡时间（秒）：下半身换姿态最慢，转身按角度，手臂动作约 0.8 秒
BASE_T = {frozenset(('stand', 'sit')): 2.0, frozenset(('stand', 'crouch')): 1.2, frozenset(('sit', 'slump')): 1.1,
          frozenset(('sit_bed', 'lie')): 1.7, frozenset(('sit_bed', 'stand')): 1.8, frozenset(('sit_bed', 'hug_knees')): 1.3,
          frozenset(('stand', 'lie')): 2.4, frozenset(('crouch', 'sit')): 1.3, frozenset(('stand', 'sit_tight')): 2.0, frozenset(('stand', 'sit_lean')): 2.0, frozenset(('stand', 'sit_back')): 2.0}

def trans_time(a, b):
    t = 0.0
    ba, bb = a.get('base', 'stand'), b.get('base', 'stand')
    if ba != bb: t = max(t, BASE_T.get(frozenset((ba, bb)), 1.4))
    if a.get('arms') != b.get('arms') or a.get('reach') != b.get('reach'): t = max(t, 0.8)
    dyaw = abs((b.get('yaw', 0) - a.get('yaw', 0) + 180) % 360 - 180)
    t = max(t, dyaw / 90 * 0.5)
    d = (Vector(a.get('pos', (0, 0, 0))) - Vector(b.get('pos', (0, 0, 0)))).length
    if d > 0.02: t = max(t, 0.5 + d / 0.7)               # 原地挪一两步
    return t

HEADNECK = set(NECK + ['head'])
ARM_BONES = {n for n in BODY if any(k in n for k in ('clavicle', 'shoulder', 'arm', 'wrist'))}

def key(rig, frame, lag=0):
    """lag>0：动作分层错开——躯干先到，头颈晚 lag/2 帧，手臂晚 lag 帧（跟随动作，避免全身同时启停的机器感）"""
    for n in BODY:
        pb = rig.pose.bones.get(n)
        if pb is None: continue
        f = frame + (lag if n in ARM_BONES else (lag // 2 if n in HEADNECK else 0))
        pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
        if n == 'root': pb.keyframe_insert('location', frame=f, group=n)

def head_pos(rig):
    return (rig.matrix_world @ rig.pose.bones['head'].matrix).translation.copy()

def hand_matrix(rig, side='R'):
    return rig.matrix_world @ rig.pose.bones['wrist.' + side].matrix
