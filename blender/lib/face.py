# -*- coding: utf-8 -*-
"""口型：Rhubarb 嘴型（A–H、X）-> 面部骨骼姿态（下颌开合 + 嘴唇骨骼），按配音时间打关键帧。
骨骼：jaw（下颌，局部 X 轴旋转张嘴），oris*（嘴唇一圈），来自 MPFB default rig。
"""
import math, json

# 每个嘴型：(下颌张开角度°, 嘴角内收量 0-1 = 嘟嘴/圆唇, 下唇上抬 0-1)
VISEME = {
    'X': (0.0, 0.0, 0.0),    # 闭嘴放松
    'A': (0.0, 0.0, 0.3),    # M/B/P 双唇紧闭
    'B': (5.0, 0.0, 0.0),    # 大多数辅音，微张
    'C': (10.0, 0.0, 0.0),   # e/ei 半张
    'D': (17.0, 0.0, 0.0),   # a 大张
    'E': (9.0, 0.5, 0.0),    # o/e(r) 圆唇
    'F': (4.0, 1.0, 0.0),    # u/ü 嘟嘴
    'G': (3.0, 0.0, 0.8),    # f 下唇贴上齿
    'H': (8.0, 0.0, 0.0),    # l 舌尖
}
JAW_SIGN = 1.0   # 由测试图确定下颌张嘴的旋转方向

def set_viseme(rig, shape, weight=1.0):
    jaw_deg, pucker, lip_up = [v * weight for v in VISEME[shape]]
    pb = rig.pose.bones
    pb['jaw'].rotation_mode = 'XYZ'
    pb['jaw'].rotation_euler = (math.radians(jaw_deg) * JAW_SIGN, 0, 0)
    for side, sx in (('L', -1), ('R', 1)):     # 嘴角骨骼向中线收 = 嘟嘴
        for n in ('oris03.', 'oris07.'):
            b = pb.get(n + side)
            if b: b.location = (sx * 0.004 * pucker, 0, 0)
    for n in ('oris05', 'oris06'):            # 下唇骨骼上抬
        b = pb.get(n)
        if b: b.location = (0, 0.003 * lip_up, 0)

def key_viseme(rig, frame):
    pb = rig.pose.bones
    pb['jaw'].keyframe_insert('rotation_euler', frame=frame)
    for n in ('oris03.L', 'oris03.R', 'oris07.L', 'oris07.R', 'oris05', 'oris06'):
        if n in pb: pb[n].keyframe_insert('location', frame=frame)

def apply_rhubarb(rig, cue_json, start_frame, fps=24):
    """读取 Rhubarb 输出，从 start_frame 起逐个嘴型打关键帧（嘴型之间自动插值过渡）"""
    cues = json.load(open(cue_json, encoding='utf-8'))['mouthCues']
    for c in cues:
        f = start_frame + c['start'] * fps
        set_viseme(rig, c['value']); key_viseme(rig, f)
    set_viseme(rig, 'X'); key_viseme(rig, start_frame + cues[-1]['end'] * fps + 2)
