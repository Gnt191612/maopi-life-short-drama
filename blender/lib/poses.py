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
 'slump':  dict(dz=-0.42, pitch=0, spine=V(0, -0.75, 0.8), uleg=V(0.05, -1, 0.04), lleg=V(0, 0.12, -1), foot=V(0, -1, -0.3), head=V(0, -0.5, -0.85)),   # 前倾约 43°、头低下去（原来 60°，林晓胖，头伸到桌后墙边）
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
 'cross_arms':  dict(R=DOWN_R, hand={'R': ('chest', (0.21, 0.13, -0.12)), 'L': ('chest', (0.18, -0.14, -0.08))},   # 前 0.21/0.18：前臂压在胸前（0.13 时整条前臂陷在胸腔里）
                        wrist={'R': (-0.75, 0.5, 0.1), 'L': (-0.75, -0.5, 0.15)}),   # 手腕搭到对侧上臂、手掌往回包住胳膊（原来手伸出身体外、像摊手）   # 抱臂
 'chin':        dict(R=DOWN_R, hand={'R': ('chin', (0.09, 0.0, -0.19)), 'L': ('chest', (0.15, -0.04, -0.17))}, pole='down'),   # 手腕在下巴下方，手指托住下巴（原来手腕在嘴边，手掌盖住半张脸）    # 托下巴思考（另一只手托着手肘）
 'glasses':     dict(R=DOWN_R, hand={'R': ('eyes', (0.10, -0.015, -0.23))}, pole='down'),   # 目标是手腕：手腕在下巴前、指尖够到鼻梁（手掌连手指约 18cm，原来手腕对准眼睛，整只手盖在脸上）；，手肘朝下（原来手在两眼正中、肘朝外，前臂横挡整张脸）                                            # 推眼镜
 'scratch_head': dict(R=DOWN_R, hand={'R': ('crown', (-0.02, -0.07, 0.0))}),                                       # 挠头
 'neck_rub':    dict(R=DOWN_R, hand={'R': ('neck', (-0.08, -0.03, 0.03))}),                                        # 摸后脖颈（尴尬）
 'hands_back':  dict(R=DOWN_R, hand={'R': ('hip', (-0.19, -0.04, 0.03)), 'L': ('hip', (-0.19, 0.04, 0.05))}),      # 背着手
 'pockets':     dict(R=DOWN_R, hand={'R': ('hip', (0.06, -0.17, -0.09)), 'L': ('hip', (0.06, 0.17, -0.09))}),      # 双手插兜
 'pocket1':     dict(R=DOWN_R, hand={'R': ('hip', (0.06, -0.17, -0.09))}),                                          # 单手插兜
 'hip_hand':    dict(R=DOWN_R, hand={'R': ('hip', (0.0, -0.21, 0.07))}, pole='out'),                               # 单手叉腰
 'sleeves':     dict(R=DOWN_R, hand={'R': ('belly', (0.22, 0.03, 0.0)), 'L': ('belly', (0.22, -0.03, 0.02))}),     # 缩着袖子两手拢在身前
 'rub_hands':   dict(R=DOWN_R, hand={'R': ('chest', (0.26, 0.02, -0.12)), 'L': ('chest', (0.26, -0.02, -0.12))}), # 搓手
 'hand_chest':  dict(R=DOWN_R, hand={'R': ('chest', (0.11, 0.03, 0.0))}),                                         # 手按胸口（真诚）
 'open_palms':  dict(R=DOWN_R, hand={'R': ('chest', (0.32, -0.22, -0.12)), 'L': ('chest', (0.32, 0.22, -0.12))}),   # 胸前高度（原来对准肚子，坐着时和手搭腿上看不出区别）    # 摊开双手说话
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

NOT_SEAT = ('table', 'desk', 'shelf', 'counter', 'board', 'cabinet', 'hutch')   # 坐的时候不能当座位（2026-11-22：射线先碰到伸过来的桌面边，人坐到了桌面上）

def support_height(rig, x, y, z_hint, kind='seat'):
    """从髋部上方往下打射线，跳过人物，返回 (支撑面高度, 家具名)；找不到返回 None"""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    o = Vector((x, y, z_hint + 0.6)); d = Vector((0, 0, -1)); t = 0
    while t < 2.5:
        hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + d * t, d, distance=2.5 - t)
        if not hit: return None
        if _is_person(obj) or obj.name.startswith('prop_'): t = (o - loc).length + 0.01; continue
        if kind == 'seat' and any(k in obj.name.lower() for k in NOT_SEAT): t = (o - loc).length + 0.01; continue
        return loc.z, obj.name
    return None

SEAT_WORDS = ('_seat', 'stool', 'bench', 'sofa', 'couch')

def nearest_seat(x, y, radius):
    """离 (x,y) 最近的座位（椅面/凳子/长椅/沙发）中心；半径内没有返回 None"""
    best = None
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith('furn_') or not any(k in o.name for k in SEAT_WORDS): continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = sum(p.x for p in bb) / 8; cy = sum(p.y for p in bb) / 8
        if max(p.x for p in bb) - min(p.x for p in bb) > 1.0 or max(p.y for p in bb) - min(p.y for p in bb) > 1.0:   # 长椅、沙发：取离得最近的那一点
            cx = min(max(x, min(p.x for p in bb) + 0.25), max(p.x for p in bb) - 0.25); cy = min(max(y, min(p.y for p in bb) + 0.25), max(p.y for p in bb) - 0.25)
        d = math.hypot(cx - x, cy - y)
        if d < radius and (best is None or d < best[0]): best = (d, (cx, cy))
    return best[1] if best else None

def make_stool(rig, x, y, back=(0.0, 0.0)):
    """在 (x,y) 放一张 45cm 高的方凳（furn_stool_auto_*），已有就复用"""
    for o in bpy.data.objects:
        if o.name.startswith('furn_stool_auto') and math.hypot(o.location.x - x - back[0], o.location.y - y - back[1]) < 0.15: return True
    s, h = 0.15, 0.45   # 30cm 见方、放在臀部稍后（人坐凳子前半部分；原来 34cm 正中，大腿/小腿和凳子重叠 6~13cm）
    vs = [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0), (-s, -s, h), (s, -s, h), (s, s, h), (-s, s, h)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new('furn_stool_auto'); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new('furn_stool_auto_' + rig.name, me); ob.location = (x + back[0], y + back[1], 0)
    src = next((o for o in bpy.data.objects if o.name.startswith('furn_chair') and o.type == 'MESH' and o.data.materials), None)
    if src: me.materials.append(src.data.materials[0])
    bpy.context.scene.collection.objects.link(ob); bpy.context.view_layer.update()
    print('STOOL', rig.name, round(x, 2), round(y, 2), flush=True)
    return True

def body_rot(yaw, pitch):
    # 先在身体坐标系里俯仰（躺下），再绕世界竖轴转朝向。原来用 'ZXY' 顺序会先转朝向再绕世界 X 轴倒下，
    # 朝向 180° 的人就变成脸朝下趴着（手脚穿过床板），已修正为 'YXZ'
    return Euler((math.radians(pitch), 0, math.radians(yaw)), 'YXZ').to_quaternion()

def reset(rig):
    for n in BODY:
        pb = rig.pose.bones.get(n)
        if pb: pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()

def aim(rig, name, wdir):
    """让骨骼 Y 轴指向世界方向 wdir（最小扭转）"""
    pb = rig.pose.bones.get(name)
    if pb is None: return
    W = rig.matrix_world @ pb.matrix
    q = (W.to_quaternion() @ Y).rotation_difference(wdir) @ W.to_quaternion()
    pb.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(W.translation, q, W.to_scale())
    pb.scale = (1, 1, 1)   # 写整个矩阵会带进缩放误差，反复转头会累积（2026-11-22：第 8 场林晓的头被拉长 10 倍）；骨骼动画只要旋转
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
    support = support_height(rig, x, y, hip, kind) if (kind and SUPPORT_ON) else None
    if support is not None and abs(support[0] - (hip - 0.1)) > 0.6: support = None   # 离得太远：不是它坐/躺的那件家具
    if SUPPORT_ON and st.get('base', 'stand') in ('stand', 'stand_rest') and nearest_seat(x, y, 0.2):   # 从椅子上站起来原地站着：椅子穿过腿，像站在椅子上（s08 陈瑶）——往前迈一步
        fwd = Rb @ Vector((0, -1, 0)); fwd.z = 0
        if fwd.length > 1e-3: fwd.normalize(); x, y = x + fwd.x * 0.4, y + fwd.y * 0.4
    if kind == 'seat' and SUPPORT_ON and b['dz'] > -0.6 and (support is None or support[0] < 0.2):   # 只管坐椅子的姿势（盘腿、抱膝可以坐地上）   # 要坐但身下没有座位：附近 45cm 内有椅子就对过去，没有就放一张凳子（剧本让人坐在空地上，脚陷进地板）
        bk = Rb @ Vector((0, 0.08, 0))   # 身后 8cm（身体前方是 -Y）
        xy = nearest_seat(x, y, 0.45) or (make_stool(rig, x, y, (bk.x, bk.y)) and (x, y))
        x, y = xy
        support = support_height(rig, x, y, hip, kind)
        if support is not None and abs(support[0] - (hip - 0.1)) > 0.6: support = None
    root.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(Vector((x, y, hip)), Rb @ R0.to_quaternion(), R0.to_scale()); root.scale = (1, 1, 1)
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
        settle_on(rig, support, kind, st.get('base', 'stand'))
        if kind == 'seat' and 'step' in (support[1] or '').lower(): legs_on_step(rig, Rb, support[0])   # 坐在台阶上：脚踩下一级台阶
        place_hands()                                                 # 坐稳后高度变了，再落一次手
        if kind == 'seat' and SUPPORT_ON: clear_space(rig, zmin_rel=0.25, radius=(0.75 if st.get('base') == 'slump' else 0.34))   # 趴桌：前倾的头和上身也要查（林晓胖，头伸进桌后书架 14cm）   # 坐着：上身/头别钻进书架、桌上隔板
    elif st.get('base', 'stand') in ('stand', 'crouch', 'stand_rest') and SUPPORT_ON: clear_space(rig)
    if a.get('hand'): body_hands(rig, Rb, a['hand'], a.get('pole'), a.get('wrist'))   # 身体定位以后再摆手（坐稳/推开之后身体位置才确定）
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

def body_hands(rig, Rb, spec, pole_kind=None, wrist_dirs=None):
    fwd = Rb @ Vector((0, -1, 0)); left = Rb @ Vector((1, 0, 0)); up = Rb @ Vector((0, 0, 1))
    for side, sgn in (('L', 1), ('R', -1)):
        if side not in spec: continue
        anchor, (df, dl, du) = spec[side]
        t = body_anchor(rig, anchor, Rb) + fwd * df + left * dl + up * du
        if pole_kind == 'out': pole = left * sgn * 1.5 - fwd * 0.4
        elif pole_kind == 'down': pole = -up * 1.6 + left * sgn * 0.25 - fwd * 0.1   # 手到脸附近：手肘垂下贴近身体（不横在脸前）
        elif anchor in ('hip',) and df < 0: pole = left * sgn * 1.0 - fwd * 0.6 - up * 0.3   # 背手：手肘朝外后
        else: pole = -up * 0.8 + left * sgn * 0.7 - fwd * 0.25                               # 一般：手肘朝下、略向外
        _two_bone(rig, side, t, pole)
        if wrist_dirs and side in wrist_dirs:   # 手腕弯折：手掌指向给定方向（身体坐标 前/左/上），否则手掌顺着前臂伸出去
            wf, wl, wu = wrist_dirs[side]; aim(rig, 'wrist.' + side, (fwd * wf + left * wl + up * wu).normalized())

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
        pb_ = rig.pose.bones; L1 = pb_['upperarm01.' + side].length + pb_['upperarm02.' + side].length
        L2 = pb_['lowerarm01.' + side].length + pb_['lowerarm02.' + side].length
        drop = S.z - (z + 0.045)
        if 0 < drop < L1 * 0.95:   # 桌面相对肩膀偏高：手肘垂下去会低于桌面，前臂斜着穿过桌子（陈瑶伏案，2026-11-23）——让手肘落在桌面上、前臂平放
            h = math.sqrt(L1 * L1 - drop * drop)
            q = S + fwd * (h + L2 * 0.8) + left * (-sgn * 0.10)
            hit, loc, _, _, obj, _ = sc.ray_cast(dg, Vector((q.x, q.y, S.z + 0.1)), Vector((0, 0, -1)), distance=1.0)
            if hit and abs(loc.z - z) < 0.03: p = q
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
        if o.type != 'MESH' or any(k in o.name for k in ('hair', 'scalp', 'eyebrow', 'eyelash', 'teeth', 'high-poly', 'eye')): continue   # 衣服全算（原来只算身体和 suit：裙子、外套下摆比皮肤低几厘米，压进沙发 5cm）
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); ev.to_mesh_clear()
        M = np.array(o.matrix_world, np.float32); pts.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(pts) if pts else None

WALLISH = ('wall', 'mirror', 'glass', 'facade', 'curtain')

GROUND_WORDS = ('step', 'landing', 'stair', 'platform', 'stage', 'curb', 'podium', 'ground', 'floor', 'track', 'plaza', 'path', 'road', 'grass', 'lawn', 'pavement')

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
            if o.type != 'MESH' or _is_person(o) or o.name.startswith(('prop_', 'cam_')) or any(k in o.name.lower() for k in GROUND_WORDS): continue   # 地面类（台阶、平台）不是障碍：站在 1.2m 平台上时脚踩着平台，原来被当成「陷进平台」水平推出去、推进外墙 24cm（s04）；不跳过 hide_render：那是机位临时藏的家具，换机位就出现（原来趴桌时书架正被藏着，没推开，下一拍头嵌在书架里）
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
        root.matrix = rig.matrix_world.inverted() @ M; root.scale = (1, 1, 1)
        bpy.context.view_layer.update()

def legs_on_step(rig, Rb, seat_z, drop=0.15, reach=0.42):
    """坐在台阶上：膝盖抬高、脚踩在下一级台阶上（台阶每级只低 15cm，按坐椅子的姿势小腿会插进下一级，2026-11-23 规则审查）"""
    M = rig.matrix_world; pb = rig.pose.bones
    fwd = Rb @ Vector((0, -1, 0)); fwd.z = 0; fwd.normalize(); up = Vector((0, 0, 1))
    for side in ('L', 'R'):
        if pb.get('upperleg01.' + side) is None: continue
        S = M @ pb['upperleg01.' + side].head; E0 = M @ pb['lowerleg01.' + side].head; W0 = M @ pb['foot.' + side].head
        ankle_h = (M @ rig.data.bones['foot.' + side].head_local).z - M.translation.z
        target = Vector((S.x, S.y, 0)) + fwd * reach; target.z = seat_z - drop + ankle_h
        a, b = (E0 - S).length, (W0 - E0).length
        d = target - S; dist = min(d.length, (a + b) * 0.98); dn = d.normalized()
        ca = max(-1, min(1, (a * a + dist * dist - b * b) / (2 * a * dist)))
        pole = fwd + up * 0.8; perp = pole - dn * pole.dot(dn)
        perp = perp.normalized() if perp.length > 1e-5 else up
        knee = S + dn * (a * ca) + perp * (a * math.sqrt(1 - ca * ca)); foot = S + dn * dist
        for n_ in ('upperleg01.', 'upperleg02.'): aim(rig, n_ + side, (knee - S).normalized())
        for n_ in ('lowerleg01.', 'lowerleg02.'): aim(rig, n_ + side, (foot - knee).normalized())
        aim(rig, 'foot.' + side, (fwd - up * 0.3).normalized())

def settle_on(rig, support, kind, base='sit'):
    """实测：摆好姿势后找出落在家具上方的身体/衣服最低点，整个人上下平移到正好压在面上（软垫允许陷 1 cm）"""
    import numpy as np
    surf, name = support; LAST_SUPPORT[rig.name] = name
    root = rig.pose.bones['root']; rh = rig.matrix_world @ root.head
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in rig.children:
        if o.type != 'MESH' or any(k in o.name for k in ('hair', 'scalp', 'eyebrow', 'eyelash', 'teeth', 'high-poly', 'eye')): continue   # 衣服全算（原来只算身体和 suit：裙子、外套下摆比皮肤低几厘米，压进沙发 5cm）
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); ev.to_mesh_clear()
        co = co.reshape(-1, 3); M = np.array(o.matrix_world, np.float32)
        pts.append(co @ M[:3, :3].T + M[:3, 3])
    if not pts: return
    w = np.concatenate(pts)
    reach = 0.35 if (kind == 'seat' and base not in ('sit_bed', 'hug_knees')) else 1.2   # 坐椅子：只看臀部/大腿（小腿垂到地上不算）；躺、坐在床上伸腿/抱膝：整个身体（伸直的腿原来陷进床垫）
    w = w[(np.hypot(w[:, 0] - rh.x, w[:, 1] - rh.y) < reach) & (w[:, 2] < rh.z + 0.3)]
    for side in (('L', 'R') if kind == 'seat' else ()):   # 躺着时手臂也压在床上，要算（否则胳膊陷进床垫 5cm）；坐着时手和前臂不算：坐着垂下的手落在椅面边上，整个人被抬高 26cm（s02 陈瑶挥手，2026-11-22）
        e0 = rig.pose.bones.get('lowerarm01.' + side); wr = rig.pose.bones.get('wrist.' + side)
        if e0 is None or wr is None or not len(w): continue
        a_ = np.array(rig.matrix_world @ e0.head, np.float32); b_ = np.array(rig.matrix_world @ wr.tail, np.float32)
        b_ = b_ + (b_ - a_) / max(1e-4, float(np.linalg.norm(b_ - a_))) * 0.12   # 延长到指尖
        ab = b_ - a_; tt = np.clip(((w - a_) @ ab) / float(ab @ ab), 0, 1)
        w = w[np.linalg.norm(w - (a_ + tt[:, None] * ab), axis=1) > 0.09]
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
            if _is_person(obj) or obj.name.startswith('prop_'): t = o.z - loc.z + 0.005; continue   # 机位临时藏起来的家具照样是支撑面
            if kind == 'seat' and any(k in obj.name.lower() for k in NOT_SEAT): t = o.z - loc.z + 0.005; continue   # 坐着时大腿下面的书桌不算支撑（林晓被抬到大腿搁在桌面上，浮在椅子上方 36cm，2026-11-22）
            if loc.z > float(p[2]) + 0.15: t = o.z - loc.z + 0.005; continue   # 面在这一点上方 15cm 以上：人在它下面（腿伸在桌下），不是压在它上面
            g = float(p[2]) - loc.z; gap = g if gap is None else min(gap, g); break
    if gap is None: return
    dz = -0.01 - gap                                     # 最贴近的那一处压在面上（软垫陷 1 cm）
    M = rig.matrix_world @ root.matrix; M.translation.z += dz
    root.matrix = rig.matrix_world.inverted() @ M; root.scale = (1, 1, 1)
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
