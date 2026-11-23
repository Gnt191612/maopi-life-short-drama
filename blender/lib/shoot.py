# -*- coding: utf-8 -*-
"""白模拍摄引擎：把一个「地点片段」（同一场戏里同一地点的连续若干拍）搭成完整动画：
  场景 + 角色 + 道具 + 每拍走位/姿态（状态在拍之间连续继承）+ 走路动作捕捉 + 口型 + 自动机位（含 180° 轴线）+ 渲染设置。
时间轴：片段内各拍首尾相接（24fps），拍时长 = 动作所需与台词所需取大。
"""
import os, sys, json, math, re
import bpy, zlib
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import poses, face, retarget, sets, life, nav, phone_ui, realism
import blocking

VIS = config.VISEMES; MOCAP = config.MOCAP
from segments import FPS, LEAD, META, TEXT, CID, EST_SET, audio_plan, screen_plan, beat_dur, beat_frames, loc_of, segments
from lines import SCREEN
NAME = {v: k for k, v in CID.items()}
# 人物习惯动作（不说话时在长镜头里自然流露）：林晓局促、陈瑶理性克制、周明远沉稳、王老师师长气、同学甲大大咧咧、同学乙文静、林母慈和
# 不用推眼镜/托腮：IK 只管手腕位置、手掌顺着前臂立起来，整只手盖在嘴和鼻子上，云端换脸、口型都会坏（2026-11-23 手势总览检查）
HABITS = {'lin':    {'stand': ['scratch_head', 'neck_rub', 'pocket1', 'rub_hands'], 'sit': ['rub_hands', 'neck_rub', 'scratch_head']},
          'chen':   {'stand': ['cross_arms', 'pockets', 'hands_back'], 'sit': ['cross_arms', 'hand_chest']},
          'zhou':   {'stand': ['pockets', 'hands_back'], 'sit': ['rub_hands', 'hand_chest']},
          'wang':   {'stand': ['hands_back', 'cross_arms'], 'sit': ['rub_hands', 'hand_chest']},
          'classA': {'stand': ['scratch_head', 'hip_hand', 'pockets'], 'sit': ['scratch_head', 'neck_rub']},
          'classB': {'stand': ['sleeves', 'hair_tuck', 'cross_arms'], 'sit': ['sleeves', 'hair_tuck']},
          'mom':    {'stand': ['hand_chest'], 'sit': ['hair_tuck', 'hand_chest']}}
TALK = {'lin': ['open_palms', 'scratch_head', 'hand_chest'], 'chen': ['open_palms', 'hand_chest'],   # 说话时不用推眼镜/托腮：手挡在脸前，云端换脸和口型都会坏（2026-11-23）
        'zhou': ['open_palms', 'hand_chest'],
        'wang': ['open_palms', 'hand_chest'], 'classA': ['scratch_head', 'open_palms'], 'classB': ['hand_chest', 'hair_tuck'],
        'mom': ['hand_chest', 'open_palms']}

# ---------------- 场景/角色装配 ----------------
def append_cast(cid):
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects: bpy.context.scene.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']
    rig.animation_data_create(); rig.animation_data.action = bpy.data.actions.new(cid + '_act')
    realism.enhance_character(rig)                    # 皮肤毛孔、眼睛湿润高光、衣服褶皱
    return rig

make_phone = phone_ui.make_phone   # 每个角色一部手机：机身 + 屏幕面（prop_screen_<cid>）+ 屏幕界面

def show_phone(pair, frame, in_hand):
    held, rest = pair
    for o, vis in ((held, in_hand), (rest, not in_hand)):
        for c in phone_ui.phone_parts(o):
            c.hide_render = c.hide_viewport = not vis
            c.keyframe_insert('hide_render', frame=frame); c.keyframe_insert('hide_viewport', frame=frame)

def attach(prop, rig, bone, frame, on, local=None):
    """道具跟随手骨（Child Of 约束 influence 打关键帧切换：拿起/放下）"""
    con = prop.constraints.get('hold') or prop.constraints.new('CHILD_OF')
    con.name = 'hold'; con.target = rig; con.subtarget = bone
    con.inverse_matrix = Matrix.Identity(4)
    con.influence = 1.0 if on else 0.0; con.keyframe_insert('influence', frame=frame)

# ---------------- 机位 ----------------
SHOT = {'ECU': (0.42, 60), 'CU': (0.75, 50), 'MCU': (1.15, 45), 'MS': (2.1, 32), 'WS': (3.8, 22)}

def shot_type(en):
    e = (en or '').lower()
    if 'extreme close' in e: return 'ECU'
    if 'medium close' in e: return 'MCU'
    if 'close-up' in e or 'close up' in e: return 'CU'
    if 'wide' in e or 'long shot' in e: return 'WS'
    return 'MS'

def _bbox(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return [min(p[i] for p in bb) for i in range(3)], [max(p[i] for p in bb) for i in range(3)]

def with_resting(names, protect=()):
    """连同「放在它上面」的东西一起移走：只拆书架不拆书，书就悬在半空（陈瑶身前一排漂浮的书，2026-11-22）"""
    out = set(names); todo = list(names)
    boxes = {o.name: _bbox(o) for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(('furn_', 'prop_')) and o.parent is None}
    while todo:
        n = todo.pop(); ob = bpy.data.objects.get(n)
        if ob is None or ob.type != 'MESH': continue
        lo, hi = boxes.get(n) or _bbox(ob)
        for m, (l2, h2) in boxes.items():
            if m in out or m in protect or m.startswith(('prop_phonebody_', 'prop_screen_')): continue
            on_top = abs(l2[2] - hi[2]) < 0.04 and l2[0] < hi[0] and h2[0] > lo[0] and l2[1] < hi[1] and h2[1] > lo[1]
            inside = all(l2[i] > lo[i] - 0.03 and h2[i] < hi[i] + 0.03 for i in range(3))   # 嵌在里面的（书架方块里的书）
            if on_top or inside:
                out.add(m); todo.append(m)
    return out

def hide_range(names, frame0, frame1, protect=()):
    """在 frame0..frame1 内临时移走挡镜头的家具（前后恢复）"""
    for n in sorted(with_resting(names, protect)):
        ob = bpy.data.objects[n]
        for fr, v in ((frame0 - 1, False), (frame0, True), (frame1 + 1, False)):
            ob.hide_render = v; ob.keyframe_insert('hide_render', frame=fr)

HIDEABLE = ('furn_', 'prop_', 'ext_lamp', 'ext_trunk', 'ext_crown', 'ext_bike', 'ext_column', 'ext_bench', 'ext_bin', 'ext_sign', 'ext_hedge', 'ext_flower')

def _wall(name):
    """房间的墙（不含地面、天花）：像真实片场的「活动墙」一样，挡在机位后面时可以临时拆掉"""
    if any(k in name for k in ('_glass_window', '_fabric_curtain', '_wood_door')): return True   # 窗玻璃、窗帘、门跟着墙一起拆（机位在墙外时它们挡在画面边上）
    return '_wall' in name and 'ceiling' not in name and 'floor' not in name

def place_camera(name, subj_pts, facing_yaw, kind, side, bounds, frame0, frame1, en='', head_up=None, protect=(), validate=None, own_rigs=()):
    """subj_pts: 被摄主体关键点（头部世界坐标列表）；facing_yaw：主体朝向；side：+1/-1 轴线一侧；
    validate(cam)->bool：按分数从高到低试候选机位，第一个通过检查（脸朝镜头、在画面里、没被人挡）的就用"""
    dist, lens = SHOT[kind]
    protect = set(protect) | {b + n.split('_', 2)[-1] for n in protect if n.startswith(NO_HIDE) for b in NO_HIDE}   # 有人躺/坐的床：床板、床垫、被子、枕头整套都不许移走
    c = sum(subj_pts, Vector()) / len(subj_pts)
    # 瞄准高度（相对头部骨骼根部≈下巴高度；头顶约在其上 0.22m）。45mm 镜头竖向半视角 ≈ 0.225×距离：
    # 原来中近景瞄胸口（-0.25）、中景 -0.45，画面上沿切到额头（2026-11-22 试片发现林母只拍到下半张脸）；特写 +0.02（低头时脸会往下移，抬太高只拍到头顶）；超近景多是拍物件，不动
    tgt = c + Vector((0, 0, {'ECU': -0.05, 'CU': 0.02, 'MCU': -0.05, 'MS': -0.25}.get(kind, -0.45)))
    e = (en or '').lower()
    if len(subj_pts) > 1: dist *= 1.0 + 0.35 * (len(subj_pts) - 1)
    face_dir = facing_yaw if isinstance(facing_yaw, Vector) else Vector((math.sin(math.radians(facing_yaw)), -math.cos(math.radians(facing_yaw)), 0))
    face_dir = face_dir.normalized()
    right = face_dir.cross(Vector((0, 0, 1))) if abs(face_dir.z) < 0.9 else Vector((1, 0, 0))
    lying = abs(face_dir.z) > 0.9 and head_up is not None
    if lying:   # 躺着（脸朝上）：候选机位往房间中间那一侧转（原来固定往 +X 转，一半的床靠墙那侧只能从床垫底下拍，s01 林晓躺床）
        right = Vector(head_up).cross(face_dir); right.z = 0
        if right.length < 1e-3: right = Vector((1, 0, 0))
        right.normalize()
        if right.dot(-Vector((c.x, c.y, 0))) < 0: right = -right
        tgt = c - Vector(head_up).normalized() * {'ECU': 0.05, 'CU': -0.02, 'MCU': 0.05, 'MS': 0.25}.get(kind, 0.45)   # 瞄准偏移沿身体方向（不是世界竖直）
    right.normalize(); upv = right.cross(face_dir).normalized()
    if 'from behind' in e: offs = [180 - 20 * side, 160, 200]
    elif 'over the shoulder' in e or 'over shoulder' in e: offs = [150 * side, 130 * side]
    elif 'from beside' in e: offs = [70 * side, 50 * side, 90 * side]
    else: offs = [28 * side, 12 * side, 45 * side, 65 * side, 90 * side, 110 * side]   # 先 3/4 正面，挡住就逐步转向侧面（不越轴）
    if lying: offs = [abs(o) for o in offs]
    n_main = len(offs)
    if 'from behind' not in e: offs = offs + [-o for o in offs[:3]]   # 最后的退路：越轴到另一侧（人在本拍里脸朝另一边时，同侧候选全都看不到脸）
    elev = 0.06 if kind in ('ECU', 'CU', 'MCU') else 0.18
    if 'floor level' in e: elev = -0.35
    if ('close-up of' in e or 'close-up over' in e) and any(k in e for k in OBJ_CLOSE['hands'] + OBJ_CLOSE['phone']): elev = 1.1 if any(k in e for k in ('table', 'desk')) else 0.55   # 桌面/手/手机特写（桌面特写近乎俯拍）：斜上方俯拍（平拍时身体挡在手前面，画面一大块外套）
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    spread = 0.1 if kind in ('ECU', 'CU') else 0.25
    def probe(p, d):
        """沿视线收集挡在中间的家具/道具（可临时移走），遇到墙/地/天花/其他人则停下"""
        hidden, t = set(), 0.28
        while t < dist:
            hit, loc, _, _, obj, _ = sc.ray_cast(dg, p + d * t, d, distance=dist - t)
            if not hit: return dist, hidden, False
            hd = (loc - p).length
            if obj.name.startswith(PASS_THRU): t = hd + 0.02; continue   # 手机不藏（原来把自拍手机的屏幕藏掉了）
            if (obj.name.startswith(HIDEABLE) or _wall(obj.name)) and obj.name not in protect:
                hidden.add(obj.name); t = hd + 0.02; continue
            if obj.parent is not None and obj.parent in own_rigs: t = hd + 0.02; continue   # 被摄主体自己的身体：穿过去（三人挤在一起时瞄准点在中间那人胸口里，原来一出发就撞上，所有机位都贴在她身上）
            person = bool(obj.name.split('_')[0] in CID.values() or (obj.parent is not None and obj.parent.name.endswith('_rig')))
            return hd - 0.12, hidden, person
        return dist, hidden, False
    cands = []
    for k, o in enumerate(offs):   # 每个候选角度打 5 条射线（主体中心 + 上下左右），按视线通畅程度打分
        for ev, epen in ((elev, 0.0), (elev + 0.18, 0.05), (elev + 0.6, 0.12)):   # 第三档高机位俯拍：床铺、桌面上的人和物件被前景挡住时的退路
            a = math.radians(o)
            d = (face_dir * math.cos(a) + right * math.sin(a) + upv * ev).normalized()
            rgt = d.cross(Vector((0, 0, 1))).normalized() if abs(d.z) < 0.95 else Vector((1, 0, 0))
            clear, hidden, by_person = dist, set(), False
            for p in (tgt, tgt + rgt * spread, tgt - rgt * spread, tgt + Vector((0, 0, spread)), tgt - Vector((0, 0, spread))):
                c_, h_, pr = probe(p, d); clear = min(clear, c_); hidden |= h_; by_person |= pr
            walls = sum(1 for n in hidden if _wall(n))
            score = (min(clear, dist) / dist - 0.04 * k - epen - (0.6 if k >= n_main else 0) - 0.01 * len(hidden) - 0.04 * walls
                     - ((1.0 if clear < 0.8 * dist else 0.5) if by_person else 0))   # 被别人挡住：前景一大块肩膀，尽量不用
            cands.append((score, d, max(0.3, min(clear, dist)), hidden))
    cands.sort(key=lambda c_: -c_[0])
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); bpy.context.scene.collection.objects.link(cam)
    fstop = {'ECU': 2.8, 'CU': 2.8, 'MCU': 2.8, 'MS': 4.0}.get(kind)   # 景深：对焦在主体脸上
    def aim_at(d, clear):
        pos = tgt + d * clear
        cam.data.lens = max(14, lens * clear / dist)              # 被迫收近时换广角，保持景别
        cam.data.clip_start = 0.05; cam.data.clip_end = 300
        if fstop:
            cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = fstop; cam.data.dof.focus_distance = max(0.2, (pos - tgt).length)
        dd = tgt - pos; cam.location = pos
        up = Vector((0, 0, 1))
        if head_up is not None and (abs(dd.normalized().z) > 0.6 or (lying and kind in ('ECU', 'CU', 'MCU'))): up = Vector(head_up)   # 躺着的人拍近景：画面上方对着头顶（侧面机位按世界竖直会把脸拍倒，s01 林晓）   # 俯拍/仰拍躺着的人：以头顶方向为画面上方，避免人脸倒置
        z = (-dd).normalized(); x = up.cross(z)
        if x.length < 1e-4: x = Vector((1, 0, 0))
        x.normalize(); y = z.cross(x)
        cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        bpy.context.view_layer.update()
        return pos, dd
    global _HIDE_ACC, _HIDE_ACC_PROTECT
    FAIL_LOG.clear(); chosen = cands[0]; least = None
    for c_ in cands:
        aim_at(c_[1], c_[2])
        if validate is None: chosen = c_; break
        hid_ = [bpy.data.objects[n] for n in c_[3] if n in bpy.data.objects and not bpy.data.objects[n].hide_viewport]
        for o in hid_: o.hide_viewport = True                # 验证视线时按这个机位拆墙后的样子算（射线检测看 hide_viewport）
        _HIDE_ACC, _HIDE_ACC_PROTECT = set(), set(protect)
        try: ok_ = validate(cam)
        finally: extra = _HIDE_ACC; _HIDE_ACC = None
        for o in hid_: o.hide_viewport = False
        if ok_: chosen = (c_[0], c_[1], c_[2], set(c_[3]) | extra); break
        if least is None or LAST_SEV[0] < least[0]: least = (LAST_SEV[0], (c_[0], c_[1], c_[2], set(c_[3]) | extra))
    else:
        if least is not None: chosen = least[1]
        print('CAM FALLBACK', name, '（没有候选通过检查，用问题最轻的）', ' | '.join(FAIL_LOG[:6]), flush=True)
    _, d, clear, hidden = chosen
    pos, d = aim_at(d, clear)
    hide_range(hidden, frame0, frame1, protect)   # 本拍临时移走挡镜头的家具/活动墙（拍完恢复）
    camera_move(cam, pos, tgt, kind, e, frame0, frame1, len(subj_pts), lying=(head_up is not None and abs(face_dir.z) > 0.9))
    cam['hidden'] = sorted(with_resting(hidden, protect))   # 沿用机位时也要连书带架一起移走
    return cam

EMO = ('tear', 'cry', 'sob', 'slump', 'shock', 'stunn', 'realiz', 'silent', 'silence', 'laugh', 'hug', 'moved', 'sigh', 'frozen', 'stare', 'whisper', 'smile')
PUSH = {'ECU': 0.03, 'CU': 0.045, 'MCU': 0.055, 'MS': 0.07, 'WS': 0.06}   # 一拍推近多少（占机位距离的比例）

def _look(pos, tgt):
    z = (pos - tgt).normalized(); x = Vector((0, 0, 1)).cross(z)
    if x.length < 1e-4: return None
    x.normalize(); y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_euler()

def camera_move(cam, pos, tgt, kind, e, f0, f1, n_subj, lying=False):
    """运镜（白模的镜头运动经深度图/骨架图直接带进成片）：
    原来每拍只推近不到 12cm，几乎是固定机位，整片很「死」（2026-11-22 用户要求优化运镜）。
    全景/中景缓推；多人中景绕人物弧移 4°（视差让空间立体）；近景/特写轻推 + 极轻的手持呼吸感；情绪拍子推得更多。"""
    sc = bpy.context.scene; dist = (tgt - pos).length; d = (tgt - pos).normalized()
    emo = any(k in e for k in EMO)
    push = min(dist * PUSH.get(kind, 0.05) * (1.8 if emo else 1.0), 0.35)
    end = pos + d * push
    if kind in ('MS', 'WS') and n_subj > 1 and not lying and f1 - f0 > 36:   # 弧移：先确认路上没东西
        side_ = 1 if (zlib.crc32(cam.name.encode()) & 1) else -1
        rel = pos - tgt; ang = math.radians(4) * side_
        arc = tgt + Vector((rel.x * math.cos(ang) - rel.y * math.sin(ang), rel.x * math.sin(ang) + rel.y * math.cos(ang), rel.z))
        arc = arc + (tgt - arc).normalized() * push
        dg = bpy.context.evaluated_depsgraph_get(); mv = arc - pos
        hit = sc.ray_cast(dg, pos, mv.normalized(), distance=mv.length + 0.2)[0] if mv.length > 1e-3 else False
        if not hit: end = arc
    cam.location = pos; cam.keyframe_insert('location', frame=f0)
    r0 = cam.rotation_euler.copy(); cam.keyframe_insert('rotation_euler', frame=f0)
    cam.location = end; cam.keyframe_insert('location', frame=f1)
    r1 = _look(end, tgt) if (end - (pos + d * push)).length > 1e-3 else None
    if r1 is not None:
        r1.make_compatible(r0); cam.rotation_euler = r1
    cam.keyframe_insert('rotation_euler', frame=f1)
    cam.rotation_euler = r0; cam.location = pos
    act = cam.animation_data.action if cam.animation_data else None
    if act is None: return
    for fc in act.fcurves:
        for k in fc.keyframe_points: k.interpolation = 'BEZIER'; k.easing = 'EASE_IN_OUT'   # 起落都缓（真人推轨的加减速）
        if kind in ('ECU', 'CU', 'MCU') and (fc.data_path, fc.array_index) in (('rotation_euler', 0), ('rotation_euler', 2), ('location', 2)):
            nm = fc.modifiers.new('NOISE'); nm.scale = 48; nm.phase = (zlib.crc32((cam.name + str(fc.array_index)).encode()) % 1000) / 10.0   # crc32 而不是 hash()：hash 每次运行都变，重拍结果就对不上
            nm.strength = 0.004 if fc.data_path == 'rotation_euler' else 0.006   # 约 ±0.1°、±3mm：只是呼吸感，不晃
    cam['move'] = 'arc' if r1 is not None else ('hand' if kind in ('ECU', 'CU', 'MCU') else 'push')   # 写进 _cuts.json，云端提示词用
    print('CAM MOVE', cam.name, kind, 'emo' if emo else '', 'arc' if r1 is not None else 'push %.2f' % push, flush=True)

def face_dir(rig):
    """头部真实朝向（含转头）：静止时脸朝 -Y，换算到头骨局部轴再随姿态转到世界"""
    hb = rig.pose.bones['head']
    rest = hb.bone.matrix_local.inverted().to_3x3() @ Vector((0, -1, 0))
    hm = rig.matrix_world @ hb.matrix
    return (hm.to_3x3() @ rest).normalized(), hm.translation + hm.to_3x3() @ Vector((0, hb.length * 0.5, 0))

_HIDE_ACC = None; _HIDE_ACC_PROTECT = set()   # 验证候选机位时收集「挡视线但可以移走」的物件
NO_HIDE = ('furn_bed_', 'furn_mattress_', 'furn_quilt_', 'furn_pillow_')   # 有人躺/坐的床整套不移走（place_camera 里按 protect 展开）
PASS_THRU = ('prop_phonebody_', 'prop_screen_', 'prop_phone')
NOT_OBSTRUCT = ('floor', 'ground', 'ceiling', 'ext_road', 'ext_grass', 'ext_path', 'ext_plaza')   # 地面、天花：出现在画面里不算挡

def _hideable(name):
    return _HIDE_ACC is not None and (name.startswith(HIDEABLE) or _wall(name)) and name not in _HIDE_ACC_PROTECT

def _near_hand(rig, p, r=0.11):
    for s in ('L', 'R'):
        wb = rig.pose.bones.get('wrist.' + s)
        if wb is None: continue
        h_ = rig.matrix_world @ wb.head; t_ = rig.matrix_world @ wb.tail
        if (p - h_).length < r or (p - t_).length < r or (p - (t_ + (t_ - h_).normalized() * 0.06)).length < r: return True
    return False

def _blocked(sc, dg, cpos, target, own=None, margin=0.25, own_near=None, hands_block=True):
    """镜头到目标点的视线是否被挡（墙、家具、别人；目标自己的身体与手机不算）。
    验证机位时（_HIDE_ACC 不为空）挡路的可移走家具记下来本拍移走，不算挡"""
    global _LAST_BLOCK
    d = target - cpos; dist = d.length - margin
    if dist <= 0.05: return False
    d.normalize(); t = 0.02
    while t < dist:
        hit, loc, _, _, obj, _ = sc.ray_cast(dg, cpos + d * t, d, distance=dist - t)
        if not hit: return False
        if hands_block and own_near is not None and own is not None and (obj.name.startswith(PASS_THRU) or (obj.parent is own and _near_hand(own, loc))) and (loc - target).length > 0.05:
            _LAST_BLOCK = obj.name; return True   # 自己的手、手机挡在脸前（举着手机看/自拍）
        if own_near is not None and own is not None and obj.parent is own and ((loc - target).length < own_near or any(k in obj.name for k in ('hair', 'scalp', 'eyebrow', 'eyelash', 'teeth', 'high-poly'))): t = (loc - cpos).length + 0.01; continue   # 自己的头发不算挡（拍背影时后脑勺当然在脸前面）   # 物件特写：手本身不算挡，胳膊、身子挡在前面才算
        if obj.name.startswith(PASS_THRU) and (loc - cpos).length < 0.3: _LAST_BLOCK = obj.name; return True   # 手机贴在镜头前（自拍举着的手机离镜头 9cm，画面一片黑）
        if obj.name.startswith(PASS_THRU) or (own_near is None and own is not None and obj.parent is own): t = (loc - cpos).length + 0.01; continue
        if _hideable(obj.name):
            _HIDE_ACC.add(obj.name); t = (loc - cpos).length + 0.01; continue   # 书架、梯子、床柱挡脸：本拍移走（原来直接判不合格，宿舍里几乎所有候选都不合格）
        _LAST_BLOCK = obj.name
        return True
    return False

def _foreground(sc, dg, cam, cpos, depth, ignore=()):
    """画面里 5×3 条视线，depth 之前就撞上不可移走的东西（门、墙角、别人）的比例。
    原来只查到脸的一条线：脸露出来了，但半个画面是门框/墙/床架（s01 宿舍多个镜头）"""
    M = cam.matrix_world; fr_ = cam.data.view_frame(scene=sc); bad = 0.0; n = 0
    for i in range(5):
        for j in range(3):
            u, v = 0.1 + 0.2 * i, 0.2 + 0.3 * j
            top = fr_[3].lerp(fr_[0], u); bot = fr_[2].lerp(fr_[1], u); pt = M @ bot.lerp(top, v)
            d = (pt - cpos).normalized(); t = 0.02; n += 1
            while t < depth:
                hit, loc, _, _, obj, _ = sc.ray_cast(dg, cpos + d * t, d, distance=depth - t)
                if not hit: break
                nm = obj.name
                if nm.startswith(PASS_THRU) and (loc - cpos).length < 0.3: bad += 1; break
                if nm.startswith(PASS_THRU): t = (loc - cpos).length + 0.01; continue
                if any(k in nm for k in NOT_OBSTRUCT): break
                if _hideable(nm): _HIDE_ACC.add(nm); t = (loc - cpos).length + 0.01; continue
                if obj.parent is not None and obj.parent.type == 'ARMATURE':
                    hd_ = (loc - cpos).length
                    if hd_ < 0.3: bad += 1.0   # 镜头贴在（任何人的）身上：画面一大块衣服（手部特写镜头贴着林晓的肚子）
                    elif obj.parent not in ignore: bad += 0.4
                    elif hd_ < depth - 0.06: bad += 0.7   # 被摄主体自己的身体挡在目标前面（物件特写时手前面是外套）
                    break   # 前景里有别人：轻微扣分（过肩镜头本来就有）
                bad += 1; break
    return bad / n

_LAST_BLOCK = ''; FAIL_LOG = []   # 候选机位不合格的原因（CAM FALLBACK 时打印，方便查）
LAST_SEV = [0]   # 最近一次不合格有多严重：镜头在人身体里 3 > 被挡/前景遮挡 2 > 出画/没朝镜头 1（都不合格时挑最轻的）
def _fail(why, fr):
    FAIL_LOG.append('f%d %s' % (fr, why))
    LAST_SEV[0] = 3 if '身体里' in why else (2 if ('挡' in why) else 1)
    return False

def shot_ok(cam, rigs, watch, subj, f0, f1, targets=None, moving=(), back=False):
    """候选机位是否可用：说话的人脸朝镜头、在画面里、没被挡（墙、家具、别人）；所有主体都在画面里；镜头不在任何人身体里；
    画面前景不能大片被门框/墙/床架占住。三个检查帧里，「在画面里」「脸朝镜头」允许一帧不满足（转身、抬手的过程）。
    targets：物件特写时的目标点函数（返回世界坐标），只要求它在画面里、视线不被挡；
    moving：本拍起身/走动并且会加跟拍约束的人，不查是否在画面里"""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene; frames = (f0, (f0 + f1) // 2, f1); soft = 0   # 镜头第一帧就是观众看到的第一帧（原来从 f0+2 查，开头一帧镜头卡在头发里）
    for fr in frames:
        sc.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); cpos = cam.matrix_world.translation
        for r in rigs.values():
            rh = r.matrix_world @ r.pose.bones['root'].head; top = poses.head_pos(r).z + 0.15
            if Vector((cpos.x - rh.x, cpos.y - rh.y)).length < 0.3 and cpos.z < top: return _fail('镜头在人身体里', fr)
        rgt = cam.matrix_world.to_3x3() @ Vector((1, 0, 0)); upc = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
        if targets is not None:
            for tf, own in targets:
                tp = tf(); v = world_to_camera_view(sc, cam, tp)
                if v.z <= 0 or not (0.1 < v.x < 0.9 and 0.1 < v.y < 0.9):
                    soft += 1
                    if soft > 1: return _fail('物件出画 v=(%.2f,%.2f,%.2f)' % tuple(v), fr)
                    continue
                if _blocked(sc, dg, cpos, tp, own, 0.02, own_near=0.14, hands_block=False): return _fail('物件被 %s 挡' % _LAST_BLOCK, fr)   # 本人身体也算挡（手部特写镜头放在身体另一侧，拍到一大块衣服，2026-11-22）
            if targets:
                fg = _foreground(sc, dg, cam, cpos, (targets[0][0]() - cpos).length - 0.12, [o_ for _, o_ in targets if o_ is not None])
                if fg > 0.34: return _fail('前景遮挡 %.2f' % fg, fr)
            continue
        miss = False
        for s_ in subj:
            hp = poses.head_pos(rigs[s_]); v = world_to_camera_view(sc, cam, hp)
            if s_ not in moving and (v.z <= 0 or not (0.05 < v.x < 0.95 and 0.05 < v.y < 0.88)):
                miss = True; FAIL_LOG.append('f%d %s 头出画 v=(%.2f,%.2f,%.2f)' % ((fr, s_) + tuple(v))); continue
            if v.z <= 0: continue
            fd_, hc_ = face_dir(rigs[s_]); fp = hc_ + fd_ * 0.09   # 瞄脸面（头骨根部在后颈，躺着时埋在枕头里，原来总判成被枕头/床垫挡）
            for off in (Vector(), rgt * 0.08, -rgt * 0.08, upc * 0.08, upc * 0.035, -upc * 0.035, -upc * 0.07):   # 七条线：一两条线会从梯子横杆（3cm 粗）的缝里穿过去
                if _blocked(sc, dg, cpos, (hc_ if back else fp) + off, rigs[s_], 0.03, own_near=(None if back else 0.16)): return   # back：背影镜头查头部中心、自己的身体不算 _fail('%s 脸被 %s 挡' % (s_, _LAST_BLOCK), fr)
        for s_ in watch:
            fd, head = face_dir(rigs[s_]); to_cam = (cpos - head).normalized()
            if fd.dot(to_cam) < 0.15:
                miss = True; FAIL_LOG.append('f%d %s 没朝镜头 %.2f' % (fr, s_, fd.dot(to_cam))); continue
            t, dist = 0.05, (head - cpos).length - 0.15; d = (head - cpos).normalized()
            while t < dist:
                hit, loc, _, _, obj, _ = sc.ray_cast(dg, cpos + d * t, d, distance=dist - t)
                if not hit: break
                if obj.parent is not None and obj.parent.type == 'ARMATURE':
                    if obj.parent is not rigs[s_] and not obj.name.startswith('prop_'): return _fail('%s 被别人 %s 挡' % (s_, obj.name), fr)
                t = (loc - cpos).length + 0.01
        if miss:
            soft += 1
            if soft > 1: LAST_SEV[0] = 1; return False
        if subj:   # 三帧都查：走动的人中间帧离镜头近，只查中间帧会漏掉开头挡在前面的墙（s01 陈瑶进门）
            depth = min((poses.head_pos(rigs[s_]) - cpos).length for s_ in subj) - 0.35   # 查到人跟前（原来只查 80% 距离，紧挨着人的书架背板漏掉了）
            fg = _foreground(sc, dg, cam, cpos, depth, [rigs[s_] for s_ in subj])
            if fg > 0.34: return _fail('前景遮挡 %.2f' % fg, fr)
    return True

def clear_est_view(cam, f0, f1, near=15.0):
    """空镜机位：在画面里均匀打 9×5 条视线，近处（near 米内）挡住视线的可移走物件在本拍隐藏"""
    sc = bpy.context.scene; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    M = cam.matrix_world; o = M.translation; fr = cam.data.view_frame(scene=sc)
    hidden = set()
    for i in range(9):
        for j in range(5):
            u, v = i / 8, j / 4
            top = fr[3].lerp(fr[0], u); bot = fr[2].lerp(fr[1], u); pt = M @ bot.lerp(top, v)
            d = (pt - o).normalized(); t = 0.1
            while t < near:
                hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + d * t, d, distance=near - t)
                if not hit: break
                if obj.name.startswith(HIDEABLE): hidden.add(obj.name); t = (loc - o).length + 0.05; continue
                break
    if hidden: hide_range(sorted(hidden), f0, f1); print('EST CLEAR', cam.name, len(hidden), flush=True)

OBJ_CLOSE = {'phone': ('smartphone', 'phone screen', 'his phone', 'her phone', 'the phone'), 'hands': ('hands', 'hand ', 'fingers', 'the table', 'the desk', 'window table'),
             'feet': ('feet', 'foot')}

def object_target(en, rigs, subj, phones):
    """剧本写的是物件特写（'close-up of …' 且说的是手机/手/桌面/脚）时，返回 (目标点函数, 所属角色骨架)；否则 None"""
    e = (en or '').lower()
    if 'close-up of' not in e and 'close-up over' not in e: return None
    who = subj[0] if subj else None
    if who is None: return None
    rig = rigs[who]
    def wrist():   # 手掌中间（手腕被袖口包着，瞄手腕总判成被外套挡）
        wb = rig.pose.bones['wrist.R']; h_ = rig.matrix_world @ wb.head; t_ = rig.matrix_world @ wb.tail
        return t_ + (t_ - h_).normalized() * 0.05
    if any(k in e for k in OBJ_CLOSE['feet']):
        return (lambda: rig.matrix_world @ rig.pose.bones['foot.L'].head), rig
    if any(k in e for k in OBJ_CLOSE['phone']):
        held, rest = phones.get(who, (None, None))
        if 'pillow' in e and rest is not None: return (lambda: rest.matrix_world.translation.copy()), None
        return wrist, rig
    if any(k in e for k in ('table', 'desk')):   # 桌面特写：对准手前方 20cm 的桌面（对准手腕时镜头被身子挡，拍到一大块外套，s02 窗边桌）
        def on_table():
            fd = face_dir(rig)[0]; fd.z = 0
            fd = fd.normalized() if fd.length > 1e-3 else Vector((0, -1, 0))
            return wrist() + fd * 0.2 - Vector((0, 0, 0.03))
        return on_table, rig
    if any(k in e for k in OBJ_CLOSE['hands']): return wrist, rig
    return None

FIXED_ID = {'lin': 1, 'chen': 2, 'zhou': 3, 'wang': 4, 'mom': 5, 'classA': 6, 'classB': 7}   # 每个角色在全片里的固定遮罩编号

def assign_ids():
    """物体编号（遮罩用）：主角 1~7 固定；路人 10 起；手机 15；场景 0。返回 {编号: 名字}"""
    ids, nxt = {}, 10
    for rig in sorted((o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name.endswith('_rig')), key=lambda o: o.name):
        cid = rig.name[:-4]; k = FIXED_ID.get(cid)
        if k is None: k = nxt; nxt += 1
        for c in rig.children_recursive:
            if c.type in ('MESH', 'CURVES'): c.pass_index = k
        ids[k] = NAME.get(cid, cid)
    for o in bpy.data.objects:
        if o.name.startswith(('prop_phonebody_', 'prop_screen_')): o.pass_index = 15
    ids[15] = '手机'
    return ids

OBSTACLE = ('ext_trunk', 'ext_crown', 'ext_lamp', 'ext_bench', 'ext_bin', 'ext_sign', 'ext_bike', 'ext_column')

def _xy_box(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((sum(p.x for p in bb) / 8, sum(p.y for p in bb) / 8)), bb

def clear_walk_path(a, b):
    """路人走的直线上挡着的树、路灯、长椅等：整段移走（同一棵树的树干、树冠一起）。原来路人从树干、树冠里穿过去（s04，2026-11-23）"""
    from mathutils.geometry import intersect_point_line
    ab = b - a
    if ab.length < 0.1: return
    obs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(OBSTACLE) and not o.hide_render]
    hide = set()
    for o in obs:
        c, bb = _xy_box(o)
        if min(p.z for p in bb) > 1.95: continue                     # 头顶上方的树冠不碍事
        rad = max(max(p.x for p in bb) - min(p.x for p in bb), max(p.y for p in bb) - min(p.y for p in bb)) / 2 + 0.3
        q, t = intersect_point_line(c, a, b); t = max(0.0, min(1.0, t))
        if (c - (a + ab * t)).length < rad: hide.add(o.name)
    for n in list(hide):   # 同一棵树：树干和树冠水平位置相近
        if not n.startswith(('ext_trunk', 'ext_crown')): continue
        c0, _ = _xy_box(bpy.data.objects[n])
        for o in obs:
            if o.name.startswith(('ext_trunk', 'ext_crown')) and (_xy_box(o)[0] - c0).length < 0.8: hide.add(o.name)
    for n in hide:
        ob = bpy.data.objects[n]
        if ob.animation_data and ob.animation_data.action:   # 机位临时移走时打过 hide_render 关键帧，不删的话换机位又冒出来
            for fc in [fc for fc in ob.animation_data.action.fcurves if fc.data_path in ('hide_render', 'hide_viewport')]: ob.animation_data.action.fcurves.remove(fc)
        ob.hide_render = True; ob.hide_viewport = True
    if hide: print('WALK PATH CLEAR', len(hide), sorted(hide)[:6], flush=True)

def add_walkers(walkers, f_end, clip):
    """外景背景里来往的路人学生：按设定时刻出发、动捕走路；片段结束前走不完就走到哪算哪（只烘焙需要的帧）"""
    for cid, p0, p1, t0 in walkers:
        if not os.path.exists(os.path.join(config.CAST, cid + '.blend')): continue
        fs = 1 + round(t0 * FPS)
        if fs >= f_end - 10: continue      # 先判断再加载：原来先加载再跳过，没摆姿势的路人张着双臂站在场景原点（路中间），2026-11-22 全片检查发现
        rig = append_cast(cid)
        d = Vector(p1) - Vector(p0)
        yaw = math.degrees(math.atan2(-d.x, d.y)) + 180
        frames, _, _ = retarget.walk_plan(clip, rig, p0, p1)
        frac = min(1.0, (f_end - fs) / max(1, frames))                      # 只走到片段结束
        q1 = Vector(p0) + d * frac
        clear_walk_path(Vector(p0[:2]), q1.xy)
        poses.apply_state(rig, dict(pos=(p0[0], p0[1], 0), yaw=yaw, base='stand', arms='down'), 1)
        retarget.walk(clip, rig, fs, p0, (q1.x, q1.y))
        if fs > 1:   # 出发前不在画面里（不会有人杵在路边等着）
            for c in rig.children:
                for fr, v in ((1, True), (fs - 1, True), (fs, False)):
                    c.hide_render = v; c.keyframe_insert('hide_render', frame=fr)
        life.add_idle(rig, sum(map(ord, cid)))
        life.hands(rig, 1)

GROUNDISH = ('step', 'landing', 'stair', 'platform', 'stage', 'curb', 'podium', 'ground', 'floor', 'track', 'plaza', 'path', 'road', 'grass', 'lawn', 'pavement')

def ground_follow(rigs, f_start, f_end):
    """站着/走路的人脚不能低于脚下的地面：台阶、门口平台、路沿。走路动捕和站位都按 z=0 摆，
    s04 林晓走上图书馆台阶时腿整个埋进台阶、站在平台上埋到腰（2026-11-23）。逐帧算要抬多少，前后平滑后补关键帧。
    坐着/躺着（髋部离脚不到 0.7m）不动：坐在台阶上的人已经按台阶落座了。"""
    sc = bpy.context.scene
    grounds = [o for o in bpy.data.objects if o.type == 'MESH' and any(k in o.name.lower() for k in GROUNDISH)]
    if not any(max((o.matrix_world @ Vector(c)).z for c in o.bound_box) > 0.04 for o in grounds): return   # 场景里没有高出地面的台阶/平台
    raise_ = {r: [0.0] * (f_end + 2) for r in rigs}; hipz = {r: [0.0] * (f_end + 2) for r in rigs}
    for f in range(f_start, f_end + 1):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        for r in rigs:
            M = r.matrix_world; pb = r.pose.bones
            if pb.get('foot.L') is None: continue
            feet = [M @ pb['foot.' + s].head for s in 'LR'] + [M @ pb['foot.' + s].tail for s in 'LR']
            z0 = M.translation.z; bd = r.data.bones   # 鞋底高度 = 踝/脚尖骨骼点 − 它们静止时离地的高度（骨骼点本身比鞋底高约 20cm，原来直接用骨骼点，每级台阶都抬得不够）
            soles = [feet[k].z - ((M @ (bd['foot.' + 'LRLR'[k]].head_local if k < 2 else bd['foot.' + 'LRLR'[k]].tail_local)).z - z0) for k in range(4)]
            fz = min(soles); hip = M @ pb['root'].head; hipz[r][f] = hip.z
            if hip.z - fz < 0.7: continue
            need = 0.0
            for p in feet:   # 每只脚正下方（从鞋底上方 0.9m 往下）第一块地面的高度；扶手、栏杆等非地面物体穿过去
                o = Vector((p.x, p.y, fz + 1.4)); t = 0.0   # 从鞋底上方 1.4m 往下（平台高 1.2m，起点低于平台顶就看不到顶面）
                while t < 1.7:
                    hit, loc, _, _, obj, _ = sc.ray_cast(dg, o + Vector((0, 0, -t)), Vector((0, 0, -1)), distance=1.7 - t)
                    if not hit: break
                    if (obj.parent is not None and obj.parent.type == 'ARMATURE') or obj.name.startswith('prop_') or obj.hide_render: t = o.z - loc.z + 0.005; continue
                    if any(k in obj.name.lower() for k in GROUNDISH): need = max(need, loc.z - fz); break
                    t = o.z - loc.z + 0.005
            raise_[r][f] = max(0.0, need)
            if os.environ.get('V11_GDEBUG') and f % 6 == 0: print('GDBG', r.name, f, 'fz %.2f hip %.2f need %.2f' % (fz, hip.z, need), flush=True)
    for r, arr in raise_.items():
        if max(arr) < 0.01: continue
        sm = arr[:]
        for f in range(f_start, f_end + 1):   # 先取前后 4 帧最大值（不许中途陷下去），再平均（台阶一级级上去、不跳）
            sm[f] = max(arr[max(f_start, f - 4):min(f_end, f + 4) + 1])
        sm2 = sm[:]
        for f in range(f_start, f_end + 1):
            w = sm[max(f_start, f - 3):min(f_end, f + 3) + 1]; sm2[f] = sum(w) / len(w)
            hz = hipz[r]; near = [arr[g] for g in range(max(f_start, f - 2), min(f_end, f + 2) + 1) if abs(hz[g] - hz[f]) < 0.1]
            sm2[f] = min(sm2[f], max(near) + 0.02)   # 原动画自己已经升上去的帧不再叠加（走到终点时原走位跳上平台，叠加后冲高到 2.8m）
        root = r.pose.bones['root']; todo = []
        for f in range(f_start, f_end + 1):   # 先把每帧该到的位置全算好再写关键帧（边算边写的话，后一帧的基准会被前一帧新插的键带高，抬两次）
            if sm2[f] < 0.004 and (f == f_start or sm2[f - 1] < 0.004) and (f == f_end or sm2[f + 1] < 0.004): continue
            sc.frame_set(f)
            Mw = r.matrix_world @ root.matrix; Mw.translation.z += sm2[f]
            root.matrix = r.matrix_world.inverted() @ Mw; todo.append((f, root.location.copy()))
        for f, loc_ in todo:
            root.location = loc_; root.keyframe_insert('location', frame=f, group='root')
        n = len(todo)
        print('GROUND FOLLOW', r.name, 'max %.2f m' % max(arr), 'frames', n, flush=True)

def climb_path(start, new):
    """从上铺爬梯子下来的分步状态 [(相对帧, 状态)]：梯子位置取离起点最近的梯子横档"""
    rungs = [o for o in bpy.data.objects if o.name.startswith('furn_ladder_') and 'rail' not in o.name]
    sp = Vector(start['pos'][:2])
    near = min(rungs, key=lambda o: (o.matrix_world.translation.xy - sp).length)
    tag = near.name.split('.')[0]
    mine = [o for o in rungs if o.name.split('.')[0] == tag]
    lad = sum((o.matrix_world.translation for o in mine), Vector()) / len(mine); lad.z = 0
    tops = sorted({round(max((o.matrix_world @ Vector(c)).z for c in o.bound_box), 3) for o in mine})
    foot = Vector(new['pos'][:2] + (0,))
    out = (foot - lad); out.z = 0; out.normalize()                         # 从梯子指向房间（站梯子的人在这一侧）
    face_room = math.degrees(math.atan2(out.x, -out.y))                     # 朝向角 yaw 的面朝方向 = (sin yaw, -cos yaw)
    face_ladder = (face_room + 180) % 360
    t, steps = 0, []
    edge = lad - out * 0.28
    t += round(0.7 * FPS); steps.append((t, dict(start, pos=(edge.x, edge.y, start['pos'][2]), yaw=face_room, base='sit_bed', arms='down')))
    t += round(0.8 * FPS); steps.append((t, dict(pos=(edge.x, edge.y, start['pos'][2]), yaw=face_ladder, base='crouch', arms='down', lean=12)))   # 蹲着时手放下、身体前倾（上铺离天花板只有 1.28m，直着蹲头顶到天花板）；（举手的爬梯姿势会插进天花板）
    lip = lad - out * 0.06
    t += round(0.5 * FPS); steps.append((t, dict(pos=(lip.x, lip.y, start['pos'][2]), yaw=face_ladder, base='crouch', arms='climb', lean=12)))   # 挪到床沿、手扶梯子   # 先在床上转身蹲好、面朝床里（原来坐着直接接爬梯姿势：转身 180° + 下降同时插值，人斜着飞出去穿过床板，2026-11-23）
    on = lad + out * 0.40   # 离床沿远一点（0.2/0.32 时林晓的肚子顶进床板）
    t += round(0.7 * FPS); steps.append((t, dict(pos=(on.x, on.y, tops[-1]), yaw=face_ladder, base='climbA', arms='climb')))   # 再往后一步踩上最高一级
    for k, z in enumerate(reversed(tops[:-1])):
        t += round(0.42 * FPS); steps.append((t, dict(pos=(on.x, on.y, z), yaw=face_ladder, base='climbB' if k % 2 == 0 else 'climbA', arms='climb')))
    t += round(0.45 * FPS); steps.append((t, dict(pos=(on.x, on.y, 0.0), yaw=face_ladder, base='stand', arms='climb')))
    t += round(0.6 * FPS); steps.append((t, new))
    return steps

# ---------------- 主装配 ----------------
def build_segment(seg_id, scene, set_name, beats):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sets._cube = None; sets._MATS.clear(); sets._PROTO.clear()
    info = sets.build(set_name); marks = info['marks']; bounds = info.get('bounds')
    realism.apply_hdri(set_name)                       # 真实全景光照与反射（替代纯色/渐变天空）
    sc = bpy.context.scene; sc.render.fps = FPS; sc['v11_set'] = set_name
    B = blocking.get(scene['id'])
    chars = sorted({c for bt in beats for c in bt['chars']} | set(B.get('extras', {}).get(set_name, [])))
    rigs = {CID[c]: append_cast(CID[c]) for c in chars}
    init = B.get('init_' + set_name) or B['init']
    phones = {}
    talk_spans = {}
    for cid, rig in rigs.items():   # 手上一部（挂手骨）+ 放下的一部（固定位置），按拿起/放下切换显示
        held = make_phone(cid + '_held'); held.parent = rig; held.parent_type = 'BONE'; held.parent_bone = 'wrist.R'
        held.location = (0.0, 0.06, 0.03)
        con = held.constraints.new('DAMPED_TRACK'); con.target = rig; con.subtarget = 'head'; con.track_axis = 'TRACK_Z'   # 屏幕始终朝向自己的脸
        con.influence = 0.85
        rest = make_phone(cid + '_rest'); rest.location = B.get('phones', {}).get(cid, (0, -60, -10))
        phones[cid] = (held, rest)
    state = {cid: dict(init.get(cid, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down'))) for cid in rigs}
    for cid, st in state.items(): blocking.resolve(st, marks)
    prev = [sid for sid, s2, L2, _ in segments() if s2['id'] == scene['id'] and L2 == set_name]
    prev = prev[:prev.index(seg_id)] if seg_id in prev else []
    if prev and os.path.exists(os.path.join(config.SHOTS, prev[-1] + '_end.json')):   # 同一场戏回到同一地点：接着上一段结束时的状态
        saved = json.load(open(os.path.join(config.SHOTS, prev[-1] + '_end.json'), encoding='utf-8'))
        for cid in state:
            if cid in saved: state[cid] = dict(saved[cid], pos=tuple(saved[cid]['pos']))
    f = 1; side = B.get('side', 1); cam_prev = None
    timeline = []; hand_ev = {cid: [] for cid in rigs}
    WALK = os.path.join(MOCAP, '07_01.bvh')
    LAG = 4                                    # 手臂比躯干晚 4 帧（≈0.17 秒）到位
    TURN = 6                                   # 走路拐弯时的转身帧数
    def grips(st):
        a = st.get('arms', 'down'); prop = poses.ARMS[a].get('prop')
        return (prop in ('hand', 'ear', 'tray') or a == 'cup', a in ('phone2', 'phone_up', 'tray'))
    def heading(p0, p1, fallback):
        d = Vector(p1[:2]) - Vector(p0[:2])
        return math.degrees(math.atan2(-d.x, d.y)) + 180 if d.length > 0.05 else fallback
    for bt in beats:
        spec = B['beats'].get(bt['id'], {})
        sync = [l for o, l, y in audio_plan(bt) if y]
        speaker = CID.get(TEXT[sync[0]][0]) if sync else None
        # 0) 规划：每个角色本拍做什么、真人需要多久（走路按动捕原速，不再为塞进拍子而加速）
        plans, need = {}, 0
        for cid, rig in rigs.items():
            act = spec.get(cid)
            if act is None: continue
            start, new = state[cid], blocking.resolve(dict(state[cid], **act[1]), marks)
            kind = act[0]
            d = (Vector(new['pos']) - Vector(start['pos'])).length
            if kind in ('set', 'blend') and 0.45 < d <= 1.6: kind = 'walk'              # 挪了一段距离却没写走路：走过去
            if kind == 'set' and (d > 1.6 or bt['cam'] in ('new', 'est')): kind = 'snap'  # 时间省略（换场、隔了一段时间）
            if kind == 'walk' and d < 0.3: kind = 'blend'
            if (kind in ('set', 'blend') and start.get('base') in ('sit_bed', 'lie', 'hug_knees') and start['pos'][2] > 1.0
                    and new.get('base') == 'stand' and new['pos'][2] < 0.3):   # 从上铺下到地面：走梯子，不能直接穿过床板
                steps = climb_path(start, new)
                plans[cid] = ('climb', new, steps); need = max(need, steps[-1][0] + LAG + 4)
            elif kind in ('set', 'blend'):
                tt = max(act[2] if kind == 'blend' and len(act) > 2 else 0, poses.trans_time(start, new))
                plans[cid] = ('blend', new, round(tt * FPS)); need = max(need, round(tt * FPS) + LAG + 18)   # +站稳/坐定的晃动
            elif kind == 'walk':
                route = nav.plan(start['pos'], new['pos'])               # 绕开家具的路线（拐点）
                legs = [(route[i], route[i + 1]) for i in range(len(route) - 1) if (Vector(route[i + 1]) - Vector(route[i])).length > 0.05]
                if not legs: legs = [(start['pos'][:2], new['pos'][:2])]
                wyaw = heading(legs[0][0], legs[0][1], start['yaw'])
                stand = dict(start, base='stand', arms='down', yaw=wyaw); stand.pop('reach', None)
                prep = round(poses.trans_time(start, stand) * FPS)
                wf = sum(retarget.walk_plan(WALK, rig, a_, b_)[0] for a_, b_ in legs) + TURN * (len(legs) - 1)
                end_stand = dict(stand, pos=new['pos'], yaw=heading(legs[-1][0], legs[-1][1], wyaw))
                settle = max(10, round(poses.trans_time(end_stand, new) * FPS))
                plans[cid] = ('walk', new, (stand, prep, wf, settle, legs)); need = max(need, prep + 5 + wf + settle + LAG + 4)
            else:
                plans[cid] = ('snap', new, 0)
        n = max(beat_frames(bt), need); f0, f1 = f, f + n - 1
        # 1) 走位/姿态：拍开头的状态（继承上一拍）+ 本拍的变化
        walking = {}; looks = {}
        for cid, rig in rigs.items():
            if cid not in [CID[c] for c in bt['chars']] and cid not in spec:
                poses.apply_state(rig, blocking.with_look(state[cid], None), f0); continue
            start = dict(state[cid])
            if speaker and cid != speaker and speaker in rigs: start['look'] = poses.head_pos(rigs[speaker])
            elif speaker == cid:
                lst = [o for o in rigs if o != cid and o in [CID[c] for c in bt['chars']]]
                start['look'] = poses.head_pos(rigs[lst[0]]) if lst else None
            looks[cid] = start.get('look')
            if cid not in plans:
                poses.apply_state(rig, start, f0); poses.apply_state(rig, start, f1)
                hand_ev[cid].append((f0, grips(start)))
                continue
            kind, new, arg = plans[cid]
            new_l = dict(new, look=start.get('look'))
            t_change = f0
            if kind == 'snap':       # 时间省略：拍开头已是新状态
                poses.apply_state(rig, new_l, f0); poses.apply_state(rig, new_l, f1)
            elif kind == 'blend':    # 真人速度过渡，躯干先动、手臂跟随；起身/坐下按重心移动分阶段（符合物理）
                fe = min(f1 - LAG - 14, f0 + max(6, arg)); fe = max(f0 + 6, fe)
                sb_, nb_ = start.get('base', 'stand'), new.get('base', 'stand')
                seatish = lambda b_: poses.SUPPORTED.get(b_) == 'seat'
                fw = Vector((math.sin(math.radians(new['yaw'])), -math.cos(math.radians(new['yaw'])), 0))
                poses.apply_state(rig, start, f0, lag=LAG)
                if seatish(sb_) and nb_ == 'stand':
                    # 起身（按力学分阶段）：前倾、双手挪到膝盖上方撑住 -> 手撑腿蹬起（手按在腿上、手臂随身体升高伸直）
                    # -> 臀部离开椅面后松手，手臂靠惯性甩下（回弹缓动略过头再回来）-> 直起身略后仰 -> 站稳
                    T = fe - f0; p_ = Vector(start['pos']) + fw * 0.12
                    poses.apply_state(rig, dict(start, base='sit_lean', arms='push', look=None), f0 + round(T * 0.28))
                    poses.apply_state(rig, dict(new_l, base='rise', pos=tuple(p_), arms='push', look=None), f0 + round(T * 0.55))
                    poses.apply_state(rig, dict(new_l, lean=-4), f0 + round(T * 0.82), lag=LAG)
                    poses.apply_state(rig, dict(new_l, lean=1.5), fe + 5); poses.apply_state(rig, new_l, fe + 12)
                elif sb_ == 'stand' and seatish(nb_):    # 坐下：前倾、屈膝放低 -> 坐实 -> 往后靠一下再坐定
                    p_ = Vector(new['pos']) + fw * 0.12
                    poses.apply_state(rig, dict(new_l, base='rise', pos=tuple(p_), arms=start.get('arms', 'down')), f0 + round((fe - f0) * 0.55), lag=LAG)
                    poses.apply_state(rig, dict(new_l, lean=-3), fe, lag=LAG); poses.apply_state(rig, new_l, fe + 9)
                else:
                    poses.apply_state(rig, new_l, fe, lag=LAG)
                poses.apply_state(rig, new_l, f1)
                t_change = (f0 + fe) // 2
            elif kind == 'climb':    # 挪到床边 -> 转身面向梯子 -> 双手扶梯一级级踩下来 -> 落地
                prev_f = f0; poses.apply_state(rig, start, f0, lag=LAG)
                for k_, (fr_, st_) in enumerate(arg):
                    fk = min(f1 - LAG, f0 + fr_); poses.apply_state(rig, dict(st_, look=None) if k_ < len(arg) - 1 else new_l, fk, lag=LAG if k_ in (0, len(arg) - 1) else 1)
                poses.apply_state(rig, new_l, f1)
                t_change = f0 + arg[-1][0]
            elif kind == 'walk':     # 先起身/转身 -> 动捕走路（整步循环）-> 停步、转向、摆好姿势
                stand, prep, wf, settle, legs = arg
                p0, p1 = start['pos'], new['pos']; walking[cid] = (Vector(p0[:2] + (0,)), Vector(p1[:2] + (0,)))
                poses.apply_state(rig, start, f0, lag=LAG)
                ws = f0 + prep + 5
                if prep: poses.apply_state(rig, dict(stand, lean=4), f0 + prep, lag=0)   # 起步前身体先微微前倾（预备动作）
                for li, (a_, b_) in enumerate(legs):     # 拐点之间留 TURN 帧，由插值完成转身
                    ws += retarget.walk(WALK, rig, ws, a_, b_) + (TURN if li < len(legs) - 1 else 0)
                we = ws
                end_yaw = heading(legs[-1][0], legs[-1][1], stand['yaw'])
                poses.apply_state(rig, dict(stand, pos=new['pos'], yaw=end_yaw, lean=5), min(f1 - LAG - 2, we + 4))   # 急停：惯性让上身往前一冲
                poses.apply_state(rig, new_l, min(f1 - LAG, we + settle), lag=LAG); poses.apply_state(rig, new_l, f1)
                t_change = we
            state[cid] = new
            # 手机：在手上 or 放下；手指握持随之变化
            prop = poses.ARMS[new.get('arms', 'down')].get('prop')
            show_phone(phones[cid], t_change, prop in ('hand', 'ear'))
            hand_ev[cid].append((f0, grips(start))); hand_ev[cid].append((t_change, grips(new)))
        # 1b) 生活小动作：不说话的人在较长的镜头里做一次自己的习惯动作；说长句的人换一种说话手势（各有性格）
        for cid, rig in rigs.items():
            if cid in plans: continue
            st = state[cid]; base = st.get('base', 'stand'); seated = poses.SUPPORTED.get(base) == 'seat'
            if base not in ('stand', 'stand_rest') and not seated: continue
            if st.get('arms', 'down') not in ('down', 'thighs', 'lap', 'desk', 'pocket', 'pockets', 'gesture'): continue
            talking = cid == speaker
            if n < (3.0 if talking else 3.6) * FPS: continue
            pool = TALK.get(cid) if talking else HABITS.get(cid, {}).get('sit' if seated else 'stand')
            if not pool: continue
            act_ = pool[sum(map(ord, bt['id'] + cid)) % len(pool)]
            if act_ == st.get('arms'): continue
            lk = looks.get(cid); tr = round(0.75 * FPS)
            fa, fb = f0 + round(n * 0.28), f0 + round(n * 0.70)
            poses.apply_state(rig, dict(st, look=lk), fa, lag=LAG)
            poses.apply_state(rig, dict(st, arms=act_, look=lk), fa + tr, lag=LAG)
            poses.apply_state(rig, dict(st, arms=act_, look=lk), fb, lag=LAG)
            poses.apply_state(rig, dict(st, look=lk), min(f1 - LAG, fb + tr), lag=LAG)
        # 2) 口型
        for off, lid, y in audio_plan(bt):
            if not y: continue
            cid = CID.get(TEXT[lid][0])
            if cid in rigs and os.path.exists(os.path.join(VIS, lid + '.json')):
                face.apply_rhubarb(rigs[cid], os.path.join(VIS, lid + '.json'), f0 + off * FPS, FPS)
                talk_spans.setdefault(cid, []).append((round(f0 + off * FPS), round(f0 + (off + META[lid]['dur']) * FPS)))   # 说话时头和上身跟着动（life.talk_motion）
        # 3) 机位：cont 沿用上一机位，其余按描述自动生成
        def faces_away(cam):   # 说话人背对（或侧背对）这台机位：看不见嘴
            if not speaker or speaker not in rigs: return False
            st = state[speaker]
            fd = poses.body_rot(st['yaw'], poses.BASE[st.get('base', 'stand')]['pitch']) @ Vector((0, -1, 0))
            sc.frame_set(f1); to_cam = (cam.matrix_world.translation - poses.head_pos(rigs[speaker])).normalized()
            return fd.dot(to_cam) < 0.15
        from bpy_extras.object_utils import world_to_camera_view
        def subj_ids():
            return ([speaker] if speaker in rigs else []) or [CID[c] for c in bt['chars'] if CID[c] in rigs][:2]
        def out_of_frame(cam):   # 主体（头部）在本拍任意时刻跑出画面：沿用旧机位就会拍空
            for fr in (f0, (f0 + f1) // 2, f1):
                sc.frame_set(fr)
                for s_ in subj_ids():
                    v = world_to_camera_view(sc, cam, poses.head_pos(rigs[s_]))
                    if v.z <= 0 or not (0.06 < v.x < 0.94 and 0.06 < v.y < 0.86): return True   # 头顶要留出空间（头心在 0.86 以上，头顶就被切了）
            return False
        protect = {poses.LAST_SUPPORT.get(rigs[c].name) for c in rigs if state[c].get('base') in poses.SUPPORTED} - {None}
        if bt['cam'] == 'cont' and cam_prev is not None and not walking and not faces_away(cam_prev) and not out_of_frame(cam_prev):
            cam = cam_prev
            cam.keyframe_insert('location', frame=f1)
            for n in cam.get('hidden', []):   # 沿用机位时，之前移走的遮挡物在本拍也保持移走（原先会在拍子交界处冒回来挡住镜头）
                ob = bpy.data.objects[n]
                for fr, v in ((f0 - 1, True), (f0, True), (f1 + 1, False)):
                    ob.hide_render = v; ob.keyframe_insert('hide_render', frame=fr)
        else:
            if bt['cam'] == 'est':
                loc, tgt, lens = next(iter(info['cams'].values()))
                cam = bpy.data.objects.new('cam_' + bt['id'], bpy.data.cameras.new('cam_' + bt['id'])); sc.collection.objects.link(cam)
                cam.location = loc; cam.data.lens = lens; cam.data.clip_end = 400
                cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
                camera_move(cam, Vector(loc), Vector(tgt), 'WS', 'est', f0, f1, 1)   # 空镜缓推
                clear_est_view(cam, f0, f1)   # 空镜：离镜头近、挡住画面的树/路灯等临时移走（原来开场空镜被一棵大树占了半个画面）
            else:
                subj = [speaker] if speaker in rigs else [CID[c] for c in bt['chars'] if CID[c] in rigs][:3]
                kind = shot_type(bt.get('en'))
                if kind in ('MS', 'WS'): subj = [CID[c] for c in bt['chars'] if CID[c] in rigs][:3] or subj
                sc.frame_set(f0)
                def _avg_head(r_):   # 头在本拍的平均位置（转头、俯身时头会移开，只对准第一帧，转过来脸就在画面边上，s09 林晓回头）
                    a_ = Vector()
                    for fr_ in (f0, (f0 + f1) // 2, f1): sc.frame_set(fr_); a_ += poses.head_pos(r_)
                    sc.frame_set(f0); return a_ / 3
                pts = [_avg_head(rigs[s]) for s in subj] or [Vector((0, 0, 1.4))]
                obj_t = object_target(bt.get('en'), rigs, subj, phones)   # 「手机/手/桌面/脚的特写」：镜头对准物件，不对准人头
                if obj_t is not None and kind == 'ECU': kind = 'CU'   # 物件特写退半步：0.42m 只拍到一块黑色机身，看不出是什么（枕边手机）
                if obj_t is not None:   # 物件（手、手机）在本拍里会动：瞄开头、中间、结尾三处的平均位置（原来只瞄开头，手一抬就出画）
                    acc = Vector()
                    for fr_ in (f0, (f0 + f1) // 2, f1): sc.frame_set(fr_); acc += obj_t[0]()
                    sc.frame_set(f0); pts = [acc / 3]
                for i, s_ in enumerate(subj):   # 走动中的人：取路径中点，并至少用中景（长距离用全景）
                    if s_ in walking:
                        a_, b_ = walking[s_]; mid = (a_ + b_) / 2; pts[i] = Vector((mid.x, mid.y, pts[i].z))
                        kind = 'WS' if (b_ - a_).length > 3 else ('MS' if kind in ('ECU', 'CU', 'MCU') else kind)
                st0 = state[subj[0]] if subj else dict(yaw=0, base='stand')
                yaw = poses.body_rot(st0['yaw'], poses.BASE[st0.get('base', 'stand')]['pitch']) @ Vector((0, -1, 0))   # 脸的真实朝向（躺着=朝上）
                hu = poses.body_rot(st0['yaw'], poses.BASE[st0.get('base', 'stand')]['pitch']) @ Vector((0, 0, 1))
                if subj and st0.get('base', 'stand') not in ('lie', 'lie_side'):   # 按头的真实朝向（三帧平均）摆机位：人在本拍里转身时，按身体朝向摆的机位全在背后（s01 陈瑶进门）
                    acc = Vector()
                    for fr_, w_ in ((f0, 0.5), ((f0 + f1) // 2, 1.0), (f1, 1.5)): sc.frame_set(fr_); acc += face_dir(rigs[subj[0]])[0] * w_   # 偏向结尾：转头/转身的拍子，观众要看的是转过来之后的脸（s09 林晓回头）
                    sc.frame_set(f0); acc.z *= 0.3
                    if acc.length > 1.5: yaw = acc.normalized()
                watch = [speaker] if speaker in rigs else subj[:1]
                movers = [s_ for s_ in subj if s_ in walking]
                sc.frame_set(f0); hp0 = {s_: poses.head_pos(rigs[s_]) for s_ in subj}
                sc.frame_set(f1)
                movers += [s_ for s_ in subj if s_ not in movers and (abs(poses.head_pos(rigs[s_]).z - hp0[s_].z) > 0.2 or (poses.head_pos(rigs[s_]) - hp0[s_]).length > 0.5)]   # 起身/坐下/挪步：镜头跟着摇
                sc.frame_set(f0); mv_ = movers[:1]
                if obj_t is not None:
                    vfun = lambda c_, a_=f0, b_=f1, t_=obj_t: shot_ok(c_, rigs, [], [], a_, b_, targets=[t_])
                elif 'from behind' in (bt.get('en') or ''):
                    vfun = lambda c_, a_=f0, b_=f1, all_=subj: shot_ok(c_, rigs, [], all_, a_, b_, moving=mv_, back=True)   # 背影：不要求脸朝镜头，但不能被挡
                else:
                    vfun = lambda c_, w_=watch, a_=f0, b_=f1, all_=subj: shot_ok(c_, rigs, w_, all_, a_, b_, moving=mv_)
                cam = place_camera('cam_' + bt['id'], pts, yaw, kind, side, bounds, f0, f1, bt.get('en'), head_up=hu, protect=protect, validate=vfun, own_rigs=[rigs[s_] for s_ in subj])
                if movers:   # 走动的人：镜头跟着摇（真人摄影师的跟拍），不会拍着拍着人走出画面
                    con = cam.constraints.new('TRACK_TO'); con.target = rigs[movers[0]]; con.up_axis = 'UP_Y'   # 保持画面水平（DAMPED_TRACK 会让镜头歪，s10 结尾三人走远时画面倾斜）
                    con.subtarget = 'neck01'   # 跟拍瞄脖子（原来走路的人瞄 spine01，人走近时头被切出画面，s07 林晓）
                    con.track_axis = 'TRACK_NEGATIVE_Z'; con.influence = 0.9; cam['move'] = 'track'
        if cam is not cam_prev:
            m = sc.timeline_markers.new(bt['id'], frame=f0); m.camera = cam
        cam_prev = cam
        sp = screen_plan(bt)
        if sp:   # 手机屏幕：界面在三维屏幕上逐条出现；切到手机特写让观众看清，看完切回人物反应
            beat_c = [CID[x] for x in bt['chars'] if CID[x] in rigs]
            holder = next((c for c in beat_c if poses.ARMS[state[c].get('arms', 'down')].get('prop') in ('hand', 'ear')), None)
            owner = holder or (beat_c[0] if beat_c else None)
            if owner:
                held, rest = phones[owner]
                ph = held if holder or rest.location.y < -50 else rest
                if ph is held and not holder: show_phone(phones[owner], f0, True)
                items = [(round(f0 + o * FPS), SCREEN[s_][0], SCREEN[s_][1]) for o, s_, d in sp]
                phone_ui.build_ui(ph, NAME[owner], items, f1, bt['id'])
                icam = phone_ui.insert_camera(ph, 'cam_%s_phone' % bt['id'])
                fi1 = round(f0 + (sp[-1][0] + sp[-1][2]) * FPS)
                m = sc.timeline_markers.new(bt['id'] + '_ph', frame=items[0][0]); m.camera = icam
                if fi1 < f1: m = sc.timeline_markers.new(bt['id'] + '_re', frame=fi1); m.camera = cam
        timeline.append(dict(id=bt['id'], f0=f0, f1=f1, audio=[(round(f0 + o * FPS), l) for o, l, _ in audio_plan(bt)],
                             screen=[(round(f0 + o * FPS), sid, d) for o, sid, d in screen_plan(bt)],
                             sfx=[s_ for s_ in bt.get('sfx', []) if s_[1] != 'ding'] +          # 评论提示音跟着评论出现的时刻走
                                 [(round(o, 2), 'ding') for o, sid, d in screen_plan(bt) if SCREEN[sid][0].startswith(('网友', '妈妈'))]))
        f = f1 + 1
    ground_follow(list(rigs.values()), 1, f - 1)   # 站着/走路的人脚落到台阶、平台上
    for i, (cid, rig) in enumerate(sorted(rigs.items())):   # 活人感：呼吸、微动、眨眼、眼神、手指
        seed = sum(map(ord, seg_id + cid))
        life.inertia(rig)
        life.add_idle(rig, seed)
        life.talk_motion(rig, talk_spans.get(cid, []), seed + 7)
        life.blinks(rig, 1, f - 1, seed)
        last = None
        for fr, (gr, gl) in sorted(hand_ev[cid]):
            if (gr, gl) != last:
                if last is not None: life.hands(rig, max(1, fr - 4), *last)   # 换手势前保持原样，约 0.3 秒内握住/松开
                life.hands(rig, fr + 4, gr, gl); last = (gr, gl)
        if last is None: life.hands(rig, 1)
    add_walkers(info.get('walkers', []), f - 1, WALK)
    ids = assign_ids()
    json.dump(ids, open(os.path.join(config.SHOTS, seg_id + '_ids.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sc.frame_start, sc.frame_end = 1, f - 1
    sc.camera =sc.timeline_markers[0].camera if sc.timeline_markers else None
    sc['v11_timeline'] = json.dumps(timeline, ensure_ascii=False)
    json.dump({c: {k: (list(v) if isinstance(v, tuple) else v) for k, v in st.items() if k != 'look'} for c, st in state.items()},
              open(os.path.join(config.SHOTS, seg_id + '_end.json'), 'w', encoding='utf-8'), ensure_ascii=False, default=list)
    return timeline

def setup_render(out_dir, w=960, h=540):
    sc = bpy.context.scene
    # 写实渲染：Cycles 路径追踪（GPU/OptiX）+ 降噪；64 采样与 256 采样肉眼无差，单帧数秒
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.render.resolution_x, sc.render.resolution_y = w, h
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    sc.cycles.samples = int(os.environ.get('CY_SAMPLES', 64)); sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6
    if config.PREVIEW:   # 剧情预览：EEVEE 实时引擎，640x360，单帧不到 1 秒
        pw, ph = map(int, os.environ.get('V11_PREVIEW_RES', '640x360').split('x'))   # 云端写实化输入用 960x540（Cycles 渲十几万根发丝每帧 15 秒，太慢）
        sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = pw, ph
        sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    night = any(k in bpy.data.filepath + sc.get('v11_set', '') for k in ('_nt', 'track', 'dusk'))
    sc.view_settings.exposure = 1.3 if night else 0.0          # 夜景提亮，避免整段死黑
    for m in bpy.data.materials:   # 皮肤次表面散射按真实尺度（米），避免蜡像感
        b = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes and m.node_tree else None
        if b and b.inputs['Subsurface Weight'].default_value > 0: b.inputs['Subsurface Scale'].default_value = 0.004
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, 'beauty_')
    vl = sc.view_layers[0]; vl.use_pass_z = True; vl.use_pass_normal = True
    full = sc.render.engine == 'CYCLES'               # 正式渲染（Cycles）额外输出物体编号与 Cryptomatte 遮罩；EEVEE 预览不支持
    if full: vl.use_pass_object_index = True; vl.use_pass_cryptomatte_object = True
    # 合成器：控制图层（给云端 AI 写实化当「施工图纸」）
    sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers'); comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], comp.inputs['Image'])
    # 深度：固定 0.1~40 米映射（近白远黑），每帧同一标尺——原先逐帧归一化，标尺随画面跳变会闪
    mr = nt.nodes.new('CompositorNodeMapRange'); mr.inputs['From Min'].default_value = 0.1; mr.inputs['From Max'].default_value = 40.0
    mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0; mr.use_clamp = True
    fo = nt.nodes.new('CompositorNodeOutputFile'); fo.base_path = out_dir
    fo.file_slots[0].path = 'depth_'; fo.format.file_format = 'PNG'; fo.format.color_mode = 'BW'; fo.format.color_depth = '16'
    nt.links.new(rl.outputs['Depth'], mr.inputs['Value']); nt.links.new(mr.outputs['Value'], fo.inputs[0])
    if full:   # 原始数据另存多层 EXR：真实深度（米）、世界空间法线、物体编号（每个角色固定编号，见 shots/<seg>_ids.json）、Cryptomatte
        ex = nt.nodes.new('CompositorNodeOutputFile'); ex.base_path = os.path.join(out_dir, 'ctrl_')
        ex.format.file_format = 'OPEN_EXR_MULTILAYER'; ex.format.color_depth = '32'; ex.format.exr_codec = 'ZIP'
        ex.layer_slots.clear()
        for name in ('Depth', 'Normal', 'IndexOB'):
            ex.layer_slots.new(name); nt.links.new(rl.outputs[name], ex.inputs[name])
        for o in rl.outputs:
            if o.name.startswith('CryptoObject'): ex.layer_slots.new(o.name); nt.links.new(o, ex.inputs[o.name])
        mk = nt.nodes.new('CompositorNodeMath'); mk.operation = 'DIVIDE'; mk.inputs[1].default_value = 20.0   # 遮罩 PNG：编号/20 → 灰度
        fm = nt.nodes.new('CompositorNodeOutputFile'); fm.base_path = out_dir
        fm.file_slots[0].path = 'mask_'; fm.format.file_format = 'PNG'; fm.format.color_mode = 'BW'; fm.format.color_depth = '8'
        nt.links.new(rl.outputs['IndexOB'], mk.inputs[0]); nt.links.new(mk.outputs[0], fm.inputs[0])
