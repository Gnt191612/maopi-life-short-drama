# -*- coding: utf-8 -*-
"""白模拍摄引擎：把一个「地点片段」（同一场戏里同一地点的连续若干拍）搭成完整动画：
  场景 + 角色 + 道具 + 每拍走位/姿态（状态在拍之间连续继承）+ 走路动作捕捉 + 口型 + 自动机位（含 180° 轴线）+ 渲染设置。
时间轴：片段内各拍首尾相接（24fps），拍时长 = 动作所需与台词所需取大。
"""
import os, sys, json, math, re
import bpy
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # 仓库根目录
import config
import poses, face, retarget, sets, life, nav, phone_ui
import blocking

VIS = config.VISEMES; MOCAP = config.MOCAP
from segments import FPS, LEAD, META, TEXT, CID, EST_SET, audio_plan, screen_plan, beat_dur, beat_frames, loc_of, segments
from lines import SCREEN
NAME = {v: k for k, v in CID.items()}

# ---------------- 场景/角色装配 ----------------
def append_cast(cid):
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects: bpy.context.scene.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']
    rig.animation_data_create(); rig.animation_data.action = bpy.data.actions.new(cid + '_act')
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

def hide_range(names, frame0, frame1):
    """在 frame0..frame1 内临时移走挡镜头的家具（前后恢复）"""
    for n in names:
        ob = bpy.data.objects[n]
        for fr, v in ((frame0 - 1, False), (frame0, True), (frame1 + 1, False)):
            ob.hide_render = v; ob.keyframe_insert('hide_render', frame=fr)

HIDEABLE = ('furn_', 'prop_', 'ext_lamp', 'ext_trunk', 'ext_crown', 'ext_bike', 'ext_column', 'ext_bench', 'ext_bin', 'ext_sign', 'ext_hedge', 'ext_flower')

def _wall(name):
    """房间的墙（不含地面、天花）：像真实片场的「活动墙」一样，挡在机位后面时可以临时拆掉"""
    return '_wall' in name and 'ceiling' not in name and 'floor' not in name

def place_camera(name, subj_pts, facing_yaw, kind, side, bounds, frame0, frame1, en='', head_up=None, protect=(), validate=None):
    """subj_pts: 被摄主体关键点（头部世界坐标列表）；facing_yaw：主体朝向；side：+1/-1 轴线一侧；
    validate(cam)->bool：按分数从高到低试候选机位，第一个通过检查（脸朝镜头、在画面里、没被人挡）的就用"""
    dist, lens = SHOT[kind]
    c = sum(subj_pts, Vector()) / len(subj_pts)
    tgt = c + Vector((0, 0, -0.05 if kind in ('ECU', 'CU') else (-0.25 if kind == 'MCU' else -0.45)))
    e = (en or '').lower()
    if len(subj_pts) > 1: dist *= 1.0 + 0.35 * (len(subj_pts) - 1)
    face_dir = facing_yaw if isinstance(facing_yaw, Vector) else Vector((math.sin(math.radians(facing_yaw)), -math.cos(math.radians(facing_yaw)), 0))
    face_dir = face_dir.normalized()
    right = face_dir.cross(Vector((0, 0, 1))) if abs(face_dir.z) < 0.9 else Vector((1, 0, 0))
    right.normalize(); upv = right.cross(face_dir).normalized()
    if 'from behind' in e: offs = [180 - 20 * side, 160, 200]
    elif 'over the shoulder' in e or 'over shoulder' in e: offs = [150 * side, 130 * side]
    elif 'from beside' in e: offs = [70 * side, 50 * side, 90 * side]
    else: offs = [28 * side, 12 * side, 45 * side, 65 * side, 90 * side, 110 * side]   # 先 3/4 正面，挡住就逐步转向侧面（不越轴）
    elev = 0.06 if kind in ('ECU', 'CU', 'MCU') else 0.18
    if 'floor level' in e: elev = -0.35
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    spread = 0.1 if kind in ('ECU', 'CU') else 0.25
    def probe(p, d):
        """沿视线收集挡在中间的家具/道具（可临时移走），遇到墙/地/天花/其他人则停下"""
        hidden, t = set(), 0.28
        while t < dist:
            hit, loc, _, _, obj, _ = sc.ray_cast(dg, p + d * t, d, distance=dist - t)
            if not hit: return dist, hidden, False
            hd = (loc - p).length
            if (obj.name.startswith(HIDEABLE) or _wall(obj.name)) and obj.name not in protect:
                hidden.add(obj.name); t = hd + 0.02; continue
            person = bool(obj.name.split('_')[0] in CID.values() or (obj.parent is not None and obj.parent.name.endswith('_rig')))
            return hd - 0.12, hidden, person
        return dist, hidden, False
    cands = []
    for k, o in enumerate(offs):   # 每个候选角度打 5 条射线（主体中心 + 上下左右），按视线通畅程度打分
        for ev, epen in ((elev, 0.0), (elev + 0.18, 0.05)):
            a = math.radians(o)
            d = (face_dir * math.cos(a) + right * math.sin(a) + upv * ev).normalized()
            rgt = d.cross(Vector((0, 0, 1))).normalized() if abs(d.z) < 0.95 else Vector((1, 0, 0))
            clear, hidden, by_person = dist, set(), False
            for p in (tgt, tgt + rgt * spread, tgt - rgt * spread, tgt + Vector((0, 0, spread)), tgt - Vector((0, 0, spread))):
                c_, h_, pr = probe(p, d); clear = min(clear, c_); hidden |= h_; by_person |= pr
            walls = sum(1 for n in hidden if _wall(n))
            score = (min(clear, dist) / dist - 0.04 * k - epen - 0.01 * len(hidden) - 0.04 * walls
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
        if head_up is not None and abs(dd.normalized().z) > 0.6: up = Vector(head_up)   # 俯拍/仰拍躺着的人：以头顶方向为画面上方，避免人脸倒置
        z = (-dd).normalized(); x = up.cross(z)
        if x.length < 1e-4: x = Vector((1, 0, 0))
        x.normalize(); y = z.cross(x)
        cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        bpy.context.view_layer.update()
        return pos, dd
    chosen = cands[0]
    for c_ in cands[:10]:
        aim_at(c_[1], c_[2])
        if validate is None or validate(cam): chosen = c_; break
    _, d, clear, hidden = chosen
    pos, d = aim_at(d, clear)
    hide_range(hidden, frame0, frame1)   # 本拍临时移走挡镜头的家具/活动墙（拍完恢复）
    cam.keyframe_insert('location', frame=frame0)
    cam.location = pos + d.normalized() * min(0.12, d.length * 0.04)     # 缓慢推近，画面有呼吸感
    cam.keyframe_insert('location', frame=frame1)
    cam['hidden'] = list(hidden)
    return cam

def face_dir(rig):
    """头部真实朝向（含转头）：静止时脸朝 -Y，换算到头骨局部轴再随姿态转到世界"""
    hb = rig.pose.bones['head']
    rest = hb.bone.matrix_local.inverted().to_3x3() @ Vector((0, -1, 0))
    hm = rig.matrix_world @ hb.matrix
    return (hm.to_3x3() @ rest).normalized(), hm.translation + hm.to_3x3() @ Vector((0, hb.length * 0.5, 0))

def shot_ok(cam, rigs, watch, subj, f0, f1):
    """候选机位是否可用：说话的人脸朝镜头、在画面里、没被别人挡；所有主体都在画面里；镜头不在任何人身体里"""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene; ok = True
    for fr in (f0 + 2, (f0 + f1) // 2, max(f0 + 2, f1 - 2)):
        sc.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); cpos = cam.matrix_world.translation
        for r in rigs.values():
            rh = r.matrix_world @ r.pose.bones['root'].head; top = poses.head_pos(r).z + 0.15
            if Vector((cpos.x - rh.x, cpos.y - rh.y)).length < 0.3 and cpos.z < top: return False
        for s_ in subj:
            v = world_to_camera_view(sc, cam, poses.head_pos(rigs[s_]))
            if v.z <= 0 or not (0.03 < v.x < 0.97 and 0.03 < v.y < 0.97): return False
        for s_ in watch:
            fd, head = face_dir(rigs[s_]); to_cam = (cpos - head).normalized()
            if fd.dot(to_cam) < 0.15: return False
            t, dist = 0.05, (head - cpos).length - 0.15; d = (head - cpos).normalized()
            while t < dist:
                hit, loc, _, _, obj, _ = sc.ray_cast(dg, cpos + d * t, d, distance=dist - t)
                if not hit: break
                if obj.parent is not None and obj.parent.type == 'ARMATURE':
                    if obj.parent is not rigs[s_] and not obj.name.startswith('prop_'): return False
                t = (loc - cpos).length + 0.01
    return ok

def add_walkers(walkers, f_end, clip):
    """外景背景里来往的路人学生：按设定时刻出发、动捕走路；片段结束前走不完就走到哪算哪（只烘焙需要的帧）"""
    for cid, p0, p1, t0 in walkers:
        if not os.path.exists(os.path.join(config.CAST, cid + '.blend')): continue
        rig = append_cast(cid)
        fs = 1 + round(t0 * FPS)
        if fs >= f_end - 10: continue
        d = Vector(p1) - Vector(p0)
        yaw = math.degrees(math.atan2(-d.x, d.y)) + 180
        frames, _, _ = retarget.walk_plan(clip, rig, p0, p1)
        frac = min(1.0, (f_end - fs) / max(1, frames))                      # 只走到片段结束
        q1 = Vector(p0) + d * frac
        poses.apply_state(rig, dict(pos=(p0[0], p0[1], 0), yaw=yaw, base='stand', arms='down'), 1)
        retarget.walk(clip, rig, fs, p0, (q1.x, q1.y))
        if fs > 1:   # 出发前不在画面里（不会有人杵在路边等着）
            for c in rig.children:
                for fr, v in ((1, True), (fs - 1, True), (fs, False)):
                    c.hide_render = v; c.keyframe_insert('hide_render', frame=fr)
        life.add_idle(rig, sum(map(ord, cid)))
        life.hands(rig, 1)

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
    on = lad + out * 0.2
    t += round(0.9 * FPS); steps.append((t, dict(pos=(on.x, on.y, tops[-1]), yaw=face_ladder, base='climbA', arms='climb')))
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
    sc = bpy.context.scene; sc.render.fps = FPS; sc['v11_set'] = set_name
    B = blocking.get(scene['id'])
    chars = sorted({c for bt in beats for c in bt['chars']} | set(B.get('extras', {}).get(set_name, [])))
    rigs = {CID[c]: append_cast(CID[c]) for c in chars}
    init = B.get('init_' + set_name) or B['init']
    phones = {}
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
                plans[cid] = ('blend', new, round(tt * FPS)); need = max(need, round(tt * FPS) + LAG + 4)
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
        walking = {}
        for cid, rig in rigs.items():
            if cid not in [CID[c] for c in bt['chars']] and cid not in spec:
                poses.apply_state(rig, blocking.with_look(state[cid], None), f0); continue
            start = dict(state[cid])
            if speaker and cid != speaker and speaker in rigs: start['look'] = poses.head_pos(rigs[speaker])
            elif speaker == cid:
                lst = [o for o in rigs if o != cid and o in [CID[c] for c in bt['chars']]]
                start['look'] = poses.head_pos(rigs[lst[0]]) if lst else None
            if cid not in plans:
                poses.apply_state(rig, start, f0); poses.apply_state(rig, start, f1)
                hand_ev[cid].append((f0, grips(start)))
                continue
            kind, new, arg = plans[cid]
            new_l = dict(new, look=start.get('look'))
            t_change = f0
            if kind == 'snap':       # 时间省略：拍开头已是新状态
                poses.apply_state(rig, new_l, f0); poses.apply_state(rig, new_l, f1)
            elif kind == 'blend':    # 真人速度过渡，躯干先动、手臂跟随
                fe = min(f1 - LAG, f0 + max(6, arg))
                poses.apply_state(rig, start, f0, lag=LAG); poses.apply_state(rig, new_l, fe, lag=LAG); poses.apply_state(rig, new_l, f1)
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
                if prep: poses.apply_state(rig, stand, f0 + prep, lag=0)
                for li, (a_, b_) in enumerate(legs):     # 拐点之间留 TURN 帧，由插值完成转身
                    ws += retarget.walk(WALK, rig, ws, a_, b_) + (TURN if li < len(legs) - 1 else 0)
                we = ws
                poses.apply_state(rig, new_l, min(f1 - LAG, we + settle), lag=LAG); poses.apply_state(rig, new_l, f1)
                t_change = we
            state[cid] = new
            # 手机：在手上 or 放下；手指握持随之变化
            prop = poses.ARMS[new.get('arms', 'down')].get('prop')
            show_phone(phones[cid], t_change, prop in ('hand', 'ear'))
            hand_ev[cid].append((f0, grips(start))); hand_ev[cid].append((t_change, grips(new)))
        # 2) 口型
        for off, lid, y in audio_plan(bt):
            if not y: continue
            cid = CID.get(TEXT[lid][0])
            if cid in rigs and os.path.exists(os.path.join(VIS, lid + '.json')):
                face.apply_rhubarb(rigs[cid], os.path.join(VIS, lid + '.json'), f0 + off * FPS, FPS)
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
                    if v.z <= 0 or not (0.04 < v.x < 0.96 and 0.04 < v.y < 0.98): return True
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
            else:
                subj = [speaker] if speaker in rigs else [CID[c] for c in bt['chars'] if CID[c] in rigs][:3]
                kind = shot_type(bt.get('en'))
                if kind in ('MS', 'WS'): subj = [CID[c] for c in bt['chars'] if CID[c] in rigs][:3] or subj
                sc.frame_set(f0)
                pts = [poses.head_pos(rigs[s]) for s in subj] or [Vector((0, 0, 1.4))]
                for i, s_ in enumerate(subj):   # 走动中的人：取路径中点，并至少用中景（长距离用全景）
                    if s_ in walking:
                        a_, b_ = walking[s_]; mid = (a_ + b_) / 2; pts[i] = Vector((mid.x, mid.y, pts[i].z))
                        kind = 'WS' if (b_ - a_).length > 3 else ('MS' if kind in ('ECU', 'CU', 'MCU') else kind)
                st0 = state[subj[0]] if subj else dict(yaw=0, base='stand')
                yaw = poses.body_rot(st0['yaw'], poses.BASE[st0.get('base', 'stand')]['pitch']) @ Vector((0, -1, 0))   # 脸的真实朝向（躺着=朝上）
                hu = poses.body_rot(st0['yaw'], poses.BASE[st0.get('base', 'stand')]['pitch']) @ Vector((0, 0, 1))
                watch = [speaker] if speaker in rigs else subj[:1]
                cam = place_camera('cam_' + bt['id'], pts, yaw, kind, side, bounds, f0, f1, bt.get('en'), head_up=hu, protect=protect,
                                   validate=None if 'from behind' in (bt.get('en') or '') else
                                   (lambda c_, w_=watch, a_=f0, b_=f1, all_=subj: shot_ok(c_, rigs, w_, all_, a_, b_)))
                movers = [s_ for s_ in subj if s_ in walking]
                if movers:   # 走动的人：镜头跟着摇（真人摄影师的跟拍），不会拍着拍着人走出画面
                    con = cam.constraints.new('DAMPED_TRACK'); con.target = rigs[movers[0]]; con.subtarget = 'spine01'
                    con.track_axis = 'TRACK_NEGATIVE_Z'; con.influence = 0.9
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
    for i, (cid, rig) in enumerate(sorted(rigs.items())):   # 活人感：呼吸、微动、眨眼、眼神、手指
        seed = sum(map(ord, seg_id + cid))
        life.add_idle(rig, seed)
        life.blinks(rig, 1, f - 1, seed)
        last = None
        for fr, (gr, gl) in sorted(hand_ev[cid]):
            if (gr, gl) != last:
                if last is not None: life.hands(rig, max(1, fr - 4), *last)   # 换手势前保持原样，约 0.3 秒内握住/松开
                life.hands(rig, fr + 4, gr, gl); last = (gr, gl)
        if last is None: life.hands(rig, 1)
    add_walkers(info.get('walkers', []), f - 1, WALK)
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
        sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 640, 360
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
    # 合成器：深度归一化后另存一路 PNG（控制图层）
    sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers'); comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], comp.inputs['Image'])
    norm = nt.nodes.new('CompositorNodeNormalize'); inv = nt.nodes.new('CompositorNodeInvert')
    fo = nt.nodes.new('CompositorNodeOutputFile'); fo.base_path = out_dir
    fo.file_slots[0].path = 'depth_'; fo.format.file_format = 'PNG'; fo.format.color_mode = 'BW'; fo.format.color_depth = '16'
    nt.links.new(rl.outputs['Depth'], norm.inputs[0]); nt.links.new(norm.outputs[0], inv.inputs['Color']); nt.links.new(inv.outputs[0], fo.inputs[0])
