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

def _world_rest(arm, pb):
    return arm.matrix_world @ pb.bone.matrix_local

def retarget(src, tgt, f0, f1, dst_start=1, action_name='clip', root_offset=(0, 0, 0), root_yaw=0.0):
    """把 src 第 f0..f1 帧烘焙到 tgt 的 dst_start 起。root_offset/root_yaw：把动作整体搬到场景里的位置与朝向。"""
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
    sc.frame_set(f0); start_hips = (src.matrix_world @ spb['Hips'].matrix).translation.copy()
    sh = start_hips                                    # BVH 静止姿态的根骨在地面，用首帧实际髋高
    k = th.z / max(sh.z, 1e-3)                         # 髋高比例
    if not tgt.animation_data: tgt.animation_data_create()
    if action_name or tgt.animation_data.action is None:   # action_name=None：写进骨架现有动画（与姿态、口型同一条时间轴）
        tgt.animation_data.action = bpy.data.actions.new(action_name or 'clip')
    act = tgt.animation_data.action
    for tb in tpb: tb.rotation_mode = 'QUATERNION'
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for sb, tb in pairs:
            s_rest, s_cur = _world_rest(src, sb).to_quaternion(), (src.matrix_world @ sb.matrix).to_quaternion()
            delta = yaw @ (s_cur @ s_rest.inverted())
            new_rot = delta @ align[tb.name]
            tw = tgt.matrix_world @ tb.matrix
            if tb.name == 'root':
                hp = (src.matrix_world @ sb.matrix).translation
                rel = hp - start_hips; rel = Vector((rel.x * k, rel.y * k, 0))
                head = off + (yaw @ rel) + Vector((0, 0, th.z + (hp.z - sh.z) * k))
            else:
                head = tw.translation
            m = Matrix.LocRotScale(head, new_rot, tw.to_scale())
            tb.matrix = tgt.matrix_world.inverted() @ m
            bpy.context.view_layer.update()
        fr = f
        for sb, tb in pairs:
            tb.keyframe_insert('rotation_quaternion', frame=fr, group=tb.name)
            if tb.name == 'root': tb.keyframe_insert('location', frame=fr, group='root')
    return act
