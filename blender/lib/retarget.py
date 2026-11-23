# -*- coding: utf-8 -*-
"""CMU 动作捕捉（BVH）-> MPFB default 骨骼 重定向。
做法：逐帧取源骨骼在世界空间相对其静止姿态的转动量，施加到目标骨骼上。
CMU 静止姿态是 T-pose、MPFB 是 A-pose：先算出把目标骨骼对齐到源骨骼静止方向的校正，再叠加转动量。
根骨骼位移按髋部高度比例缩放。结果烘焙成目标骨架上的一个 Action（只含身体骨骼，面部骨骼留给口型）。
"""
import math
import bpy
from mathutils import Matrix, Quaternion, Vector

MAP = [   # (CMU 骨骼, MPFB 骨骼) —— 按父子顺序
    ('Hips', 'root'), ('LowerBack', 'spine05'), ('Spine', 'spine03'), ('Spine1', 'spine01'),
    ('Neck', 'neck01'), ('Neck1', 'neck02'), ('Head', 'head'),
    ('LeftShoulder', 'clavicle.L'), ('LeftArm', 'upperarm01.L'), ('LeftForeArm', 'lowerarm01.L'), ('LeftHand', 'wrist.L'),
    ('RightShoulder', 'clavicle.R'), ('RightArm', 'upperarm01.R'), ('RightForeArm', 'lowerarm01.R'), ('RightHand', 'wrist.R'),
    ('LeftUpLeg', 'upperleg01.L'), ('LeftLeg', 'lowerleg01.L'), ('LeftFoot', 'foot.L'),
    ('RightUpLeg', 'upperleg01.R'), ('RightLeg', 'lowerleg01.R'), ('RightFoot', 'foot.R'),
]

def load_bvh(path, name=None, frame_start=1):
    """导入 BVH（CMU 单位约为英寸 -> 米），帧率换算到场景帧率"""
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=path, global_scale=0.056444, frame_start=frame_start, use_fps_scale=True,
                            update_scene_fps=False, update_scene_duration=False, rotate_mode='NATIVE', axis_forward='-Z', axis_up='Y')
    src = (set(bpy.data.objects) - before).pop()
    if name: src.name = name
    src.hide_render = True
    return src

_GAIT = {}

def gait(path):
    """分析走路片段的步态周期：返回 (起始帧 a, 一个完整周期帧数 P, 每周期髋部水平位移[源单位], 首帧髋高)。
    以左脚落地（脚高度的局部最低点）为周期边界，这样循环拼接时步伐相位连续、不会突然换脚。"""
    if path in _GAIT: return _GAIT[path]
    src = load_bvh(path, frame_start=1)
    fr = src.animation_data.action.frame_range; n = int(fr[1])
    foot, hips = [], []; se = SrcEval(src)
    for f in range(1, n + 1):
        W_ = se.world(f)
        foot.append(W_['LeftFoot'].translation.z); hips.append(W_['Hips'].translation.copy())
    mins = [i for i in range(2, n - 2) if foot[i] <= min(foot[i - 2:i + 3]) and foot[i] < min(foot) + 0.04]
    mins = [m for k, m in enumerate(mins) if k == 0 or m - mins[k - 1] > 8]
    a, b = (mins[0], mins[-1]) if len(mins) >= 2 else (3, n - 3)
    cycles = max(1, len(mins) - 1)
    P = (b - a) / cycles
    disp = (hips[b] - hips[a]); disp.z = 0; disp /= cycles
    bpy.data.objects.remove(src, do_unlink=True)
    _GAIT[path] = (a + 1, P, disp, hips[a].z)
    return _GAIT[path]

def walk_plan(path, tgt, p0, p1):
    """(帧数, 水平微调系数, 髋高比例)：按动捕原速走完 p0->p1 需要多少帧"""
    a, P, disp, hz = gait(path)
    th = _world_rest(tgt, tgt.pose.bones['root']).translation.z
    k = th / max(hz, 1e-3)
    dist = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)).length
    stride = disp.length * k                                    # 目标角色每周期走多远（米）
    frames = max(8, round(max(0.5, dist / max(stride, 1e-3)) * P))
    return frames, dist / max(stride * frames / P, 1e-3), k

def walk(path, tgt, dst_start, p0, p1):
    """从 p0 走到 p1（世界坐标，地面）：按动捕原速，循环拼接整步周期，水平位移微调到正好停在 p1。返回占用帧数。"""
    a, P, disp, _ = gait(path)
    frames, hs, k = walk_plan(path, tgt, p0, p1)
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
    yaw = math.degrees(math.atan2(d.y, d.x) - math.atan2(disp.y, disp.x))
    done, pos, f = 0, Vector((p0[0], p0[1], 0)), dst_start
    ip = max(1, int(round(P)))
    while done < frames:
        seg = min(ip, frames - done)
        src = load_bvh(path, frame_start=f - a + 1)            # 源第 a 帧对齐到场景第 f 帧
        retarget(src, tgt, a, a + seg, dst_start=f, action_name=None, root_offset=tuple(pos), root_yaw=yaw, hscale=hs)
        bpy.data.objects.remove(src, do_unlink=True)
        q = Quaternion((0, 0, 1), math.radians(yaw))
        pos = pos + q @ (disp * k * hs * (seg / P))
        done += seg; f += seg
    return frames

def _world_rest(arm, pb):
    return arm.matrix_world @ pb.bone.matrix_local

def retarget(src, tgt, f0, f1, dst_start=1, action_name='clip', root_offset=(0, 0, 0), root_yaw=0.0, hscale=1.0, k=None, root_z0=None):
    """把 src 第 f0..f1 帧烘焙到 tgt 的 dst_start 起。root_offset/root_yaw：把动作整体搬到场景里的位置与朝向；hscale：水平位移微调（让走路正好停在终点）。"""
    sc = bpy.context.scene
    spb, tpb = src.pose.bones, tgt.pose.bones
    pairs = [(spb[s], tpb[t]) for s, t in MAP if s in spb and t in tpb]
    # 静止姿态对齐校正：目标骨骼 Y 轴方向 -> 源骨骼 Y 轴方向
    align = {}
    for sb, tb in pairs:
        sr, tr = _world_rest(src, sb), _world_rest(tgt, tb)
        sdir = (sr.to_quaternion() @ Vector((0, 1, 0))).normalized()
        tdir = (tr.to_quaternion() @ Vector((0, 1, 0))).normalized()
        align[tb.name] = tdir.rotation_difference(sdir) @ tr.to_quaternion()
    th = _world_rest(tgt, tpb['root']).translation
    yaw = Quaternion((0, 0, 1), math.radians(root_yaw)); off = Vector(root_offset)
    # 源动作已在导入时对齐到目标时间轴：源第 f0 帧位于场景第 dst_start 帧，逐帧同时求值，避免读到目标在别处的旧姿态
    shift = dst_start - f0; f0, f1 = f0 + shift, f1 + shift
    se = SrcEval(src)
    start_hips = se.world(f0)['Hips'].translation.copy()
    sh = start_hips                                    # BVH 静止姿态的根骨在地面，用首帧实际髋高
    if k is None: k = th.z / max(sh.z, 1e-3)           # 髋高比例（首帧是站着的片段）；从坐姿开始的片段由调用方给出
    z0 = th.z if root_z0 is None else root_z0          # 首帧时目标根骨的高度（站着=静止髋高；坐着=当前坐姿髋高）
    if not tgt.animation_data: tgt.animation_data_create()
    if action_name or tgt.animation_data.action is None:   # action_name=None：写进骨架现有动画（与姿态、口型同一条时间轴）
        tgt.animation_data.action = bpy.data.actions.new(action_name or 'clip')
    act = tgt.animation_data.action
    for _, tb in pairs: tb.rotation_mode = 'QUATERNION'   # 只改身体骨骼；下颌/眼睑/手指用欧拉角，改了会让口型和眨眼失效
    # 不逐骨刷新场景：自己沿骨骼链用矩阵算（原先每骨每帧刷新一次整个场景，背景人多时慢到几十分钟）
    mapped = {tb.name: (sb.name, tb) for sb, tb in pairs}
    s_rest = {sb.name: _world_rest(src, sb).to_quaternion() for sb, _ in pairs}
    chain = _chain(tgt); rel = {b.name: _rel(b) for b in chain}
    static = {b.name: tpb[b.name].matrix_basis.copy() for b in chain if b.name not in mapped}
    MW = tgt.matrix_world; MWi = MW.inverted()
    for f in range(f0, f1 + 1):
        S = se.world(f); P = {}
        for b in chain:
            base = (P[b.parent.name] if b.parent else Matrix.Identity(4)) @ rel[b.name]
            if b.name not in mapped:
                P[b.name] = base @ static[b.name]; continue
            sname, tb = mapped[b.name]
            delta = yaw @ (S[sname].to_quaternion() @ s_rest[sname].inverted())
            new_rot = delta @ align[b.name]
            wb = MW @ base
            if b.name == 'root':
                hp = S[sname].translation
                r_ = hp - start_hips; r_ = Vector((r_.x * k * hscale, r_.y * k * hscale, 0))
                head = off + (yaw @ r_) + Vector((0, 0, z0 + (hp.z - sh.z) * k))
            else:
                head = wb.translation
            basis = base.inverted() @ (MWi @ Matrix.LocRotScale(head, new_rot, wb.to_scale()))
            tb.matrix_basis = basis; tb.scale = (1, 1, 1); P[b.name] = base @ Matrix.LocRotScale(basis.to_translation(), basis.to_quaternion(), (1, 1, 1))   # 不带缩放（防累积变形）
            tb.keyframe_insert('rotation_quaternion', frame=f, group=tb.name)
            if b.name == 'root': tb.keyframe_insert('location', frame=f, group='root')
    return act

def _chain(arm):
    """骨骼按父在前、子在后排序"""
    out = []
    def rec(b):
        out.append(b)
        for c in b.children: rec(c)
    for b in arm.data.bones:
        if b.parent is None: rec(b)
    return out

def _rel(b):
    return b.matrix_local.copy() if b.parent is None else b.parent.matrix_local.inverted() @ b.matrix_local

class SrcEval:
    """直接读动作曲线求源骨架各骨骼的世界矩阵（不切帧、不刷新场景）"""
    def __init__(self, src):
        self.src = src; self.chain = _chain(src); self.rel = {b.name: _rel(b) for b in self.chain}
        self.fc = {}
        for fc in src.animation_data.action.fcurves:
            if not fc.data_path.startswith('pose.bones["'): continue
            bn = fc.data_path.split('"')[1]; prop = fc.data_path.rsplit('.', 1)[-1]
            self.fc.setdefault((bn, prop), {})[fc.array_index] = fc
        self.mode = {pb.name: pb.rotation_mode for pb in src.pose.bones}
    def basis(self, bn, f):
        loc = self.fc.get((bn, 'location'), {}); m = self.mode[bn]
        t = Vector([loc[i].evaluate(f) if i in loc else 0.0 for i in range(3)])
        if m == 'QUATERNION':
            q = self.fc.get((bn, 'rotation_quaternion'), {})
            r = Quaternion([q[i].evaluate(f) if i in q else (1.0 if i == 0 else 0.0) for i in range(4)]).normalized().to_matrix()
        else:
            from mathutils import Euler
            e = self.fc.get((bn, 'rotation_euler'), {})
            r = Euler([e[i].evaluate(f) if i in e else 0.0 for i in range(3)], m).to_matrix()
        return Matrix.Translation(t) @ r.to_4x4()
    def world(self, f):
        P = {}
        for b in self.chain:
            P[b.name] = (P[b.parent.name] if b.parent else Matrix.Identity(4)) @ self.rel[b.name] @ self.basis(b.name, f)
        mw = self.src.matrix_world
        return {n: mw @ m for n, m in P.items()}
