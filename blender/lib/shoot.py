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
import poses, face, retarget, sets
import blocking

VIS = config.VISEMES; MOCAP = config.MOCAP
from segments import FPS, LEAD, META, TEXT, CID, EST_SET, audio_plan, beat_dur, beat_frames, loc_of, segments

# ---------------- 场景/角色装配 ----------------
def append_cast(cid):
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects: bpy.context.scene.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']
    rig.animation_data_create(); rig.animation_data.action = bpy.data.actions.new(cid + '_act')
    return rig

def make_phone(cid):
    """每个角色一部手机：机身 + 屏幕面（prop_screen_<cid>，Remotion 按其四角贴真实界面）"""
    body = sets.box('prop_phone_' + cid, (0.075, 0.155, 0.009), (0, 0, 0), 'black')
    scr = sets.box('prop_screen_' + cid, (0.068, 0.146, 0.001), (0, 0, 0.0092), (0.06, 0.09, 0.14))
    scr.parent = body
    return body

def show_phone(pair, frame, in_hand):
    held, rest = pair
    for o, vis in ((held, in_hand), (rest, not in_hand)):
        for c in [o] + list(o.children):
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

def place_camera(name, subj_pts, facing_yaw, kind, side, bounds, frame0, frame1, en='', head_up=None):
    """subj_pts: 被摄主体关键点（头部世界坐标列表）；facing_yaw：主体朝向；side：+1/-1 轴线一侧"""
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
            if obj.name.startswith(('furn_', 'prop_', 'ext_lamp', 'ext_trunk', 'ext_crown', 'ext_bike', 'ext_column')):
                hidden.add(obj.name); t = hd + 0.02; continue
            person = bool(obj.name.split('_')[0] in CID.values() or (obj.parent is not None and obj.parent.name.endswith('_rig')))
            return hd - 0.12, hidden, person
        return dist, hidden, False
    best = None
    for k, o in enumerate(offs):   # 每个候选角度打 5 条射线（主体中心 + 上下左右），选视线最通畅的
        a = math.radians(o)
        d = (face_dir * math.cos(a) + right * math.sin(a) + upv * elev).normalized()
        rgt = d.cross(Vector((0, 0, 1))).normalized() if abs(d.z) < 0.95 else Vector((1, 0, 0))
        clear, hidden, by_person = dist, set(), False
        for p in (tgt, tgt + rgt * spread, tgt - rgt * spread, tgt + Vector((0, 0, spread)), tgt - Vector((0, 0, spread))):
            c_, h_, pr = probe(p, d); clear = min(clear, c_); hidden |= h_; by_person |= pr
        score = min(clear, dist) / dist - 0.04 * k - 0.01 * len(hidden) - (0.6 if by_person else 0)   # 被别的人物挡住：换角度
        if best is None or score > best[0]: best = (score, d, max(0.3, min(clear, dist)), hidden)
    _, d, clear, hidden = best
    for n in hidden:   # 本拍临时移走挡镜头的家具（拍完恢复）
        ob = bpy.data.objects[n]
        for fr, v in ((frame0 - 1, False), (frame0, True), (frame1 + 1, False)):
            ob.hide_render = v; ob.keyframe_insert('hide_render', frame=fr)
    pos = tgt + d * clear
    lens = max(14, lens * clear / dist)                      # 被迫收近时换广角，保持景别
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = lens; cam.data.clip_start = 0.05; cam.data.clip_end = 300
    fstop = {'ECU': 2.8, 'CU': 2.8, 'MCU': 2.8, 'MS': 4.0}.get(kind)   # 景深：对焦在主体脸上
    if fstop:
        cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = fstop; cam.data.dof.focus_distance = max(0.2, (pos - tgt).length)
    d = tgt - pos; cam.location = pos
    up = Vector((0, 0, 1))
    if head_up is not None and abs(d.normalized().z) > 0.6: up = Vector(head_up)   # 俯拍/仰拍躺着的人：以头顶方向为画面上方，避免人脸倒置
    z = (-d).normalized(); x = up.cross(z)
    if x.length < 1e-4: x = Vector((1, 0, 0))
    x.normalize(); y = z.cross(x)
    cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
    cam.keyframe_insert('location', frame=frame0)
    cam.location = pos + d.normalized() * min(0.12, d.length * 0.04)     # 缓慢推近，画面有呼吸感
    cam.keyframe_insert('location', frame=frame1)
    return cam

# ---------------- 主装配 ----------------
def build_segment(seg_id, scene, set_name, beats):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sets._cube = None; sets._MATS.clear()
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
    f = 1; side = B.get('side', 1); cam_prev = None; markers = []
    timeline = []
    for bt in beats:
        n = beat_frames(bt); f0, f1 = f, f + n - 1
        spec = B['beats'].get(bt['id'], {})
        sync = [l for o, l, y in audio_plan(bt) if y]
        speaker = CID.get(TEXT[sync[0]][0]) if sync else None
        # 1) 走位/姿态：拍开头的状态（继承上一拍）+ 本拍的变化
        walking = {}
        for cid, rig in rigs.items():
            if cid not in [CID[c] for c in bt['chars']] and cid not in spec:
                poses.apply_state(rig, blocking.with_look(state[cid], None), f0); continue
            act = spec.get(cid)
            start = dict(state[cid])
            if speaker and cid != speaker and speaker in rigs: start['look'] = poses.head_pos(rigs[speaker])
            elif speaker == cid:
                lst = [o for o in rigs if o != cid and o in [CID[c] for c in bt['chars']]]
                start['look'] = poses.head_pos(rigs[lst[0]]) if lst else None
            if act is None:
                poses.apply_state(rig, start, f0); poses.apply_state(rig, start, f1)
                continue
            kind, new = act[0], blocking.resolve(dict(state[cid], **act[1]), marks)
            if kind == 'set':        # 拍开头即是新状态（换机位时“片刻之后”）
                poses.apply_state(rig, new, f0); poses.apply_state(rig, new, f1)
            elif kind == 'blend':    # 在 t 秒内过渡到新状态
                t = act[2] if len(act) > 2 else 0.8
                poses.apply_state(rig, start, f0); poses.apply_state(rig, new, min(f1, f0 + round(t * FPS))); poses.apply_state(rig, new, f1)
            elif kind == 'walk':     # 走路动作捕捉：从当前位置走到新位置，最后过渡到新状态
                p0, p1 = Vector(start['pos'][:2] + (0,)), Vector(new['pos'][:2] + (0,))
                dist = (p1 - p0).length; walking[cid] = (p0, p1)
                yaw = math.degrees(math.atan2(-(p1 - p0).x, (p1 - p0).y)) + 180 if dist > 0.05 else start['yaw']
                frames = min(n - 6, max(12, round(dist / 1.25 * FPS)))
                src = retarget.load_bvh(os.path.join(MOCAP, '07_01.bvh'), frame_start=(f0 + 1) - 12 + 1)   # 源第 12 帧对齐到场景第 f0+1 帧
                poses.apply_state(rig, dict(start, yaw=yaw, base='stand', arms='down'), f0)
                retarget.retarget(src, rig, 12, 12 + frames, dst_start=f0 + 1, action_name=None, root_offset=tuple(p0), root_yaw=yaw)
                bpy.data.objects.remove(src, do_unlink=True)
                poses.apply_state(rig, new, min(f1, f0 + frames + 6)); poses.apply_state(rig, new, f1)
            state[cid] = new
            # 手机：在手上 or 放下
            prop = poses.ARMS[new.get('arms', 'down')].get('prop')
            show_phone(phones[cid], f0, prop in ('hand', 'ear'))
        # 2) 口型
        for off, lid, y in audio_plan(bt):
            if not y: continue
            cid = CID.get(TEXT[lid][0])
            if cid in rigs and os.path.exists(os.path.join(VIS, lid + '.json')):
                face.apply_rhubarb(rigs[cid], os.path.join(VIS, lid + '.json'), f0 + off * FPS, FPS)
        # 3) 机位：cont 沿用上一机位，其余按描述自动生成
        if bt['cam'] == 'cont' and cam_prev is not None:
            cam = cam_prev
            cam.keyframe_insert('location', frame=f1)
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
                cam = place_camera('cam_' + bt['id'], pts, yaw, kind, side, bounds, f0, f1, bt.get('en'), head_up=hu)
        if cam is not cam_prev:
            m = sc.timeline_markers.new(bt['id'], frame=f0); m.camera = cam
        cam_prev = cam
        timeline.append(dict(id=bt['id'], f0=f0, f1=f1, audio=[(round(f0 + o * FPS), l) for o, l, _ in audio_plan(bt)]))
        f = f1 + 1
    sc.frame_start, sc.frame_end = 1, f - 1
    sc.camera = sc.timeline_markers[0].camera if sc.timeline_markers else None
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
