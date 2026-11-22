# -*- coding: utf-8 -*-
"""发型「主体 + 发片」：照着定妆照建发型（替换程序发丝——发丝做不出干净的发型轮廓，头顶尖、刘海乱、两侧外张）。
1) 发型主体：发际线以上的头皮往外长出一层光滑厚壳（头顶厚、两侧服帖、发际线处收薄），决定发型轮廓；
2) 发流坐标：所有头发从前额中分点 N 出发、汇向后脑扎发点 S——过 N、S 两点的一族圆（绕 N–S 弦旋转的平面与头部球面的交线）
   正好是「中分 → 梳向两侧 → 拢到脑后」的走向；φ = 绕弦的角度（φ=0 是经过头顶的中线 = 分缝），t = 从 N 到 S 的进度。
   主体的 UV 就是 (φ, t)：发丝条纹沿 t 方向，分缝在 φ≈0、t 小的地方；
3) 发片：沿发流铺在主体表面的窄带（程序生成发丝透明贴图），打破光滑轮廓；太阳穴垂几缕碎发；
4) 马尾：渐细的发束 + 外层发片；发箍、发圈沿用 hair.py。
发际线按定妆照标注（assets/identity/<cid>_landmarks_full.json 的 hairline）投到模型上。所有部件挂在头部骨骼上。"""
import os, sys, json, math, random
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import hair as HL

# rgb 发色（线性）；thick_top/side 头顶/两侧发层厚度（米，未缩放的基础网格）；tail 马尾长；tail_r 马尾最粗半径；tie_up 扎发点方向的高低
CARDS = {
 'classB': dict(style='ponytail', rgb=(0.007, 0.0055, 0.005), thick_top=0.006, thick_side=0.003, part_t=0.28, front_vol=0.007, corner=0.0, hl_drop=0.0178,   # 2026-11-21 发际线补偿改按拟合时眼睛高度后标定
                part_notch=0.0, part_v=0.005, junction={'R': 4, 'L': 4}, edge_cards=0, curtain={},
                tie_up=-0.10, tail=0.34, tail_r=0.026, n_cards=0, wisps={}, frame={'R': 5, 'L': 4}, baby=220, fly=90,
                headband=(0.010, 0.010, 0.012)),
 # 男生短发（style='short'）：发际线 = 照片上看得见的头发边缘（含刘海），厚度头顶厚、两侧薄；发流从前额往后脑梳
 'chen':   dict(style='short', no_part=True, rgb=(0.006, 0.005, 0.0045), thick_top=0.018, thick_side=0.009, part_t=0.28, front_vol=0.004, fringe=dict(n=160, az=48, len=(0.004, 0.025), w=(0.005, 0.011)), hl_drop=0.013,
                tie_up=-0.35, n_cards=0, baby=80, fly=220, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072), curl=0.25, sink=(0.0, -1.0, -0.6)),   # 韩式中分刘海
 'zhou':   dict(style='short', no_part=True, rgb=(0.005, 0.0045, 0.004), thick_top=0.022, thick_side=0.017, part_t=0.28, front_vol=0.004, fringe=dict(n=260, az=48, len=(0.004, 0.026), w=(0.004, 0.010), gap=9, sweep=18), tufts=dict(n=260, t0=(0.0, 0.75), len=(0.18, 0.4), amp=(0.006, 0.016), w=(0.010, 0.020)),
                tie_up=-0.35, n_cards=0, baby=60, fly=420, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072), hl_drop=0.019, curl=0.55, clump=0.005, sink=(0.0, -1.0, -0.3)),   # 偏长偏厚、乱、厚刘海
 'wang':   dict(style='short', no_part=True, rgb=(0.012, 0.010, 0.009), thick_top=0.022, thick_side=0.007, part_t=0.28, front_vol=0.006,
                tie_up=-0.35, n_cards=0, baby=60, fly=120, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072), curl=0.15, whorl=(0.25, 0.3, 1.0), sink=(-0.6, -0.4, -0.5)),   # 偏短侧分、往一侧梳
 'classA': dict(style='short', no_part=True, rgb=(0.006, 0.005, 0.0045), thick_top=0.010, thick_side=0.003, part_t=0.28, front_vol=0.002, fringe=dict(n=90, az=48, len=(0.001, 0.006), w=(0.003, 0.006)),
                tie_up=-0.35, n_cards=0, baby=100, fly=150, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072), curl=0.2, clump=0.002, sink=(0.0, -1.0, -0.5), base_hl2=dict(behind=-0.05, nape=-0.055)),   # 两侧推短、头顶短碎往前
 'lin':    dict(style='short', no_part=True, rgb=(0.006, 0.005, 0.0045), thick_top=0.03, thick_side=0.009, part_t=0.28, front_vol=0.012,
                tie_up=-0.35, n_cards=0, baby=80, fly=260, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072)),
}

def _photo_hairline(cid, bb, eyes, H):
    """定妆照上标注的发际线 → 模型上的 3D 点（按脸型拟合的视角与相似变换投影，再沿视线打到头上）→ [(方位角, 高度)]"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fp = os.path.join(root, 'assets', 'identity', cid + '_face_fit.json'); lp = os.path.join(root, 'assets', 'identity', cid + '_landmarks_full.json')
    if not (os.path.exists(fp) and os.path.exists(lp)): return None
    fit = json.load(open(fp, encoding='utf-8')); lm = json.load(open(lp, encoding='utf-8'))
    if 'hairline' not in lm or 'photo_to_model' not in fit: return None
    T = fit['photo_to_model']; s, R2, t2 = T['s'], T['R'], T['t']
    # 头相对照片拟合时上下移了多少（腿加长后抬回地面、脖子缩短都会移动头）：用两眼中心对齐。
    # 照片瞳孔点映射到模型平面后比眼球骨骼中心高约 2.4cm（未动身体时以抬地高度为准标定），减掉这个固定差
    ex = ((lm['eye_R'][0] + lm['eye_L'][0]) / 2, (lm['eye_R'][1] + lm['eye_L'][1]) / 2)
    lift = (eyes.z - fit['eye_z']) if 'eye_z' in fit else (eyes.z - (s * (R2[1][0] * ex[0] + R2[1][1] * -ex[1]) + t2[1]) - 0.024)
    Rm = Matrix.Rotation(math.radians(fit['pitch_deg']), 3, 'X') @ Matrix.Rotation(math.radians(fit['yaw_deg']), 3, 'Z'); Rt = Rm.transposed()
    out = []
    for x, y in lm['hairline']:
        u = s * (R2[0][0] * x + R2[0][1] * -y) + t2[0]; v = s * (R2[1][0] * x + R2[1][1] * -y) + t2[1]
        o = Rt @ Vector((u, -1.0, v)) + Vector((0, 0, lift)); d = Rt @ Vector((0, 1, 0))
        hit = bb.ray_cast(o, d, 3.0)[0]
        if hit is None: continue
        rel = hit - H; out.append((math.degrees(math.atan2(rel.x, -rel.y)), hit.z, hit))
    return out or None

def _front_dist(p3, drop, notch=None):
    """前额发际线 = 正面视角（x, z 平面）里按照片顺序连成的折线（两端往下延长 6cm）。
    返回 hd(p)：点到折线的带符号距离（米，头发一侧为正）。直线段就是直线、弧就是弧，竖直段也不会因为
    「每个方位角一个高度」的表示来回折成锯齿；只在前额（端点以前）使用，两侧/脑后仍按方位角的高度"""
    P = [(p.x, p.z - drop) for p in p3]
    if notch and notch[1] > 0:   # 分缝与发际线交界：发际线在分缝处凹进一个 V 形楔口（额头皮肤伸进分缝，两边头发各自分开）
        px, depth, hw = notch
        def z_at(x):
            for (ax, az_), (bx, bz) in zip(P, P[1:]):
                if min(ax, bx) <= x <= max(ax, bx) and abs(bx - ax) > 1e-9: return az_ + (bz - az_) * (x - ax) / (bx - ax)
            return max(z for _, z in P)
        zl, zr = z_at(px - hw), z_at(px + hw)
        left = [q for q in P if q[0] < px - hw]; right = [q for q in P if q[0] > px + hw]
        P = left + [(px - hw, zl), (px - hw * 0.35, (zl + zr) / 2 + depth * 0.7), (px, (zl + zr) / 2 + depth), (px + hw * 0.35, (zl + zr) / 2 + depth * 0.7), (px + hw, zr)] + right
    P = [(P[0][0], P[0][1] - 0.06)] + P + [(P[-1][0], P[-1][1] - 0.06)]
    segs = list(zip(P, P[1:]))
    def hd(x, z):
        best = None
        for (ax, az_), (bx, bz) in segs:
            dx, dz = bx - ax, bz - az_; L2 = dx * dx + dz * dz
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - ax) * dx + (z - az_) * dz) / L2))
            cx, cz = ax + dx * t, az_ + dz * t; d = math.hypot(x - cx, z - cz)
            if best is None or d < best[0]: best = (d, dx, dz, cx, cz)
        d, dx, dz, cx, cz = best
        side = dx * (z - cz) - dz * (x - cx)                            # 沿折线（从角色右往左）前进方向的左侧 = 头发一侧
        return d if side >= 0 else -d
    return hd

def _hairline(cid, bb, eyes, H, brow_z, rnd):
    bh = dict(front=0.010, temple=-0.024, ear=-0.016, behind=-0.045); bh.update(CARDS.get(cid, {}).get('base_hl', {})); bh.update(CARDS.get(cid, {}).get('base_hl2', {}))   # 男生：耳朵上方的发际线抬高，耳朵露出来
    base = HL._hairline_fn(eyes, brow_z, rnd, **bh)   # 两鬓压低：照片里头发盖住太阳穴、一直到眼睛高度
    raw = _photo_hairline(cid, bb, eyes, H)
    if not raw:
        base.hd = lambda p: p.z - base(math.degrees(math.atan2(p.x - H.x, -(p.y - H.y)))); return base
    p3 = [h for _, _, h in raw]
    pts = sorted((a, z) for a, z, _ in raw)
    # 从中间往两侧，发际线只降不升：两侧标注点越往下越靠前（方位角变小），按方位角排序后会来回折，额角出现台阶
    zs = [z for _, z in pts]; ic = min(range(len(pts)), key=lambda i: abs(pts[i][0]))
    for i in range(ic + 1, len(pts)): zs[i] = min(zs[i], zs[i - 1])
    for i in range(ic - 1, -1, -1): zs[i] = min(zs[i], zs[i + 1])
    pts = [(a, z) for (a, _), z in zip(pts, zs)]
    a0, a1 = pts[0][0], pts[-1][0]
    print('HAIRLINE photo', [(round(a), round(z - eyes.z, 3)) for a, z in pts], flush=True)
    def g(az):
        if a0 <= az <= a1:
            for (p, zp), (q, zq) in zip(pts, pts[1:]):
                if p <= az <= q: return zp + (zq - zp) * (az - p) / max(q - p, 1e-6)
        edge, ze = (a0, pts[0][1]) if az < a0 else (a1, pts[-1][1])
        w = HL._smooth(0, 25, abs(az - edge))                              # 标注范围外 25° 内过渡到通用发际线（耳后、后颈）
        v_ = ze * (1 - w) + base(az) * w
        return min(ze, v_) if CARDS.get(cid, {}).get('cap_edge', True) else v_   # 同学乙：不高于最后一个标注点（额角台阶）；男生要让发际线绕过耳朵往上走
    corner = CARDS.get(cid, {}).get('corner', 0.0); drop = CARDS.get(cid, {}).get('hl_drop', 0.0); notch = CARDS.get(cid, {}).get('part_notch', 0.0)
    def gs(az):   # 标注点连线按 ±8° 平滑（照片标注有起伏，直接连线在额角处形成台阶）
        return sum(g(az + d) for d in (-8, -4, 0, 4, 8)) / 5
    def f(az):
        # 额角压低：照片里发际线从中分处往两边下降得很快、额角被头发盖住，额头是圆润的鹅蛋形；
        # 压低从中线附近就开始，一直延续到太阳穴再缓缓收回（收得太急会在额角留下台阶）
        a = abs(az)
        return gs(az) - drop * (1 - HL._smooth(60, 90, a)) - corner * HL._smooth(6, 32, a) * (1 - HL._smooth(55, 80, a)) \
               + notch * (1 - HL._smooth(0, 7, a))    # 分缝尽头：发际线正中往上缩一个浅 V 口，两边头发各自往外分开
    hd2 = _front_dist(p3, drop, (H.x, CARDS.get(cid, {}).get('part_v', 0.0), 0.007)); y_lim = max(p3[0].y, p3[-1].y)
    def hd(p):
        """点 p 在发际线以上多少米（负数 = 在发际线以下）：前额用正面折线距离，两侧/脑后用方位角高度，中间平滑过渡"""
        zb = p.z - f(math.degrees(math.atan2(p.x - H.x, -(p.y - H.y))))
        w = HL._smooth(y_lim - 0.004, y_lim + 0.016, p.y)
        if w >= 1.0: return zb
        return hd2(p.x, p.z) * (1 - w) + zb * w
    f.hd = hd
    return f

class Flow:
    """发流坐标：过 N（中分点）、S（扎发点）两点的圆族。方向向量 d（从颅骨中心 H 出发的单位向量）↔ (φ, t)"""
    def __init__(s, H, N, S):
        s.H = H; n = (N - H).normalized(); m = (S - H).normalized()
        s.c = (m - n).normalized(); s.h = (m - n).length / 2; s.M = (n + m) / 2; s.Ml = s.M.length
        s.e1 = s.M.normalized(); s.e2 = s.c.cross(s.e1).normalized()          # φ=0：经过 N、S 中间方向（头顶）的圆 = 中线
    def coords(s, d):
        d = d.normalized(); w = d - s.M; w = w - s.c * w.dot(s.c)
        phi = math.atan2(w.dot(s.e2), w.dot(s.e1)); t = (d - s.M).dot(s.c) / s.h * 0.5 + 0.5
        return phi, max(0.0, min(1.0, t))
    def direction(s, phi, t):
        a = -s.h + 2 * s.h * t; cp = math.cos(phi)
        disc = s.Ml * s.Ml * cp * cp - s.Ml * s.Ml + 1 - a * a
        if disc < 0: return None
        b = -s.Ml * cp + math.sqrt(disc)
        w = s.e1 * cp + s.e2 * math.sin(phi)
        return (s.M + s.c * a + w * b).normalized()

def _parent(ob, rig, pinv):
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = 'head'; ob.matrix_parent_inverse = pinv.copy()

def _link(name, me):
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob

def _strand_tex(nt, uv_sock, freq, seed):
    """发丝条纹（0~1）：沿 UV 的 x 方向密排的细条纹，噪声扭曲 + 粗细两层，像一缕缕头发"""
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (freq, 1.0, 1.0); mp.inputs['Location'].default_value = (seed * 0.37, 0, 0)
    nt.links.new(uv_sock, mp.inputs['Vector'])
    w1 = nt.nodes.new('ShaderNodeTexWave'); w1.wave_type = 'BANDS'; w1.bands_direction = 'X'; w1.inputs['Scale'].default_value = 1.0
    w1.inputs['Distortion'].default_value = 6.0; w1.inputs['Detail'].default_value = 3.0; w1.inputs['Detail Scale'].default_value = 0.6
    nt.links.new(mp.outputs['Vector'], w1.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 4.0
    mp2 = nt.nodes.new('ShaderNodeMapping'); mp2.inputs['Scale'].default_value = (freq * 2.7, 1.5, 1.0); nt.links.new(uv_sock, mp2.inputs['Vector'])
    nt.links.new(mp2.outputs['Vector'], nz.inputs['Vector'])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'FLOAT'; mx.inputs['Factor'].default_value = 0.45
    nt.links.new(w1.outputs['Fac'], mx.inputs[2]); nt.links.new(nz.outputs['Fac'], mx.inputs[3])
    return mx.outputs[0]

def _hair_mat(name, rgb, kind, part=None, freq=160.0, seed=0, part_cx=0.0, part_n=(0.0, 0.0, 0.0)):
    """kind = 'mass' 发型主体（不透明，分缝处透出头皮色） / 'card' 发片（条纹决定透明度，两侧、末端渐隐）"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; uv = nt.nodes.new('ShaderNodeUVMap')
    st = _strand_tex(nt, uv.outputs['UV'], freq, seed)
    N_, L_ = nt.nodes.new, nt.links.new
    def math(op, a, b_=None):
        n = N_('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b_)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L_(v, n.inputs[i])
        return n.outputs[0]
    def mrange(v, a, b_):   # a→0、b→1 的平滑过渡（a、b 可以是数值或接口）
        r = N_('ShaderNodeMapRange'); r.interpolation_type = 'SMOOTHSTEP'; L_(v, r.inputs['Value'])
        for sock, x in ((r.inputs['From Min'], a), (r.inputs['From Max'], b_)):
            if isinstance(x, (int, float)): sock.default_value = x
            else: L_(x, sock)
        return r.outputs['Result']
    if kind == 'mass' and part is not None:
        # 发流坐标在前额中分点 N 汇成一个极点：越靠近 N，同样的 Δφ 在头皮上越窄。按「头皮上的实际距离」算：
        # 离分缝的距离 ≈ |x−0.5|·2π·ρ，ρ ≈ 0.25·t（米，从 N 沿头顶往后的距离）
        sep = N_('ShaderNodeSeparateXYZ'); L_(uv.outputs['UV'], sep.inputs['Vector'])
        jit = N_('ShaderNodeTexNoise'); jit.inputs['Scale'].default_value = 35.0; jit.inputs['Detail'].default_value = 3.0
        jm = N_('ShaderNodeMapping'); jm.inputs['Scale'].default_value = (1.0, 1.0, 1.0); L_(uv.outputs['UV'], jm.inputs['Vector']); L_(jm.outputs['Vector'], jit.inputs['Vector'])
        # 分缝就在头部正中线上：离分缝的距离 = 物体坐标里离中线（x=cx）的左右距离（米），比用发流坐标估算准
        tc = N_('ShaderNodeTexCoord'); so = N_('ShaderNodeSeparateXYZ'); L_(tc.outputs['Object'], so.inputs['Vector'])
        dist = math('ABSOLUTE', math('SUBTRACT', so.outputs['X'], part_cx))
        dist = math('ADD', dist, math('MULTIPLY', math('SUBTRACT', jit.outputs['Fac'], 0.5), 0.0022))   # 分缝边缘不是直线
        # 横跨分缝的细发丝（条纹垂直于分缝），只用来打散分缝边缘（混进头发纹理会出现方形色块）
        swap = N_('ShaderNodeCombineXYZ'); L_(sep.outputs['Y'], swap.inputs['X']); L_(sep.outputs['X'], swap.inputs['Y'])
        st_perp = _strand_tex(nt, swap.outputs['Vector'], 420.0, seed + 7)
        # 离分缝起点 N（前额发际线正中）的实际距离（米）：分缝长度、前宽后窄、尽头张开都按它算
        vn = N_('ShaderNodeVectorMath'); vn.operation = 'DISTANCE'; L_(tc.outputs['Object'], vn.inputs[0]); vn.inputs[1].default_value = tuple(part_n)
        dN = vn.outputs['Value']
    col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'
    col.inputs[6].default_value = (*(c * 0.40 for c in rgb), 1); col.inputs[7].default_value = (*(c * 3.2 for c in rgb), 1)   # 一缕缕的明暗对比（黑发上太弱就看不出发丝）
    nt.links.new(st, col.inputs['Factor'])
    rough = nt.nodes.new('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = 0.42; rough.inputs['To Max'].default_value = 0.66   # 原来 0.30~0.50 像塑料
    nt.links.new(st, rough.inputs['Value']); nt.links.new(rough.outputs['Result'], b.inputs['Roughness'])
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.07   # 镜面反射太强会把环境反成一层灰雾，黑发发灰
    if 'Coat Weight' in b.inputs: b.inputs['Coat Weight'].default_value = 0.0; b.inputs['Coat Roughness'].default_value = 0.35   # 原来像塑料头盔一样反光
    base_col = col.outputs[2]
    if kind == 'mass' and part is not None:
        # 分缝：一直通到发际线，前宽后窄（半宽 3.5mm → 1.5mm），往后淡出；边缘虚、有发丝跨过去；露出偏灰的米色头皮
        hw = math('SUBTRACT', 0.0018, math('MULTIPLY', math('MINIMUM', dN, 0.07), 0.0011 / 0.07))
        # 分缝尽头（发际线往里 1.8cm 内）自然往两边张开成 V 字，不是一条线直直撞到额头上
        hw = math('ADD', hw, math('MULTIPLY', mrange(dN, 0.010, 0.0), 0.0015))   # 只在最前 1cm 轻微张开（张大了像个灰色水滴）
        r1 = mrange(dist, math('MULTIPLY', hw, 1.6), math('MULTIPLY', hw, 0.2))
        r2 = mrange(dN, 0.075, 0.045)                                     # 分缝长约 6~7cm，往后淡出
        fn = N_('ShaderNodeTexNoise'); fn.inputs['Scale'].default_value = 900.0; fn.inputs['Detail'].default_value = 2.0   # 横跨分缝的零散细发（规则条纹像梯子横档）
        cross = math('ADD', 0.35, math('MULTIPLY', mrange(fn.outputs['Fac'], 0.62, 0.42), 0.65))
        pm = math('MULTIPLY', math('MULTIPLY', r1, r2), cross)
        pc = N_('ShaderNodeMix'); pc.data_type = 'RGBA'; L_(pm, pc.inputs['Factor'])
        sk = N_('ShaderNodeMix'); sk.data_type = 'RGBA'; L_(mrange(dN, 0.014, 0.003), sk.inputs['Factor'])   # 越靠近交界越接近额头肤色（楔口里是额头皮肤）
        sk.inputs[6].default_value = (0.080, 0.063, 0.055, 1); sk.inputs[7].default_value = (0.20, 0.14, 0.11, 1)
        L_(base_col, pc.inputs[6]); L_(sk.outputs[2], pc.inputs[7]); base_col = pc.outputs[2]
    nt.links.new(base_col, b.inputs['Base Color'])
    if kind == 'card':   # 透明度：条纹 × 横向两侧渐隐 × 末端渐隐（发片 UV：x 横向 0~1，y 沿长度 0~1）
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(uv.outputs['UV'], sep.inputs['Vector'])
        a1 = nt.nodes.new('ShaderNodeMapRange'); a1.inputs['From Min'].default_value = 0.42; a1.inputs['From Max'].default_value = 0.62; nt.links.new(st, a1.inputs['Value'])
        e = nt.nodes.new('ShaderNodeMath'); e.operation = 'PINGPONG'; e.inputs[1].default_value = 0.5; nt.links.new(sep.outputs['X'], e.inputs[0])
        e2 = nt.nodes.new('ShaderNodeMapRange'); e2.inputs['From Min'].default_value = 0.0; e2.inputs['From Max'].default_value = 0.25; nt.links.new(e.outputs[0], e2.inputs['Value'])
        tip = nt.nodes.new('ShaderNodeMapRange'); tip.inputs['From Min'].default_value = 1.0; tip.inputs['From Max'].default_value = 0.78; nt.links.new(sep.outputs['Y'], tip.inputs['Value'])
        m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; nt.links.new(a1.outputs['Result'], m1.inputs[0]); nt.links.new(e2.outputs['Result'], m1.inputs[1])
        m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(tip.outputs['Result'], m2.inputs[1])
        nt.links.new(m2.outputs[0], b.inputs['Alpha'])
        if hasattr(m, 'surface_render_method'): m.surface_render_method = 'DITHERED'
        else: m.blend_method = 'HASHED'
        m.use_backface_culling = False
    return m

def _ribbon(bm, uvl, pts, normals, width, u0=0.0, u1=1.0):
    """一条发片：沿 pts 的窄带，宽度方向 = 法线 × 走向；UV x 横向 0~1，y 沿长度 0~1；宽度往末端收窄"""
    n = len(pts); rows = []
    for i, (p, nn) in enumerate(zip(pts, normals)):
        tg = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        side = nn.cross(tg).normalized() * width * (1 - 0.55 * i / max(1, n - 1)) / 2
        rows.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    for i in range(n - 1):
        (a0, b0), (a1, b1) = rows[i], rows[i + 1]
        f = bm.faces.new((a0, b0, b1, a1))
        for lp, (x, y) in zip(f.loops, ((u0, i / (n - 1)), (u1, i / (n - 1)), (u1, (i + 1) / (n - 1)), (u0, (i + 1) / (n - 1)))):
            lp[uvl].uv = (x, y)

def build(cid, rig, body, shell, seed=1):
    S = CARDS[cid]; rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    bb, bv, bp = HL._world_bvh(body, dg)
    eyes, H, brow_z = HL._head_frame(rig)
    hb = rig.pose.bones['head']; pinv = (rig.matrix_world @ hb.matrix @ Matrix.Translation((0, hb.length, 0))).inverted()
    hl = _hairline(cid, bb, eyes, H, brow_z, rnd)
    tris, n_main, cap_faces = HL._scalp(bv, bp, H, lambda az: hl(az) - 0.015, soft=0.004)   # 选面放宽一点，边缘由 hl.hd 精确决定
    # ---- 关键点：中分点 N（前额发际线中点稍后）、扎发点 S（后脑，耳朵上缘略低）----
    hit_n = bb.ray_cast(H, Vector((0, -0.55, 1.0)).normalized(), 0.3)[0]
    a_front = 0.0; z_front = hl(a_front)
    best = None
    for k in range(60):   # 中线上从头顶往前额找发际线位置
        d = Vector((0, -math.sin(k / 60 * 1.4), math.cos(k / 60 * 1.4)))
        hit = bb.ray_cast(H, d, 0.3)[0]
        if hit is not None and hl.hd(hit) >= 0.0: best = hit   # 按前额折线（含分缝楔口）找发际线位置
    N = best if best is not None else hit_n
    dirT = Vector((0, 1.0, S['tie_up'])).normalized()
    hit_t = bb.ray_cast(H, dirT, 0.3)[0]; Tsk = hit_t if hit_t is not None else H + dirT * 0.10
    if S.get('style') == 'short':   # 男生短发：从头顶发旋往四周放射（刘海往前往下垂，不是往后梳成背头）
        wd = Vector(S.get('whorl', (0.0, 0.35, 1.0))).normalized(); hw_ = bb.ray_cast(H, wd, 0.3)[0]
        N = hw_ if hw_ is not None else H + wd * 0.1
        sk_ = Vector(S.get('sink', (0.0, -1.0, -0.9))).normalized(); Tsk = H + sk_ * 0.1   # 发流汇向脸前下方（不能取正对面：圆族退化）
    flow = Flow(H, N, Tsk)
    def crown(z): return HL._smooth(eyes.z + 0.02, H.z + 0.08, z)   # 太阳穴、耳上服帖（照片里两侧紧贴头皮），头顶才厚
    # ---- 1) 发型主体 ----
    # 头皮网格很粗（太阳穴一格约 2cm）：直接用发际线以上的面，边缘是锯齿，再一细分往里缩一格 → 太阳穴秃一块。
    # 改为：多取一圈面、细分两次并贴回头皮；发际线以下的部分沉进皮肤 1mm，露出来的边缘正好落在发际线上
    def az_of(p): rel = p - H; return math.degrees(math.atan2(rel.x, -rel.y))
    sel = set(cap_faces)
    vf = {}
    for fi, p in enumerate(bp):
        for i in p: vf.setdefault(i, set()).add(fi)
    for _ in range(7 if S.get('style') == 'short' else 2):   # 选面要比发际线多出一大圈：露出来的边缘只由发际线距离决定（选面边界是粗网格台阶）
        ring = {g for fi in sel for i in bp[fi] for g in vf[i]} - sel
        for g in ring:
            c = sum((bv[i] for i in bp[g]), Vector()) / len(bp[g]); rel = c - H
            if rel.length < (0.23 if S.get('style') == 'short' else 0.17) and c.z > eyes.z - (0.17 if S.get('style') == 'short' else 0.06) and not (c.y < eyes.y + 0.03 and c.z < brow_z + 0.01): sel.add(g)   # 男生后颈发际线更低：选面截到眼下 12cm（原来 6cm，后颈边缘是网格的台阶）
    ear_kd = None; ear_fy = None; ear_lz = ear_cy = None
    if S.get('style') == 'short':   # 男生：头发包住耳朵周围（耳前鬓角、耳上、耳后），只把耳朵本身挖掉——原来整体抬高发际线让耳朵露出来，侧面秃了一大块
        ev_ = body.evaluated_get(dg); me_ = ev_.to_mesh(); gi_ = body.vertex_groups.get('ears')
        if gi_ is not None:
            ear = {i for i, v in enumerate(me_.vertices) if any(g.group == gi_.index and g.weight > 0.3 for g in v.groups)}
            from mathutils.kdtree import KDTree as _KDe
            kde = _KDe(len(ear))
            for k_, i in enumerate(ear): kde.insert(bv[i], k_)
            kde.balance()
            sel = {fi for fi in sel if sum(i in ear for i in bp[fi]) < len(bp[fi])}   # 只去掉完全在耳朵上的面；耳朵边缘改在厚度里平滑下沉（按面挖会留锯齿洞）
            ear_kd = kde; ear_fy = min(bv[i].y for i in ear); ear_lz = min(bv[i].z for i in ear); ear_cy = sum(bv[i].y for i in ear) / len(ear)   # 耳朵最前沿、耳垂高度、耳朵中心
            print('EAR CUT', len(ear), flush=True)
        ev_.to_mesh_clear()
    used = sorted({i for fi in sel for i in bp[fi]}); remap = {o: k for k, o in enumerate(used)}
    bm = bmesh.new(); vs = [bm.verts.new(bv[i]) for i in used]
    for fi in sorted(sel):
        try: bm.faces.new([vs[remap[i]] for i in bp[fi]])
        except ValueError: pass
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
    for v in bm.verts:   # 细分出的点在平面上，贴回头皮曲面
        loc = bb.find_nearest(v.co)[0]
        if loc is not None: v.co = loc
    bm.normal_update()
    # 厚度场：头顶厚、两侧服帖；发际线往里 1cm 长满；分缝处凹一道；发际线以下沉进皮肤
    thick = {}
    for v in bm.verts:
        rel = v.co - H; dz = hl.hd(v.co)
        phi, t = flow.coords(rel)
        az = abs(az_of(v.co)); wf = 1 - HL._smooth(30, 50, az)                 # 前额区（额角以内；两侧不加蓬松，否则像头盔）
        # 发际线处做成圆润的发帘边（前额起得快），不是贴着皮肤削薄的硬边
        th = (S['thick_side'] + (S['thick_top'] - S['thick_side']) * crown(v.co.z)) * \
             ((0.12 + 0.88 * HL._smooth(0.0, 0.010, dz)) * (1 - wf) + (0.40 + 0.60 * HL._smooth(0.0, 0.007, dz)) * wf)
        # 刘海的蓬松：中分两侧的头发从分缝处隆起、呈弧形往两边垂到额角（照片里像两片帘子）；发际线后 1~4cm 最鼓
        fv = S.get('front_vol', 0.0) * wf * HL._smooth(0.0, 0.012, dz) * (1 - HL._smooth(0.035, 0.07, dz)) * (1 - HL._smooth(0.40, 0.60, t))
        th += fv * (0.55 + 0.45 * HL._smooth(0.04, 0.25, abs(phi)))
        if abs(phi) < 0.05 and t < S['part_t'] and rel.y < 0.03: th *= 0.70 + 0.30 * HL._smooth(0.012, 0.05, abs(phi))   # 分缝浅浅一道（原来两侧鼓成两个包）
        th *= 0.35 + 0.65 * HL._smooth(0.005, 0.025, (v.co - N).length)   # 分缝与发际线交界处头发变薄（照片里楔口两边是稀疏的细发，不是厚厚一块）
        if S.get('style') == 'short' and rel.y > 0.02: th = max(0.003 * HL._smooth(0.0, 0.004, dz), th * (0.7 + 0.3 * HL._smooth(H.z - 0.05, H.z + 0.02, v.co.z)))   # 后脑勺下半略薄，但至少 3mm（后颈是凹面，皮肤细分后往外鼓，太薄会透出肉色）
        if dz < 0: th = -(0.0012 + (0.0038 if S.get('style') == 'short' else 0.0)) * HL._smooth(0.0, 0.006, -dz)   # 男生：沉得更深（身体渲染细分后凸面会往里收，浅沉的头发从下颌、鬓角透出来成黑线）
        if ear_kd is not None:   # 耳朵周围 1.2cm 平滑收到皮肤下
            de = ear_kd.find(v.co)[2]
            if de < 0.02: th = min(th, th * HL._smooth(0.008, 0.02, de) - 0.005 * (1 - HL._smooth(0.008, 0.02, de)))   # 耳朵周围 2cm 收到皮肤下，不盖住耳廓
        if v.is_boundary: th = -0.005 if S.get('style') == 'short' else -0.0015
        thick[v] = th
    for _ in range(8):   # 平滑厚度（避免网格密度不均造成的鼓包）
        thick = {v: (thick[v] * 2 + sum(thick[e.other_vert(v)] for e in v.link_edges)) / (2 + len(v.link_edges)) if not v.is_boundary else thick[v] for v in bm.verts}
    if S.get('style') == 'short':   # 平滑会把发际线以下的那条带子又抬出皮肤（后颈露出删面留下的台阶边）：平滑后再压回去
        for v in bm.verts:
            d_ = hl.hd(v.co)
            if d_ < 0: thick[v] = min(thick[v], -0.005 * HL._smooth(0.0, 0.003, -d_))
    for v in bm.verts:
        nn = v.normal if v.normal.dot(v.co - H) > 0 else -v.normal
        out = (nn + (v.co - H).normalized()).normalized()
        v.co = v.co + out * (((0.0025 if S.get('style') == 'short' else 0.0008) + thick[v]) if thick[v] >= 0 else thick[v])
    if S.get('style') == 'short':   # 发际线 1.5cm 以下的部分直接删掉（沉在皮肤下的那层在后颈、脖子上随姿势又顶出来，像套了一圈）
        def _back(p): return abs(az_of(p)) > 105
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(hl.hd(v.co) < (-0.003 if _back(v.co) else -0.010) for v in f.verts)], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        for v in bm.verts:   # 耳后、后颈：沉在皮肤下的发尾删掉后，剩下的边缘点沿竖直方向挪到发际线上、贴回头皮外 1.5mm——边缘就是平滑的发际线，不是网格台阶
            d_ = hl.hd(v.co)
            if d_ < 0 and _back(v.co):
                loc, nrm, _, _ = bb.find_nearest(v.co + Vector((0, 0, -d_)))
                if loc is not None: v.co = loc + (nrm if nrm.dot(loc - H) > 0 else -nrm) * 0.0015
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        uvs = [flow.coords(lp.vert.co - H) for lp in f.loops]
        ph = [p for p, _ in uvs]
        if max(ph) - min(ph) > math.pi:   # 跨过 φ=±π 的接缝（在脸下方，基本不会有）
            uvs = [(p + 2 * math.pi if p < 0 else p, t) for p, t in uvs]
        for lp, (p, t) in zip(f.loops, uvs): lp[uvl].uv = (p / (2 * math.pi) + 0.5, t)
    mm = bpy.data.meshes.new(cid + '_hairmass'); bm.to_mesh(mm); bm.free()
    for poly in mm.polygons: poly.use_smooth = True
    mm.materials.append(_hair_mat(cid + '_hairmass', S['rgb'], 'mass', part=None if S.get('no_part') else S['part_t'], seed=seed, part_cx=H.x, part_n=tuple(N)))
    mass = _link(cid + '_hairmass', mm)
    sd = mass.modifiers.new('subdiv', 'SUBSURF'); sd.levels = 1; sd.render_levels = 2
    _parent(mass, rig, pinv)
    bpy.context.view_layer.update()
    mb = BVHTree.FromObject(mass, bpy.context.evaluated_depsgraph_get())
    def on_mass(d, lift):
        hit, nn, _, _ = mb.ray_cast(H, d, 0.4)
        if hit is None: return None, None
        nn = nn if nn.dot(d) > 0 else -nn
        return hit + nn * lift, nn
    # ---- 2) 发片：沿发流铺在主体表面 ----
    T = on_mass(dirT, 0.0)[0] or Tsk + dirT * S['thick_top']
    bmc = bmesh.new(); uvc = bmc.loops.layers.uv.new('UVMap'); ncard = 0
    for _ in range(S['n_cards'] * 3):
        if ncard >= S['n_cards']: break
        phi = rnd.uniform(-math.pi * 0.92, math.pi * 0.92); t0 = rnd.random() ** 2 * 0.3; t1 = rnd.uniform(0.9, 1.0)   # 细长、从发际线附近一直到扎发点
        pts, nrs = [], []
        for k in range(24):
            d = flow.direction(phi, t0 + (t1 - t0) * k / 23)
            if d is None: break
            p, nn = on_mass(d, 0.0005 + rnd.random() * 0.0009)   # 紧贴主体表面（翘高了像鳞片）
            if p is None:
                if pts: break
                else: continue
            pts.append(p); nrs.append(nn)
        if len(pts) < 8: continue
        _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.004, 0.008), rnd.random(), rnd.random() + 1.0); ncard += 1
    def on_skin(d, lift):
        hit, nn, _, _ = bb.ray_cast(H, d, 0.4)
        if hit is None: return None, None
        nn = nn if nn.dot(d) > 0 else -nn
        return hit + nn * lift, nn
    def outer(d, lift_m, lift_s):   # 头发表面或皮肤，取靠外的那个（发际线附近从皮肤过渡到头发上）
        pm, nm = on_mass(d, lift_m); ps, ns = on_skin(d, lift_s)
        if pm is None: return ps, ns
        if ps is None: return pm, nm
        return (pm, nm) if (pm - H).length >= (ps - H).length else (ps, ns)
    def at_hairline(az, dz):
        """方位角 az 上、发际线以上 dz（负数 = 发际线以下）的头皮方向"""
        best = None
        for el in [i * 0.01 for i in range(-40, 140)]:
            d = Vector((math.sin(math.radians(az)) * math.cos(el), -math.cos(math.radians(az)) * math.cos(el), math.sin(el)))
            h_ = bb.ray_cast(H, d, 0.4)[0]
            if h_ is not None and h_.z >= hl(az) + dz: best = d; break
        return best
    # 发际线的细碎胎毛：从发际线下方 1~4mm 的额头皮肤起，先往上越过发际线、再顺着发流走进头发——边缘变虚，不再是一条硬线
    # （额头上的「发流」是往下经过脸的，所以不能从皮肤那点直接跟发流走）
    nedge = 0
    for k in range(S.get('edge_cards', 0)):
        az = rnd.uniform(-64, 64)
        d0 = at_hairline(az, -rnd.uniform(0.002, 0.007)); d1 = at_hairline(az, 0.006)
        if d0 is None or d1 is None: continue
        p0, n0 = on_skin(d0, 0.0004)
        if p0 is None: continue
        pts, nrs = [p0], [n0]
        phi, t = flow.coords(d1); L = rnd.uniform(0.04, 0.09)
        for j in range(7):
            d = flow.direction(phi, min(1.0, t + L * j / 6))
            if d is None: break
            p, nn = outer(d, 0.0005, 0.0004)
            if p is None: break
            pts.append(p); nrs.append(nn)
        if len(pts) < 5: continue
        pts.reverse(); nrs.reverse()                                  # 发片 UV 末端（y=1）渐隐：让皮肤那头最淡
        _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.003, 0.005), rnd.random(), rnd.random() + 0.3); nedge += 1
    # 刘海帘：中分两侧各几缕，从分缝旁沿着发际线内侧走一道弧到额角，再顺着脸侧垂到脸颊（照片里两侧像帘子一样垂下）
    for side, cnt in S.get('curtain', {}).items():
        sx = -1.0 if side == 'R' else 1.0
        for k in range(cnt):
            inset = rnd.uniform(0.002, 0.008); a1 = rnd.uniform(55, 68); lift = rnd.uniform(0.003, 0.005); pts, nrs = [], []
            for j in range(14):
                az = sx * (4 + (a1 - 4) * j / 13)
                d = at_hairline(az, inset * (1 - 0.6 * j / 13))
                if d is None: continue
                p, nn = outer(d, lift, 0.003)
                if p is None: continue
                pts.append(p); nrs.append(nn)
            if len(pts) < 5: continue
            last = pts[-1]; Lh = rnd.uniform(0.05, 0.10); ph = rnd.uniform(0, 6.28)
            for j in range(1, 13):
                f = j / 12; q = last + Vector((sx * (0.003 + 0.006 * f), -0.003 * f, -Lh * f)) + Vector((sx * 0.002 * math.sin(f * 4 + ph), 0, 0))
                loc, nn, _, dd = bb.find_nearest(q)
                if loc is not None:
                    nn = nn if (q - loc).dot(nn) >= 0 else -nn
                    if dd < 0.003: q = loc + nn * 0.003
                pts.append(q); nrs.append((q - Vector((H.x, H.y, q.z))).normalized())
            _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.004, 0.006), rnd.random(), rnd.random() + 0.5)
    # 分缝与发际线交界：楔口两侧几缕细发，从分缝旁弯出来、越过发际线搭到额头边缘（照片里交界处是稀疏弯垂的细发，不是齐边）
    for side, cnt in S.get('junction', {}).items():
        sx = -1.0 if side == 'R' else 1.0
        for k in range(cnt):
            a = N + Vector((sx * rnd.uniform(0.001, 0.005), rnd.uniform(0.012, 0.028), rnd.uniform(0.004, 0.012)))   # 分缝旁、发际线往里
            b_ = N + Vector((sx * rnd.uniform(0.010, 0.022), rnd.uniform(-0.004, 0.0), -rnd.uniform(0.004, 0.012)))  # 越过发际线，落在额头上
            da, db = (a - H).normalized(), (b_ - H).normalized(); pts, nrs = [], []
            for j in range(12):
                f_ = j / 11; d = da.slerp(db, f_ ** 0.8)
                p, nn = outer(d, 0.0007, 0.0005)
                if p is None: continue
                pts.append(p); nrs.append(nn)
            if len(pts) >= 6: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.0015, 0.0028), rnd.random(), rnd.random() + 0.25)
    # 脸侧碎发束（用户：刘海等碎头发没体现出来）：照片里两侧一缕缕碎发从太阳穴发际线出来，沿脸的外轮廓垂到下巴附近，
    # 正面看正好搭在脸边。做法：在眼睛后方 1~5cm 的竖切面上，逐高度从中线往外打射线找到脸侧皮肤（= 正面看到的脸边），
    # 发丝贴着它往下走（离皮肤 2~5mm），每束 3~5 条细发片、末端散开、轻微摆动
    def side_skin(z, y, sx):
        h_ = bb.ray_cast(Vector((H.x + sx * 0.005, y, z)), Vector((sx, 0, 0)), 0.2)
        if h_[0] is None: return None, None
        nn = h_[1] if h_[1].x * sx > 0 else -h_[1]
        return h_[0], nn
    nclump = 0
    for side, cnt in S.get('frame', {}).items():
        sx = -1.0 if side == 'R' else 1.0
        for k in range(cnt):
            yb = eyes.y + rnd.uniform(0.026, 0.056)                         # 竖切面：眼后 1~5cm（越靠前越搭在脸上）
            tuck = False                                                    # 往耳后别的会横穿耳朵，先不用
            # 发根高度 = 这个竖切面上的实际发际线（从上往下找到发际线距离 < 2mm 的位置）：统一用太阳穴的高度，
            # 靠前的碎发发根会落在发际线下面的皮肤上，和头发之间露出一段皮肤（用户：碎发没和主体头发连起来）
            z_top = None
            for i in range(80):
                z = eyes.z + 0.09 - i * 0.002
                s_, _ = side_skin(z, yb, sx)
                if s_ is not None and hl.hd(s_) < 0.002: z_top = z; break
            if z_top is None: continue
            z_bot = eyes.z - (rnd.uniform(0.03, 0.06) if tuck else rnd.uniform(0.05, 0.10))
            lift0 = rnd.uniform(0.002, 0.005); ph = rnd.uniform(0, 6.28)
            s0, n0 = side_skin(z_top, yb, sx)
            if s0 is None: continue
            L = z_top - z_bot
            for r in range(rnd.randint(6, 9)):                               # 每束多条细发（宽发片侧面看像带子）
                dy = rnd.uniform(-0.005, 0.005); lift = lift0 + rnd.uniform(0, 0.003); pts, nrs = [], []
                start = s0 + n0 * lift + Vector((0, dy, rnd.uniform(-0.003, 0.003)))
                # 发根藏在主体头发里（用户：碎发没和主要头发连起来，显得很奇怪）：从发际线以上 2~3.5cm 的头发表面下方出发，
                # 贴着头发表面往下，到发际线处钻出来再垂下
                rise = rnd.uniform(0.02, 0.035)
                for j in range(8):
                    t_ = j / 8; z = start.z + rise * (1 - t_)
                    h_ = mb.ray_cast(Vector((H.x + sx * 0.005, start.y, z)), Vector((sx, 0, 0)), 0.2)
                    if h_[0] is None: continue
                    nn_ = h_[1] if h_[1].x * sx > 0 else -h_[1]
                    pts.append(h_[0] + nn_ * (-0.0008 + 0.0018 * t_)); nrs.append(Vector((sx, -0.35, 0)).normalized())
                for j in range(22):
                    f = j / 21
                    # 自然垂下：先顺着头侧往下、略往外，再竖直垂落；末端散开、轻微摆动；别到耳后的那些下半段往后弯
                    back = 0.035 * HL._smooth(0.35, 1.0, f) if tuck else 0.0
                    q = start + Vector((sx * (0.003 * f + 0.004 * f * f), -0.006 * f + 0.004 * f * f * (r - 4) / 3 + back, -L * f)) \
                        + Vector((sx * 0.0025 * math.sin(f * 4.5 + ph + r * 0.7), 0, 0))
                    loc, nn, _, dd = bb.find_nearest(q)
                    if loc is not None:
                        nn = nn if (q - loc).dot(nn) >= 0 else -nn
                        if (q - loc).dot(nn) < 0 or dd < 0.0025: q = loc + nn * 0.0025   # 碰到脸就让开，搭在皮肤上
                    if pts and (q - pts[-1]).length < 1e-4: continue
                    pts.append(q); nrs.append(Vector((sx, -0.35, 0)).normalized())   # 发片朝外前方：正面、侧面都看得见
                if len(pts) >= 8: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.0015, 0.003), rnd.random(), rnd.random() + 0.25)
            nclump += 1
    print('HAIR FRAME clumps', nclump, flush=True)
    # 前额发际线胎毛（用户：侧面有碎发，正脸刘海和头顶也应该有）：发际线边缘一圈很短很细的绒毛，
    # 从头发里出来、越过发际线 3~8mm 搭在额头上，发梢渐隐——发际线不再是一条硬边
    nbaby = 0
    for k in range(S.get('baby', 0)):
        az = rnd.uniform(-62, 62)
        d0 = at_hairline(az, rnd.uniform(0.003, 0.008)); d1 = at_hairline(az + rnd.uniform(-4, 4), -rnd.uniform(0.003, 0.008))
        if d0 is None or d1 is None: continue
        pts, nrs = [], []; cr = rnd.uniform(-0.6, 0.6)
        for j in range(7):
            f = j / 6; d = d0.slerp(d1, f)
            d = (d + Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0)) * cr * 0.03 * math.sin(math.pi * f)).normalized()   # 微微弯
            p, nn = outer(d, 0.0006 + 0.0008 * math.sin(math.pi * f), 0.0004)
            if p is None: continue
            pts.append(p); nrs.append(nn)
        if len(pts) >= 4: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.0008, 0.0014), rnd.random(), rnd.random() + 0.15); nbaby += 1
    # 头发表面的零星碎发：沿梳头方向的细发丝，中段微微拱起离开头发表面，打破光滑的「头盔感」
    nfly = 0
    for k in range(S.get('fly', 0)):
        phi = rnd.uniform(-math.pi * 0.85, math.pi * 0.85); t0 = rnd.uniform(0.02, 0.55); tl = rnd.uniform(0.06, 0.20)
        amp = rnd.uniform(0.002, 0.007); dphi = rnd.uniform(-0.08, 0.08); pts, nrs = [], []
        for j in range(12):
            f = j / 11; d = flow.direction(phi + dphi * f, min(1.0, t0 + tl * f))
            if d is None: break
            p, nn = on_mass(d, 0.0004 + amp * math.sin(math.pi * f) ** 1.5)
            if p is None: break
            pts.append(p); nrs.append(nn)
        if len(pts) >= 6: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.0007, 0.0013), rnd.random(), rnd.random() + 0.12); nfly += 1
    print('HAIR BABY', nbaby, 'FLY', nfly, flush=True)
    # 碎刘海（用户：刘海边缘像一刀切的碗盖）：一缕缕从发际线内 2~4cm 的头发表面出发，越过发际线长短不一地垂到额头上，
    # 末端尖、宽度不一——发际线变成参差不齐的锯齿边
    nfr = 0; FR = S.get('fringe')
    if FR:
        for k in range(FR.get('n', 120)):
            az = rnd.uniform(-FR.get('az', 60), FR.get('az', 60))
            if abs(az) < FR.get('gap', 0) and rnd.random() < 0.85: continue   # 刘海中间分开一点
            sw = math.copysign(rnd.uniform(0, FR.get('sweep', 0)), az) + rnd.uniform(-6, 6)   # 往两边扫
            d0 = at_hairline(az, rnd.uniform(0.02, 0.04)); d1 = at_hairline(az + sw, -rnd.uniform(*FR.get('len', (0.004, 0.022))))
            if d0 is None or d1 is None: continue
            pts, nrs = [], []; lift = rnd.uniform(0.0015, 0.004)
            for j in range(10):
                f = j / 9; d = d0.slerp(d1, f)
                p, nn = outer(d, lift + 0.002 * math.sin(math.pi * f), 0.0012 + lift * (1 - f))
                if p is None: continue
                pts.append(p); nrs.append(nn)
            if len(pts) >= 6: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(*FR.get('w', (0.005, 0.011))), rnd.random(), rnd.random() + 0.6); nfr += 1
    print('HAIR FRINGE', nfr, flush=True)
    # 成簇的碎发层（蓬松、凌乱的发型）：一簇簇较宽的发片沿梳头方向铺在头发表面，中段拱起离开表面，前面的越过发际线搭到额头/太阳穴上
    TU = S.get('tufts'); ntu = 0
    if TU:
        for k in range(TU.get('n', 150)):
            phi = rnd.uniform(-math.pi * 0.9, math.pi * 0.9); t0 = rnd.uniform(*TU.get('t0', (0.0, 0.6))); tl = rnd.uniform(*TU.get('len', (0.15, 0.35)))
            amp = rnd.uniform(*TU.get('amp', (0.004, 0.012))); dphi = rnd.uniform(-0.15, 0.15); pts, nrs = [], []
            for j in range(14):
                f = j / 13; d = flow.direction(phi + dphi * f, min(1.0, t0 + tl * f))
                if d is None: break
                p, nn = outer(d, 0.001 + amp * math.sin(math.pi * min(1.0, f * 1.2)) ** 1.2, 0.0015 + amp * 0.3 * (1 - f))
                if p is None: break
                if hl.hd(p) < -TU.get('over', 0.012): break
                if ear_kd is not None and ear_kd.find(p)[2] < 0.03: break   # 越过发际线最多搭下 1.2cm，不扫到脸上
                pts.append(p); nrs.append(nn)
            if len(pts) >= 7: _ribbon(bmc, uvc, pts, nrs, rnd.uniform(*TU.get('w', (0.008, 0.016))), rnd.random(), rnd.random() + 0.8); ntu += 1
    print('HAIR TUFTS', ntu, flush=True)
    # 太阳穴碎发：从两侧发际线垂到脸颊（照片里右侧多、左侧少）
    for side, cnt in S.get('wisps', {}).items():
        sx = -1.0 if side == 'R' else 1.0
        for k in range(cnt):
            az = sx * rnd.uniform(54, 78); z0 = hl(az) + rnd.uniform(0.004, 0.02)   # 靠前：正面能看见（照片里太阳穴、眼尾外侧被碎发遮住一条）
            d0 = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0)); start = None
            for zz in (z0, z0 + 0.01):
                h_ = bb.ray_cast(Vector((H.x, H.y, zz)), d0, 0.3)[0]
                if h_ is not None: start = h_; break
            if start is None: continue
            L = rnd.uniform(0.08, 0.17); pts, nrs = [], []; ph = rnd.uniform(0, 6.28)
            for j in range(16):
                f = j / 15; q = start + Vector((sx * (0.004 + 0.007 * f), -0.004 * f, -L * f)) + Vector((sx * 0.004 * math.sin(f * 5 + ph), 0, 0))
                loc, nn, _, dd = bb.find_nearest(q)
                if loc is not None:
                    out = (q - loc); out = out.normalized() if out.length > 1e-6 else Vector((sx, 0, 0))
                    if dd < 0.004 or out.dot(nn if nn.dot(out) > 0 else -nn) < 0: q = loc + (nn if nn.dot(Vector((sx, -0.3, 0))) > 0 else -nn) * 0.004
                pts.append(q); nrs.append((q - Vector((H.x, H.y, q.z))).normalized())
            _ribbon(bmc, uvc, pts, nrs, rnd.uniform(0.005, 0.010), rnd.random(), rnd.random() + 0.6)
    if S.get('style') == 'short':   # 男生短发：没有马尾、发圈、发箍
        # 头发下面的头皮隐藏（耳后、后颈头发很薄，身体细分后皮肤会从头发里透出来，一块块肉色）
        mods_ = [m for m in body.modifiers if m.type == 'MASK' and m.show_viewport]
        for m in mods_: m.show_viewport = False
        bpy.context.view_layer.update(); evb = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); mb_ = evb.to_mesh()
        Pb = [body.matrix_world @ v.co for v in mb_.vertices]; evb.to_mesh_clear()
        for m in mods_: m.show_viewport = True
        hid_ = [i for i, p_ in enumerate(Pb) if (p_ - H).length < 0.25 and hl.hd(p_) > 0.05 and (ear_kd is None or ear_kd.find(p_)[2] > 0.02)
                and (ear_lz is None or (p_.z > ear_lz + 0.02 and (p_.y > ear_cy + 0.01 or p_.z > eyes.z + 0.015)))   # 只藏头顶和后脑：原来下颌附近也被挖掉，皮肤破洞透出后面的头发，像几道黑线
                and mb.find_nearest(p_)[3] is not None and mb.find_nearest(p_)[3] < 0.012]
        vgh = body.vertex_groups.new(name='v11_hair_covered'); vgh.add(hid_, 1.0, 'REPLACE')
        mkh = body.modifiers.new('v11_hair_covered', 'MASK'); mkh.vertex_group = vgh.name; mkh.invert_vertex_group = True
        ia_ = next((k for k, m in enumerate(body.modifiers) if m.type == 'ARMATURE'), -1); body.modifiers.move(len(body.modifiers) - 1, ia_ + 1)
        print('SCALP HIDE', len(hid_), flush=True)
        # 一缕缕的起伏：沿发流（UV 的 y）拉长、横向（x）密集的随机条纹，做成置换贴图——短发表面不再是光滑头盔
        import numpy as _np
        R_ = 1024; rng = _np.random.default_rng(seed)
        xs_ = _np.linspace(0, 1, R_, endpoint=False); ys_ = _np.linspace(0, 1, R_, endpoint=False)
        tex = _np.zeros((R_, R_), _np.float32)
        for freq, amp in ((45, 1.0), (22, 0.9), (90, 0.35)):   # 网格密度有限：频率太高会出摩尔纹
            ph = rng.uniform(0, 6.28, 7)
            X_, Y_ = _np.meshgrid(xs_, ys_)
            warp = S.get('curl', 0.3) * (0.012 * _np.sin(Y_ * 6.28 * 3 + ph[0]) + 0.006 * _np.sin(Y_ * 6.28 * 7 + X_ * 40 + ph[1]))   # curl：卷曲程度（1 = 很卷）
            tex += amp * (0.5 + 0.5 * _np.sin((X_ + warp) * 6.28 * freq + ph[2] + 2.0 * S.get('curl', 0.3) * _np.sin(Y_ * 6.28 * 2 + X_ * 13 + ph[3])))
        tex = (tex - tex.min()) / (tex.max() - tex.min())
        tex = tex ** 1.6                                                   # 缕与缕之间的缝窄而深
        img = bpy.data.images.new(cid + '_hairclump', R_, R_, alpha=False, float_buffer=True)
        px_ = _np.ones((R_ * R_, 4), _np.float32); px_[:, :3] = tex.ravel()[:, None]; img.pixels.foreach_set(px_.ravel()); img.pack()
        tx = bpy.data.textures.new(cid + '_hairclump', 'IMAGE'); tx.image = img; tx.extension = 'REPEAT'
        mass.modifiers['subdiv'].levels = 2
        dm = mass.modifiers.new('clumps', 'DISPLACE'); dm.texture = tx; dm.texture_coords = 'UV'; dm.uv_layer = 'UVMap'
        dm.strength = S.get('clump', 0.0035); dm.mid_level = 0.55
        # 发际线附近不置换（边缘会被顶成锯齿）：用顶点组限制，离边界 1.5cm 内渐弱
        bmq = bmesh.new(); bmq.from_mesh(mass.data); bnd = [v.co.copy() for v in bmq.verts if v.is_boundary]; bmq.free()
        from mathutils.kdtree import KDTree as _KD
        kd_ = _KD(len(bnd))
        for k_, p_ in enumerate(bnd): kd_.insert(p_, k_)
        kd_.balance(); vg_ = mass.vertex_groups.new(name='clump_w')
        for v in mass.data.vertices: vg_.add([v.index], min(1.0, kd_.find(v.co)[2] / 0.015), 'REPLACE')
        dm.vertex_group = 'clump_w'
        # 发型主体按身体皮肤的权重绑骨（原来整块挂在头骨上：后颈皮肤跟脖子骨走，摆姿势后沉在皮肤下的发尾又顶出来，后颈一圈黑色锯齿）
        from mathutils.kdtree import KDTree as _KDs
        BW = body.matrix_world; bvs = body.data.vertices; kdb = _KDs(len(bvs))
        for v in bvs: kdb.insert(BW @ v.co, v.index)
        kdb.balance()
        bones = {b.name for b in rig.data.bones if b.use_deform}; bgn = {g.index: g.name for g in body.vertex_groups if g.name in bones}
        MWm = mass.matrix_world.copy(); mass.parent = None; mass.matrix_world = Matrix.Identity(4)
        vgs = {}
        for v in mass.data.vertices:
            v.co = MWm @ v.co
            ws = [(bgn[g.group], g.weight) for g in bvs[kdb.find(v.co)[1]].groups if g.group in bgn and g.weight > 1e-4]
            tot = sum(w for _, w in ws) or 1.0
            for n_, w in (ws or [('head', 1.0)]):
                if n_ not in vgs: vgs[n_] = mass.vertex_groups.new(name=n_)
                vgs[n_].add([v.index], w / tot, 'REPLACE')
        am = mass.modifiers.new('rig', 'ARMATURE'); am.object = rig; mass.modifiers.move(len(mass.modifiers) - 1, 0)
        mass.parent = rig; mass.matrix_parent_inverse = rig.matrix_world.inverted()
        cm = bpy.data.meshes.new(cid + '_haircards'); bmc.to_mesh(cm); bmc.free()
        for poly in cm.polygons: poly.use_smooth = True
        cm.materials.append(_hair_mat(cid + '_haircards', S['rgb'], 'card', freq=9.0, seed=seed + 2))
        cards = _link(cid + '_haircards', cm); _parent(cards, rig, pinv)
        cap_in = [fi for fi in cap_faces if hl.hd(sum((bv[i] for i in bp[fi]), Vector()) / len(bp[fi])) > 0.02 and (ear_kd is None or ear_kd.find(sum((bv[i] for i in bp[fi]), Vector()) / len(bp[fi]))[2] > 0.025)]   # 男生短发边缘薄；耳朵附近不铺（深色衬底贴在耳廓上）：衬底离发际线 2cm 以上才铺
        HL._scalp_cap(cid, bv, bp, cap_in, H, rig, pinv)
        if shell is not None: shell.hide_render = True; shell.hide_viewport = True
        print('HAIR CARDS OK', cid, 'short', 'mass faces', len(mm.polygons), flush=True)
        return mass
    # ---- 3) 马尾：渐细发束 + 外层发片 ----
    axis0 = Vector((0, 0.3, -1)).normalized(); ux = Vector((1, 0, 0)); vy = axis0.cross(ux).normalized()
    Lt = S['tail']; nseg, nring = 30, 16
    def back_y(z):   # 这个高度上后背（含毛衣约 1.4cm 厚）的最靠后位置
        h_ = bb.ray_cast(Vector((H.x, H.y + 0.4, z)), Vector((0, -1, 0)), 0.6)[0]
        return None if h_ is None else h_.y + 0.014
    def tail_c(t):   # 出了发圈稍往后，随即顺着后颈、后背垂下，贴着后背（原来是直的锥体，侧面看像一根往后翘的棍子）
        c = T + Vector((0, 0.020 * HL._smooth(0, 0.06, t) + 0.010 * t, -0.97 * t))
        by = back_y(c.z)
        if by is not None and t > 0.04: c.y = max(c.y, by + tail_r(t) * 0.9) * HL._smooth(0.04, 0.12, t) + c.y * (1 - HL._smooth(0.04, 0.12, t))
        return c + Vector((0.006 * math.sin(t * 9.0) * HL._smooth(0.08, 0.3, t), 0, 0))   # 轻微 S 形
    def tail_r(t): return max(0.0025, 0.007 + S['tail_r'] * HL._smooth(0.0, 0.06, t) - S['tail_r'] * 0.6 * HL._smooth(0.10, Lt, t) - 0.004 * HL._smooth(0.8 * Lt, Lt, t))
    def keep_off_back(q):
        loc, _, _, _ = bb.find_nearest(q)
        if loc is not None and q.y < loc.y + 0.008 and abs(q.z - loc.z) < 0.04: q.y = loc.y + 0.008
        return q
    bmt = bmesh.new(); uvt = bmt.loops.layers.uv.new('UVMap'); rings = []
    for j in range(nseg + 1):
        t = Lt * j / nseg; c = tail_c(t); r = tail_r(t); row = []
        for i in range(nring):
            a = 2 * math.pi * i / nring
            row.append(bmt.verts.new(keep_off_back(c + (ux * math.cos(a) + vy * math.sin(a)) * r)))
        rings.append(row)
    for j in range(nseg):
        for i in range(nring):
            f = bmt.faces.new((rings[j][i], rings[j][(i + 1) % nring], rings[j + 1][(i + 1) % nring], rings[j + 1][i]))
            for lp, (x, y) in zip(f.loops, ((i / nring, j / nseg), ((i + 1) / nring, j / nseg), ((i + 1) / nring, (j + 1) / nseg), (i / nring, (j + 1) / nseg))):
                lp[uvt].uv = (x * 4, y)
    tip = bmt.verts.new(tail_c(Lt + 0.012))
    for i in range(nring): bmt.faces.new((rings[-1][i], rings[-1][(i + 1) % nring], tip))
    tm = bpy.data.meshes.new(cid + '_ponytail'); bmt.to_mesh(tm); bmt.free()
    for poly in tm.polygons: poly.use_smooth = True
    tm.materials.append(_hair_mat(cid + '_ponytail', S['rgb'], 'mass', freq=60.0, seed=seed + 1))
    tail = _link(cid + '_ponytail', tm); ts = tail.modifiers.new('subdiv', 'SUBSURF'); ts.levels = 1; ts.render_levels = 2
    _parent(tail, rig, pinv)
    bmt2 = bmesh.new(); uvt2 = bmt2.loops.layers.uv.new('UVMap')
    for k in range(70):   # 马尾外层发片（单独一个物体，和马尾一起绑骨）
        a = rnd.uniform(0, 2 * math.pi); L = Lt * rnd.uniform(0.6, 1.02); pts, nrs = [], []; off = rnd.uniform(0.0, 0.004)
        for j in range(14):
            t = L * j / 13; c = tail_c(t); radial = ux * math.cos(a) + vy * math.sin(a)
            q = keep_off_back(c + radial * (tail_r(t) + 0.0015 + off) + Vector((0.003 * math.sin(t * 20 + a * 3), 0, 0)))
            pts.append(q); nrs.append(radial)
        _ribbon(bmt2, uvt2, pts, nrs, rnd.uniform(0.010, 0.018), rnd.random(), rnd.random() + 1.0)
    cm = bpy.data.meshes.new(cid + '_haircards'); bmc.to_mesh(cm); bmc.free()
    for poly in cm.polygons: poly.use_smooth = True
    cm.materials.append(_hair_mat(cid + '_haircards', S['rgb'], 'card', freq=9.0, seed=seed + 2))
    cards = _link(cid + '_haircards', cm); _parent(cards, rig, pinv)
    tcm = bpy.data.meshes.new(cid + '_tailcards'); bmt2.to_mesh(tcm); bmt2.free()
    for poly in tcm.polygons: poly.use_smooth = True
    tcm.materials.append(cm.materials[0]); tcards = _link(cid + '_tailcards', tcm)
    # 马尾绑骨：扎发处跟头走，往下逐渐改跟脊柱走——原来整根挂在头骨上，低头/抬头时马尾像棍子一样整体翘起来
    MW = rig.matrix_world; zN = (MW @ rig.data.bones['neck01'].head_local).z; zS = (MW @ rig.data.bones['spine01'].head_local).z
    for ob in (tail, tcards):
        ob.parent = None; ob.matrix_world = Matrix.Identity(4)
        g_h, g_n, g_s = (ob.vertex_groups.new(name=n) for n in ('head', 'neck01', 'spine01'))
        for v in ob.data.vertices:
            z = v.co.z; a = HL._smooth(T.z - 0.06, T.z - 0.01, z); b_ = HL._smooth(zS, zN, z) * (1 - a)
            g_h.add([v.index], a, 'REPLACE'); g_n.add([v.index], b_, 'REPLACE'); g_s.add([v.index], max(0.0, 1 - a - b_), 'REPLACE')
        am = ob.modifiers.new('rig', 'ARMATURE'); am.object = rig
        ob.modifiers.move(len(ob.modifiers) - 1, 0)
        ob.parent = rig
    # ---- 4) 深色头皮底 + 发圈 + 发箍 ----
    cap_in = [fi for fi in cap_faces if hl.hd(sum((bv[i] for i in bp[fi]), Vector()) / len(bp[fi])) > 0.006]   # 深色头皮衬底只铺在发际线以内（选面时放宽过）
    HL._scalp_cap(cid, bv, bp, cap_in, H, rig, pinv)
    HL._hair_tie(cid, rig, T, axis0)
    if S.get('headband'): HL._headband(cid, rig, mb, H, 0.0016, S['headband'], pinv, eyes.z, width=0.011)   # 压在发片外面
    if shell is not None: shell.hide_render = True; shell.hide_viewport = True
    print('HAIR CARDS OK', cid, 'mass faces', len(mm.polygons), 'cards', ncard, 'edge', nedge, 'tail', len(tm.polygons), flush=True)
    return mass
