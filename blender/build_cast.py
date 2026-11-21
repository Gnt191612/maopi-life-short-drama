# -*- coding: utf-8 -*-
"""v11 角色白模：MPFB2 按剧本体型生成 7 个绑骨人体 + 眼球/眉毛/牙齿/发型/服装/鞋（MakeHuman CC0 素材），
陈瑶的眼镜、林晓的卫衣帽子为程序建模并绑到对应骨骼。按目标身高的比例生成基础网格（配件同比例贴合），各存一个 .blend，并渲染并排对比图。
运行（仓库根目录）：BLENDER_USER_RESOURCES=.tools/blender_user .tools/blender/blender -b --factory-startup -P blender/build_cast.py [-- 角色id ...]   （不带参数 = 重建全部）
年龄映射（MakeHuman）：0.5=25 岁，0.4375≈20 岁，0.5625≈35 岁，0.6875≈50 岁
"""
import os, sys, math
import bpy, addon_utils
addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根目录
import config
import hair
import hair_cards
from mathutils import Vector
# 鞋子：保留原资产贴图（皮革、网面、磨旧感），按人物身份选鞋型
SHOES = {'lin': 'shoes02', 'chen': 'shoes05', 'zhou': 'shoes02', 'wang': 'shoes04', 'mom': 'shoes01', 'classA': 'shoes06', 'classB': 'shoes05',
         'extM1': 'shoes06', 'extM2': 'shoes05', 'extM3': 'shoes02', 'extF1': 'shoes05', 'extF2': 'shoes06', 'extF3': 'shoes05'}
# 五官立体度（所有人共用一层，不按 FACE_SCALE 缩小）：鼻梁更挺、眉弓、眼窝、人中与嘴唇的起伏——白模「像娃娃」主要因为脸太平
DEPTH_M = {'nose-scale-depth-incr': 0.35, 'nose-trans-forward': 0.15, 'eyebrows-trans-forward': 0.30, 'l-eye-push1-in': 0.30, 'r-eye-push1-in': 0.30,
           'mouth-philtrum-volume-incr': 0.25, 'mouth-upperlip-volume-incr': 0.15, 'mouth-lowerlip-volume-incr': 0.15, 'chin-prominent-incr': 0.12}
DEPTH_F = {'nose-scale-depth-incr': 0.25, 'nose-trans-forward': 0.10, 'eyebrows-trans-forward': 0.15, 'l-eye-push1-in': 0.20, 'r-eye-push1-in': 0.20,
           'mouth-philtrum-volume-incr': 0.20, 'mouth-upperlip-volume-incr': 0.20, 'mouth-lowerlip-volume-incr': 0.20}
WARM = (0.93, 0.86, 0.80)   # 肤色整体压暗、偏暖（原来偏白，像打了粉的蜡像）

OUT = config.CAST
ASSET = config.mpfb_data()   # MakeHuman 素材（安装脚本放在 .tools/blender_user 下）
os.makedirs(OUT, exist_ok=True)
ASIAN = {'asian': 1.0, 'caucasian': 0.0, 'african': 0.0}
HEIGHT = {'lin': 1.72, 'chen': 1.82, 'zhou': 1.76, 'wang': 1.74, 'mom': 1.60, 'classA': 1.75, 'classB': 1.63}   # 目标身高（米）
# id: (中文名, 性别 1男0女, 年龄, 体重, 肌肉, 身高滑块, 比例, 服装, 发型, 上衣颜色, 裤子颜色)
CAST = {
 'lin':    ('林晓',   1.0, 0.50, 1.00, 0.18, 0.50, 0.40, 'male_casualsuit02',   'short02',    (0.22, 0.22, 0.24), (0.15, 0.18, 0.28)),  # 深灰卫衣；肌肉减少显得更胖更软
 'chen':   ('陈瑶',   1.0, 0.44, 0.30, 0.45, 0.80, 0.60, 'male_casualsuit01',   'short04',    (0.90, 0.90, 0.88), (0.12, 0.12, 0.14)),  # 白衬衫
 'zhou':   ('周明远', 1.0, 0.47, 0.05, 0.36, 0.60, 0.55, 'male_casualsuit05',   'short01',    (0.25, 0.28, 0.18), (0.10, 0.10, 0.10)),  # 橄榄夹克；更瘦
 'wang':   ('王老师', 1.0, 0.64, 0.70, 0.40, 0.55, 0.50, 'male_casualsuit03',   'short04',    (0.62, 0.75, 0.90), (0.20, 0.20, 0.22)),  # 浅蓝衬衫
 'mom':    ('林母',   0.0, 0.59, 0.50, 0.40, 0.40, 0.45, 'female_elegantsuit01', 'bob01',     (0.82, 0.75, 0.62), (0.35, 0.30, 0.28)),  # 米色毛衣；有妈妈气质但不显老（约四十出头）
 'classA': ('同学甲', 1.0, 0.43, 0.66, 0.95, 0.55, 0.50, 'male_casualsuit04',   'short01',    (0.08, 0.12, 0.35), (0.10, 0.10, 0.12)),  # 深蓝运动外套；更壮
 'classB': ('同学乙', 0.0, 0.43, 0.42, 0.45, 0.48, 0.55, 'female_casualsuit01', 'ponytail01', (0.85, 0.80, 0.70), (0.20, 0.22, 0.30)),  # 米色高领
}
# 路人学生（外景里走动、骑车的背景人物）：普通脸、不同体型/发型/穿搭；为了轻量，不长发丝，直接用发片
EXTRAS = {
 'extM1': ('路人男1', 1.0, 0.42, 0.45, 0.50, 0.55, 0.50, 'male_casualsuit06', 'short03', (0.55, 0.16, 0.14), (0.18, 0.24, 0.40)),  # 红外套牛仔裤
 'extM2': ('路人男2', 1.0, 0.44, 0.60, 0.40, 0.45, 0.50, 'male_casualsuit03', 'short01', (0.86, 0.86, 0.82), (0.55, 0.48, 0.36)),  # 白T卡其裤
 'extM3': ('路人男3', 1.0, 0.43, 0.30, 0.60, 0.70, 0.55, 'male_casualsuit04', 'short04', (0.15, 0.32, 0.22), (0.10, 0.10, 0.11)),  # 墨绿卫衣
 'extF1': ('路人女1', 0.0, 0.42, 0.40, 0.40, 0.45, 0.55, 'female_casualsuit02', 'long01', (0.80, 0.58, 0.66), (0.45, 0.55, 0.70)),  # 粉上衣浅牛仔
 'extF2': ('路人女2', 0.0, 0.43, 0.50, 0.45, 0.40, 0.50, 'female_sportsuit01', 'bob02', (0.22, 0.28, 0.45), (0.14, 0.14, 0.16)),   # 运动装
 'extF3': ('路人女3', 0.0, 0.42, 0.35, 0.40, 0.55, 0.55, 'female_casualsuit01', 'braid01', (0.92, 0.88, 0.70), (0.30, 0.22, 0.20)),  # 奶黄上衣
}
CAST.update(EXTRAS)
HEIGHT.update({'extM1': 1.76, 'extM2': 1.71, 'extM3': 1.80, 'extF1': 1.62, 'extF2': 1.58, 'extF3': 1.65})
from bl_ext.user_default.mpfb.services.targetservice import TargetService
LR = lambda name, v: {'l-' + name: v, 'r-' + name: v}
FACE = {   # 五官个性化（MakeHuman 形态目标，0~1）：每人不同的基础头型 + 大幅度的局部特征，避免「大众脸」
 'lin':    {'head-round': 1.0, 'head-fat-incr': 1.0, 'head-scale-horiz-incr': 0.4, **LR('cheek-volume-incr', 1.0), 'neck-double-incr': 1.0, 'chin-height-decr': 0.5,
            **LR('eye-scale-decr', 0.4), **LR('eye-height2-decr', 0.4), 'nose-scale-horiz-incr': 0.5, 'nose-point-width-incr': 0.5,
            'mouth-scale-horiz-decr': 0.2, 'mouth-lowerlip-volume-incr': 0.6, **LR('ear-flap-incr', 0.3)},
 'chen':   {'head-oval': 0.9, 'head-scale-vert-incr': 0.5, 'head-scale-horiz-decr': 0.6, **LR('cheek-volume-decr', 0.4), **LR('cheek-bones-incr', 0.4),
            'chin-prominent-incr': 0.5, 'chin-width-decr': 0.5, 'chin-height-incr': 0.4, 'nose-scale-vert-incr': 0.5, 'nose-trans-forward': 0.4,
            'nose-point-width-decr': 0.4, **LR('eye-height2-decr', 0.3), 'mouth-scale-horiz-decr': 0.3, 'mouth-lowerlip-volume-decr': 0.4},
 'zhou':   {'mouth-scale-horiz-decr': 0.35, **LR('eye-scale-decr', 0.35), 'nose-scale-horiz-decr': 0.4, 'head-rectangular': 0.9, 'head-fat-decr': 0.9, **LR('cheek-volume-decr', 1.0), **LR('cheek-bones-incr', 0.8), 'chin-bones-incr': 0.7,
            'chin-prominent-incr': 0.3, 'forehead-scale-vert-incr': 0.4, 'nose-hump-incr': 0.5, 'nose-scale-vert-incr': 0.3,
            **LR('eye-bag-incr', 0.8), **LR('eye-push2-in', 0.5), 'eyebrows-angle-down': 0.4, 'mouth-scale-horiz-incr': 0.2},   # 眼袋更重：熬夜复习的倦态
 'wang':   {'head-fat-incr': 0.7, 'head-scale-horiz-incr': 0.5, **LR('cheek-volume-incr', 0.6), 'head-square': 0.9, 'head-age-incr': 0.9, 'chin-width-incr': 0.7, 'head-scale-horiz-incr': 0.3, 'nose-scale-horiz-incr': 0.5,
            'nose-flaring-incr': 0.5, 'mouth-laugh-lines-out': 0.9, 'mouth-scale-horiz-incr': 0.3, **LR('eye-bag-incr', 0.5),
            'forehead-scale-vert-incr': 0.5, 'eyebrows-angle-up': 0.3, 'neck-double-incr': 0.7},
 # 林母：用户要「有妈感但不显老」——年龄感、眼袋、法令纹都减轻，五官更精致（2026-11-20）
 'mom':    {'head-oval': 0.5, 'head-round': 0.3, 'head-age-incr': 0.25, **LR('cheek-volume-incr', 0.3), **LR('cheek-trans-down', 0.2), 'mouth-laugh-lines-out': 0.4,
            **LR('eye-bag-incr', 0.25), **LR('eye-eyefold-up', 0.4), 'mouth-angles-up': 0.4, 'mouth-upperlip-volume-incr': 0.25, 'nose-scale-horiz-incr': 0.1,
            'eyebrows-angle-up': 0.3, 'chin-prominent-incr': 0.2, 'neck-double-incr': 0.1},
 'classA': {'head-scale-horiz-incr': 0.6, **LR('ear-flap-incr', 0.8), 'eyebrows-trans-down': 0.35, 'mouth-scale-horiz-incr': 0.5, 'head-diamond': 0.9, 'chin-prominent-incr': 0.7, 'mouth-angles-up': 0.6, 'mouth-scale-horiz-incr': 0.4, 'nose-point-up': 0.5,
            **LR('eye-scale-decr', 0.3), **LR('eye-corner1-up', 0.5), 'eyebrows-angle-up': 0.6, **LR('ear-wing-incr', 0.7), **LR('cheek-bones-incr', 0.4)},
 # 同学乙向用户选定的标准长相（写实化第四张）靠拢：正常大小的杏眼 + 双眼皮、平直眉、窄长脸、柔和下颌（2026-11-19）
 # 第二轮（对照标准照逐项调）：杏眼再小一点、眉毛下移贴近眼睛、脸和下巴收窄、两颊收、嘴唇饱满偏小
 'classB': {'head-oval': 0.8, 'head-scale-horiz-decr': 0.55, 'head-scale-vert-incr': 0.15, **LR('eye-scale-incr', 0.2), **LR('eye-height2-incr', 0.2), **LR('eye-eyefold-up', 0.6),
            'eyebrows-trans-down': 0.15, 'eyebrows-angle-down': 0.25, 'eyebrows-trans-backward': 0.3,   # 平直眉、贴近眼睛
            'nose-greek-incr': 0.7, 'nose-width1-decr': 0.35, 'nose-hump-decr': 0.2,          # 鼻梁挺直、山根立起来
            'nose-scale-horiz-decr': 0.5, 'nose-point-width-decr': 0.3,                       # 鼻头小巧
            'nose-point-up': 0.3, 'mouth-cupidsbow-incr': 0.6, 'mouth-lowerlip-volume-incr': 0.5, 'mouth-upperlip-volume-incr': 0.35,
            'mouth-scale-horiz-decr': 0.25, 'chin-triangle': 0.35, 'chin-width-decr': 0.35, **LR('cheek-volume-decr', 0.3), **LR('cheek-bones-incr', 0.25)},
}
EYEBROW = {'lin': 'eyebrow005', 'chen': 'eyebrow012', 'zhou': 'eyebrow007', 'wang': 'eyebrow001', 'mom': 'eyebrow011',
           'classA': 'eyebrow009', 'classB': 'eyebrow012',                                                    # 每人不同眉形（同学乙：平直偏浓，照标准照）
           'extM1': 'eyebrow001', 'extM2': 'eyebrow003', 'extM3': 'eyebrow006', 'extF1': 'eyebrow011', 'extF2': 'eyebrow010', 'extF3': 'eyebrow012'}
SKIN_TINT = {'lin': (1.03, 1.0, 0.98), 'chen': (1.04, 1.01, 1.0), 'zhou': (0.94, 0.92, 0.92), 'wang': (0.93, 0.88, 0.84),
             'mom': (1.0, 0.97, 0.95), 'classA': (0.88, 0.80, 0.72), 'classB': (1.03, 0.97, 0.91),          # 肤色差异（乘在皮肤贴图上）；同学乙偏暖的浅米色
             'extM1': (0.95, 0.92, 0.9), 'extM2': (1.0, 0.97, 0.95), 'extM3': (0.9, 0.85, 0.8), 'extF1': (1.04, 1.0, 0.98),
             'extF2': (0.98, 0.95, 0.92), 'extF3': (1.05, 1.02, 1.0)}

STOCKINGS = {'classB': (0.012, 0.011, 0.013)}   # 黑丝（同学乙）
IRIS = {'classB': dict(scale=0.9, rgb=(0.20, 0.075, 0.030))}   # 2026-11-21 调成照片里的中深棕（原来太暗，渲染出来发灰）   # 深棕眼仁（同学乙，照标准照；纯黑像瞪眼）；原放大 22% 像娃娃，写实化时每次被「纠正」得不一样
LIP_TINT = {'mom': (1.10, 0.76, 0.76)}   # 唇色：红润（乘在唇部材质上）；已投影标准照的角色（同学乙）唇色来自照片，不再单染

def iris_edit(eye_obj, scale, rgb):
    """改眼球贴图：虹膜按比例放大（以各自圆心做径向重映射，外圈眼白平滑过渡、不变形），颜色换成近黑的深褐（保留虹膜纹理明暗）。
    贴图里两只眼球各一个虹膜；新贴图打包进 .blend"""
    import numpy as np
    m = eye_obj.material_slots[0].material if eye_obj.material_slots else None
    node = next((n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None) if m and m.use_nodes else None
    if node is None: print('IRIS SKIP', eye_obj.name, flush=True); return
    img = node.image; w, h = img.size
    src = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(src); src = src.reshape(h, w, 4)
    out = src.copy(); rgb0 = src[..., :3]; mx_, mn_ = rgb0.max(2), rgb0.min(2)
    iris = ((mx_ - mn_) / np.maximum(mx_, 1e-4) > 0.35) & (rgb0[..., 0] > rgb0[..., 1] * 1.2)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for half in (xx < w / 2, xx >= w / 2):
        sel = iris & half
        if sel.sum() < 100: continue
        cy, cx = yy[sel].mean(), xx[sel].mean(); r = math.sqrt(sel.sum() / math.pi); r_out = r * 2.0
        d = np.hypot(xx - cx, yy - cy); zone = d < r_out
        rk = r * scale                                                  # 放大后的虹膜半径：里面按 1/scale 取样，外圈线性过渡回原样
        sd = np.where(d < rk, d / scale, r + (d - rk) * (r_out - r) / (r_out - rk))
        f = np.where(d > 1e-3, sd / np.maximum(d, 1e-3), 0)
        sx = np.clip(cx + (xx - cx) * f, 0, w - 1).astype(np.int32); sy = np.clip(cy + (yy - cy) * f, 0, h - 1).astype(np.int32)
        out[zone] = src[sy[zone], sx[zone]]
    rgb1 = out[..., :3]; mx_, mn_ = rgb1.max(2), rgb1.min(2)
    iris = ((mx_ - mn_) / np.maximum(mx_, 1e-4) > 0.35) & (rgb1[..., 0] > rgb1[..., 1] * 1.2)
    lum = rgb1.mean(2); ref = float(lum[iris].mean())
    k = np.clip(lum / max(ref, 1e-3), 0.35, 1.8)[..., None]
    rgb1[iris] = (np.array(rgb, np.float32) * k)[iris]
    white = ~iris & (rgb1.mean(2) > 0.55)                               # 眼白压暗、略偏暖：纯白眼白像洋娃娃
    rgb1[white] = rgb1[white] * np.array([0.84, 0.80, 0.76], np.float32)
    new = bpy.data.images.new(eye_obj.name + '_iris', w, h, alpha=True); new.pixels.foreach_set(out.ravel()); new.pack()
    node.image = new
    print('IRIS', eye_obj.name, 'scale', scale, flush=True)

# 主要角色的分件穿搭（MakeHuman 社区服装包，宽松款；替换原来连体紧身的系统套装）。
# 每件：(包内路径, 颜色)，第一件是外层（其余被它盖住的部分往里收）；颜色 None = 保留原贴图配色（牛仔布、格纹、毛衣花纹）。鞋写包内路径，或系统鞋名
C = lambda pack, name: '%s/clothes/%s/%s.mhclo' % (pack, name, name)
OUTFIT = {
 'lin':    [(C('shirts02', 'elvs_hooded_sweat_jacket1'), (0.22, 0.22, 0.24)),       # 深灰连帽卫衣
            (C('pants02', 'elvs_jeans_straight_leg'), None)],                        # 直筒牛仔裤
 'chen':   [(C('shirts02', 'elvs_male_shirt_untucked_bd1'), (0.90, 0.90, 0.88)),    # 白衬衫（不扎进裤子）
            (C('pants02', 'mindfront_male_trousers_1'), (0.12, 0.12, 0.14))],        # 黑色长裤
 'zhou':   [(C('shirts02', 'mindfront_knitted_sweater_01'), (0.30, 0.33, 0.22)),    # 橄榄绿针织毛衣
            (C('pants01', 'cortu_cargo_pants'), (0.20, 0.19, 0.16))],                # 工装裤
 'wang':   [(C('pants02', 'elvs_male_trouser'), (0.22, 0.22, 0.24)),                # 灰色西裤（衬衫扎在裤子里，裤子是外层）
            (C('shirts02', 'elvs_male_shirt_tie_tucked1'), (0.62, 0.75, 0.90))],     # 浅蓝衬衫
 'mom':    [(C('shirts02', 'janexx_old_female_sweater'), (0.78, 0.70, 0.58)),       # 米色毛衣
            (C('pants01', 'toigo_wool_pants'), (0.30, 0.27, 0.25))],                 # 深褐宽松羊毛长裤（原来那条像紧身打底裤）
 'classA': [(C('shirts01', 'elvs_crude_t-shirt_male'), (0.10, 0.14, 0.36)),         # 宽松深蓝 T 恤
            (C('pants02', 'punkduck_male_classic_jeans'), None)],                    # 牛仔裤
 'classB': [(C('shirts02', 'mindfront_knitted_sweater_02'), (0.85, 0.80, 0.70)),    # 米色针织毛衣
            (C('skirts02', 'elvs_pleated_plaid_mini_skirt'), None)],                 # 百褶格纹短裙
}
SHOES.update({'classB': C('shoes01', 'toigo_ballet_flats')})                         # 配黑丝的平底鞋

def stockings(body, rgb):
    """丝袜：按腿部骨骼权重算出「丝袜区域」（脚到大腿上部，大腿根渐变），在皮肤材质上叠一层半透明黑色——
    正对镜头处透肤、侧面边缘更黑（真实丝袜的光学特征），表面带一点织物光泽"""
    me = body.data
    att = me.attributes.get('v11_stocking') or me.attributes.new('v11_stocking', 'FLOAT', 'POINT')
    w = {'lowerleg01': 1.0, 'lowerleg02': 1.0, 'foot': 1.0, 'toe1-1': 1.0, 'upperleg02': 1.0, 'upperleg01': 0.55}
    gid = {}
    for vg in body.vertex_groups:
        base = vg.name.rsplit('.', 1)[0]
        for k, s in w.items():
            if base.startswith(k): gid[vg.index] = s
    vals = [0.0] * len(me.vertices)
    for v in me.vertices:
        vals[v.index] = min(1.0, sum(g.weight * gid[g.group] for g in v.groups if g.group in gid))
    att.data.foreach_set('value', vals)
    done = set()
    for slot in body.material_slots:   # MPFB 的写实皮肤把 Principled BSDF 包在节点组里：进组里改（在外面混合着色器，EEVEE 下带次表面散射的皮肤混不上）
        m = slot.material
        if not m or not m.use_nodes: continue
        nt, b = _principled_tree(m.node_tree)
        if b is None or nt in done: continue   # 各皮肤材质共用一个节点组：只加一次
        done.add(nt)
        bc = b.inputs['Base Color']; src = bc.links[0].from_socket if bc.links else None
        at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'v11_stocking'
        lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.45
        dens = nt.nodes.new('ShaderNodeMapRange'); dens.inputs['To Min'].default_value = 0.62; dens.inputs['To Max'].default_value = 0.97
        nt.links.new(lw.outputs['Facing'], dens.inputs['Value'])                 # 越侧着看越不透（丝线叠得越密），正对处微微透肤
        fac = nt.nodes.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'
        nt.links.new(at.outputs['Fac'], fac.inputs[0]); nt.links.new(dens.outputs['Result'], fac.inputs[1])
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[7].default_value = (*rgb, 1)
        if src: nt.links.new(src, mx.inputs[6])
        else: mx.inputs[6].default_value = bc.default_value
        nt.links.new(fac.outputs[0], mx.inputs['Factor']); nt.links.new(mx.outputs[2], bc)
        for name, to in (('Subsurface Weight', 0.0), ('Roughness', 0.38)):        # 丝袜处：不要皮肤的次表面透光；织物略带光泽
            s = b.inputs.get(name)
            if s is None: continue
            mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Max'].default_value = to
            if s.links: nt.links.new(s.links[0].from_socket, mr.inputs['To Min'])
            else: mr.inputs['To Min'].default_value = s.default_value
            nt.links.new(at.outputs['Fac'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], s)
        sh = b.inputs.get('Sheen Weight')
        if sh is not None and not sh.links: nt.links.new(at.outputs['Fac'], sh)   # 丝袜的柔光
    print('STOCKINGS', body.name, flush=True)

def _principled_tree(nt):
    """找 Principled BSDF 所在的节点树（MPFB 写实皮肤把它包在节点组里）"""
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b: return nt, b
    for g in (n for n in nt.nodes if n.type == 'GROUP' and n.node_tree):
        r = _principled_tree(g.node_tree)
        if r[1]: return r
    return nt, None

def tint_skin(body, rgb, only=None, warm=True):
    """皮肤调色：乘在皮肤贴图上。only = 只处理名字含该词的材质（如 'lips' 唇色）。
    原先只在材质最外层找着色器，而写实皮肤的着色器在节点组里——调色从来没生效过（2026-11-20 修）"""
    done = set()   # 7 个皮肤材质共用同一个节点组：每个节点组只调一次（否则叠乘 7 遍）
    for slot in body.material_slots:
        m = slot.material
        if not m or not m.use_nodes or (only and only not in m.name.lower()): continue
        if only:   # 只调某个部位（唇）：给它单独复制一份节点组，不影响全身
            for g in (n for n in m.node_tree.nodes if n.type == 'GROUP' and n.node_tree): g.node_tree = g.node_tree.copy()
        nt, b = _principled_tree(m.node_tree)
        if not b or not b.inputs['Base Color'].links or nt in done: continue
        done.add(nt)
        src = b.inputs['Base Color'].links[0].from_socket
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
        mix.inputs[7].default_value = (*(c * (w if warm else 1) for c, w in zip(rgb, WARM)), 1); nt.links.new(src, mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])

FACE_SCALE_OF = {'zhou': 0.85, 'wang': 0.85, 'classA': 0.85, 'classB': 0.8, 'lin': 0.8}   # 长得太像的几个人加重各自特征；林晓加重胖脸
FACE_SCALE = 0.5   # 统一按 50% 生效：保留各人头型与特征组合，但回到现实中普通人的自然比例（满强度会像漫画）

# 照片拟合之后的人工微调（叠加在拟合权重上，不缩放）：拟合只看正面关键点，有些地方要按对比图再修
FIT_ADJUST = {
 'classB': {**LR('eye-height2-decr', 0.35), **LR('eye-height1-decr', 0.15),   # 眼睛睁得比照片大（照片里上眼睑压着瞳孔上缘，杏眼）
            **LR('cheek-volume-incr', 0.2), **LR('cheek-inner-incr', 0.15),     # 两颊、嘴两侧略饱满（加到 0.5 用户嫌脸胖，回调）
            'forehead-temple-decr': 0.9, **LR('cheek-bones-decr', 0.6), 'head-scale-horiz-decr': 0.15,         # 太阳穴、颧骨收窄（用户：眼边的脸型显胖，轮廓要修）
            'mouth-upperlip-middle-down': 0.25, 'mouth-lowerlip-middle-up': 0.2,   # 闭嘴（牙齿已往后收，不用再把唇往中间挤——挤多了嘴唇往前鼓）
            # 嘴部不前凸（用户：正脸看嘴部突出）：嘴整体往后收、唇的前后厚度减薄、抵掉共用立体度层加的唇厚，嘴角回平
            'mouth-trans-backward': 0.45, 'mouth-scale-depth-decr': 0.35, 'mouth-lowerlip-volume-decr': 0.35,
            'mouth-upperlip-volume-decr': 0.2, 'mouth-angles-down': 0.25, 'chin-prognathism-decr': 0.2,
            # 山根（用户：照片里鼻梁先往上延伸一段直线、过了内眼角才以弧线连到眉骨；白模在内眼角就弯进眉骨）：
            # 鼻根收窄、垫高（希腊鼻：鼻梁一直通到眉间），内眼角旁往里凹，鼻梁两侧的直线才立得起来
            # 内眼角旁不再往里压（压凹和共用立体度层叠加，上眼皮到鼻侧挤出一道深褶，用户嫌丑）——反而往外抵掉一半立体度层的压凹；
            # 鼻根收窄回调一点，鼻梁中线不起尖棱
            'nose-width1-decr': 0.45, 'nose-greek-incr': 0.4, **LR('eye-push1-out', 0.12), 'eyebrows-trans-forward': 0.10,
            'nose-width2-decr': 1.0, 'nose-width3-decr': 0.35},   # 鼻梁中段收窄（用户：鼻头还原，但鼻子中间略粗）
}
# 局部磨平（照片拟合角色）：以某关键点连线中点为中心、半径内的皮肤做拉普拉斯平滑，越靠中心越强。
# classB：内眼角与鼻根之间的那道弧形深沟（MakeHuman 头模本身的眶缘形状，形态参数去不掉）
FIT_SMOOTH = {
 # 第二、三处（用户：眼睛与鼻子之间褶皱还在）：双眼皮褶线没在内眼角收住、绕过内眼角顺着鼻侧往下——在两个内眼角的内上方各磨一处；
 # 保护只留紧贴睑缘（睫毛根）的一圈，原来按眼角点 13mm 的保护圈正好把这段褶线护住了
 'classB': [dict(keys=('eye_R_in', 'eye_L_in'), up=0.008, radius=0.026, strength=0.85, iters=25),
            dict(keys=('eye_R_in',), side=-1, inward=0.005, up=0.004, radius=0.016, strength=1.0, iters=40),
            dict(keys=('eye_L_in',), side=1, inward=0.005, up=0.004, radius=0.016, strength=1.0, iters=40)],
}

# 头顶压低（用户：头顶到眉毛的比例不对）：眉毛以上（眼睛中点上方 z0·眼距）的头骨按 k 往下压，过渡平滑，脸不动
FIT_CROWN = {'classB': dict(z0=1.0, k=0.72)}

def fit_crown(body, cid):
    S = FIT_CROWN.get(cid)
    if not S: return
    import json, numpy as np
    lv = json.load(open(os.path.join(config.ROOT, 'assets', 'identity', cid + '_face_fit.json'), encoding='utf-8'))['landmark_verts']
    me = body.data; n = len(me.vertices)
    tmp = body.shape_key_add(name='tmp_mix', from_mix=True)
    X = np.empty(n * 3, np.float32); tmp.data.foreach_get('co', X); X = X.reshape(-1, 3).astype(np.float64)
    body.shape_key_remove(tmp)
    eR = (X[lv['eye_R_in']] + X[lv['eye_R_out']]) / 2; eL = (X[lv['eye_L_in']] + X[lv['eye_L_out']]) / 2
    iod = np.linalg.norm(eL - eR); z0 = (eR[2] + eL[2]) / 2 + S['z0'] * iod
    d = X[:, 2] - z0; Y = X.copy()
    up = d > 0; dd = d[up]; Y[up, 2] = z0 + dd - (1 - S['k']) * dd * dd / (dd + 0.02)   # 斜率从 1 平滑过渡到 k
    basis = np.empty(n * 3, np.float32); me.shape_keys.key_blocks['Basis'].data.foreach_get('co', basis)
    kb = body.shape_key_add(name='adj_crown', from_mix=False)
    kb.data.foreach_set('co', (basis.reshape(-1, 3) + (Y - X)).astype(np.float32).ravel()); kb.value = 1.0
    print('FIT CROWN', cid, 'top lowered %.4f m' % float((X[:, 2] - Y[:, 2]).max()), flush=True)

LIP_SEAL = {'classB'}   # 唇缝封口（MakeHuman 默认嘴唇微张，唇缝露出口腔暗色；形态参数合拢会把唇形扯方）

def fit_lipseal(body, cid):
    """找出上下唇贴合处（唇部顶点里法线朝上/朝下的内侧面），按左右位置求缝的中线高度，把缝两侧 6mm 内的唇部顶点往中线收拢"""
    if cid not in LIP_SEAL: return
    import numpy as np
    me = body.data; n = len(me.vertices)
    tmp = body.shape_key_add(name='tmp_mix', from_mix=True)
    X = np.empty(n * 3, np.float32); tmp.data.foreach_get('co', X); X = X.reshape(-1, 3).astype(np.float64)
    body.shape_key_remove(tmp)
    me2 = bpy.data.meshes.new('tmp_lipseal'); me2.from_pydata(X.tolist(), [], [list(p.vertices) for p in me.polygons]); me2.update()
    Nn = np.array([v.normal[:] for v in me2.vertices]); bpy.data.meshes.remove(me2)
    gi = body.vertex_groups['lips'].index
    lips = np.array([any(g.group == gi and g.weight > 0.5 for g in v.groups) for v in me.vertices])
    L = np.nonzero(lips)[0]; xs = X[L, 0]; cx = (xs.min() + xs.max()) / 2; hw = (xs.max() - xs.min()) / 2
    inner = L[np.abs(Nn[L, 2]) > 0.55]                                   # 上下唇贴合处的内侧面
    bins = np.linspace(cx - hw, cx + hw, 13); zc_x, zc_z = [], []
    for a, b in zip(bins, bins[1:]):
        sel = inner[(X[inner, 0] >= a) & (X[inner, 0] < b)]
        if len(sel) >= 2: zc_x.append((a + b) / 2); zc_z.append(float(np.median(X[sel, 2])))
    if len(zc_x) < 3: print('LIP SEAL skip', flush=True); return
    zc = np.interp(X[L, 0], zc_x, zc_z)
    d = X[L, 2] - zc; Y = X.copy()
    w = np.clip(1 - np.abs(d) / 0.006, 0, 1); w = w * w * (3 - 2 * w)
    Y[L, 2] = zc + d * (1 - 0.85 * w)                                   # 缝两侧往中线收（离缝越近收得越多）
    basis = np.empty(n * 3, np.float32); me.shape_keys.key_blocks['Basis'].data.foreach_get('co', basis)
    kb = body.shape_key_add(name='adj_lipseal', from_mix=False)
    kb.data.foreach_set('co', (basis.reshape(-1, 3) + (Y - X)).astype(np.float32).ravel()); kb.value = 1.0
    print('LIP SEAL', cid, 'bins', len(zc_x), 'moved max %.4f' % float(np.abs(Y - X).max()), flush=True)

def fit_smooth(body, cid):
    """FIT_SMOOTH 的局部磨平，结果存成一个形态键（叠加在当前所有形态键的混合结果上；后面加的立体度层影响很小）"""
    jobs = FIT_SMOOTH.get(cid)
    if not jobs: return
    import json, numpy as np
    lv = json.load(open(os.path.join(config.ROOT, 'assets', 'identity', cid + '_face_fit.json'), encoding='utf-8'))['landmark_verts']
    me = body.data; n = len(me.vertices)
    tmp = body.shape_key_add(name='tmp_mix', from_mix=True)
    X = np.empty(n * 3, np.float32); tmp.data.foreach_get('co', X); X = X.reshape(-1, 3).astype(np.float64)
    body.shape_key_remove(tmp)
    E = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', E); E = E.reshape(-1, 2)
    deg = np.bincount(E.ravel(), minlength=n).astype(np.float64)
    Y = X.copy()
    gi = {g.name: g.index for g in body.vertex_groups}
    def members(*names):
        ids = {gi[nm] for nm in names if nm in gi}
        return np.array([any(g.group in ids and g.weight > 0.5 for g in v.groups) for v in me.vertices])
    helper = members('HelperGeometry', 'JointCubes')                 # 辅助几何（睫毛、眼球等配件按它贴合）一律不动
    lash = X[members('helper-l-eyelashes-1', 'helper-l-eyelashes-2', 'helper-r-eyelashes-1', 'helper-r-eyelashes-2')]
    from mathutils.kdtree import KDTree
    kd = KDTree(len(lash))
    for i, p in enumerate(lash): kd.insert(p, i)
    kd.balance()
    dl = np.array([kd.find(p)[2] for p in X])                         # 离睑缘（睫毛根）的距离
    t_ = np.clip((dl - 0.002) / 0.003, 0, 1); protect = t_ * t_ * (3 - 2 * t_) * (~helper)   # 睑缘 2~5mm 内渐变保护：眼皮不被拉开
    for j in jobs:
        c = sum(X[lv[k]] for k in j['keys']) / len(j['keys']); c[2] += j['up']
        if 'side' in j: c[0] -= j['side'] * j['inward']               # 往鼻子那侧挪（角色右 = −x）
        d = np.linalg.norm(X - c, axis=1); w = np.clip(1 - d / j['radius'], 0, 1); w = w * w * (3 - 2 * w) * j['strength'] * protect
        for _ in range(j['iters']):
            S = np.zeros_like(Y); np.add.at(S, E[:, 0], Y[E[:, 1]]); np.add.at(S, E[:, 1], Y[E[:, 0]])
            avg = S / np.maximum(deg, 1)[:, None]
            Y = Y + (avg - Y) * (w * 0.5)[:, None]
    basis = np.empty(n * 3, np.float32); me.shape_keys.key_blocks['Basis'].data.foreach_get('co', basis)
    kb = body.shape_key_add(name='adj_smooth', from_mix=False)
    kb.data.foreach_set('co', (basis.reshape(-1, 3) + (Y - X)).astype(np.float32).ravel()); kb.value = 1.0
    print('FIT SMOOTH', cid, 'moved max %.4f m' % float(np.abs(Y - X).max()), flush=True)

def face_fit(cid):
    """按标准长相照片拟合出的五官权重（blender/face_fit_*.py 生成，assets/identity/<cid>_face_fit.json），没有则返回 None"""
    p = os.path.join(config.ROOT, 'assets', 'identity', cid + '_face_fit.json')
    if not os.path.exists(p): return None
    import json
    return json.load(open(p, encoding='utf-8'))['weights']

def apply_face(body, cid):
    fit = face_fit(cid)
    if fit is not None:   # 照片拟合：正面能看出来的五官用拟合权重（已是最终值）；只影响侧面的个人特征保留手调设定
        from face_fit_export import PROFILE_KEEP
        for name, v in fit.items():
            TargetService.load_target(body, TargetService.target_full_path(name), weight=v, name=name)
        for name, v in FIT_ADJUST.get(cid, {}).items():
            TargetService.load_target(body, TargetService.target_full_path(name), weight=v, name='adj_' + name)
        fit_smooth(body, cid); fit_crown(body, cid); fit_lipseal(body, cid)
        keep = {n: v for n, v in FACE.get(cid, {}).items() if any((n[2:] if n[:2] in ('l-', 'r-') else n).startswith(k) for k in PROFILE_KEEP)}
    else: keep = FACE.get(cid, {})
    for name, v in keep.items():
        try: TargetService.load_target(body, TargetService.target_full_path(name), weight=v * FACE_SCALE_OF.get(cid, FACE_SCALE), name=name)
        except Exception as e: print('FACE WARN', cid, name, e, flush=True)
    depth = DEPTH_M if CAST[cid][1] > 0.5 else DEPTH_F
    for name, v in depth.items():
        if fit is None and name in FACE.get(cid, {}): continue            # 个人特征里已有的不重复叠加（照片拟合时立体度层照常叠加，与拟合时的基础人体一致）
        try: TargetService.load_target(body, TargetService.target_full_path(name), weight=v, name='depth_' + name)
        except Exception as e: print('DEPTH WARN', cid, name, e, flush=True)
SKINS = {'lin': 'young_asian_male', 'chen': 'young_asian_male', 'zhou': 'young_asian_male', 'classA': 'young_asian_male',
         'wang': 'middleage_asian_male', 'mom': 'middleage_asian_female', 'classB': 'young_asian_female',
         'extM1': 'young_asian_male', 'extM2': 'young_asian_male', 'extM3': 'young_asian_male',
         'extF1': 'young_asian_female', 'extF2': 'young_asian_female', 'extF3': 'young_asian_female'}

def mat(name, rgb, rough=0.8):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    return m

def fabric(name, rgb):
    """布料材质：角色配色 + 织物纹理凹凸 + 轻微色彩起伏（不再是平涂色）"""
    rgb = tuple(c ** 2.2 for c in rgb)   # 配色按屏幕色值写的，换算成线性光
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 0.88
    b.inputs['Sheen Weight'].default_value = 0.3
    tc = nt.nodes.new('ShaderNodeTexCoord'); noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 420
    weave = nt.nodes.new('ShaderNodeTexWave'); weave.inputs['Scale'].default_value = 900; weave.inputs['Distortion'].default_value = 2
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs['Factor'].default_value = 0.12
    mix.inputs[6].default_value = (*rgb, 1); mix.inputs[7].default_value = tuple(min(1, c * 1.25) for c in rgb) + (1,)
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector']); nt.links.new(tc.outputs['Object'], weave.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], mix.inputs['Factor']); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    nt.links.new(weave.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def tint(mat, rgb):
    """保留原资产贴图的细节（牛仔布纹、针织纹理、缝线、法线贴图），只把颜色换成角色配色：
    颜色 = 角色色 x 贴图亮度（按平均亮度归一）。原先整块换成平涂色，衣服看起来像紧身衣"""
    nt = mat.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: return False
    bc = b.inputs['Base Color']
    if not bc.links: bc.default_value = (*tuple(c ** 2.2 for c in rgb), 1); return True
    src = bc.links[0].from_socket
    bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(src, bw.inputs['Color'])
    k = 1.8                                                                   # 按贴图实际平均亮度归一（固定 1.8 倍时，偏暗的贴图染出来发灰：白衬衫成了灰衬衫）
    img = bc.links[0].from_node.image if bc.links[0].from_node.type == 'TEX_IMAGE' else None
    if img is not None and img.size[0] > 0:
        import numpy as np
        px = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(px)
        lum = float((px.reshape(-1, 4)[::97, :3] ** 2.2).mean())   # 贴图像素是 sRGB，着色器里是线性值
        if lum > 1e-3: k = max(1.0, min(4.0, 1.0 / lum))
    gain = nt.nodes.new('ShaderNodeMath'); gain.operation = 'MULTIPLY'; gain.inputs[1].default_value = k; gain.use_clamp = False
    nt.links.new(bw.outputs['Val'], gain.inputs[0])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs['Factor'].default_value = 1.0
    mx.inputs[6].default_value = (*tuple(c ** 2.2 for c in rgb), 1)
    cv = nt.nodes.new('ShaderNodeCombineColor'); nt.links.new(gain.outputs[0], cv.inputs['Red']); nt.links.new(gain.outputs[0], cv.inputs['Green']); nt.links.new(gain.outputs[0], cv.inputs['Blue'])
    nt.links.new(cv.outputs['Color'], mx.inputs[7]); nt.links.new(mx.outputs[2], bc)
    return True

LOGO_TOPS = ('male_casualsuit02', 'male_casualsuit04', 'male_casualsuit06', 'female_casualsuit01', 'female_casualsuit02', 'female_sportsuit01')   # 原贴图 T 恤上印着 MakeHuman 标志

def recolor(obj, rgb_top, rgb_bottom=None, asset=''):
    """服装：按部位染成角色配色（保留原资产的 UV/形状/布纹细节）；带标志的 T 恤上衣改用素色布料"""
    for i, slot in enumerate(obj.material_slots):
        n = (slot.material.name if slot.material else '').lower()
        bottom = bool(rgb_bottom and any(k in n for k in ('jean', 'pant', 'trouser', 'skirt')))
        rgb = rgb_bottom if bottom else rgb_top
        if asset in LOGO_TOPS and not bottom:
            slot.material = fabric('%s_%d' % (obj.name, i), rgb); continue
        if not (slot.material and slot.material.use_nodes and tint(slot.material, rgb)):
            slot.material = fabric('%s_%d' % (obj.name, i), rgb)
    if not obj.material_slots: obj.data.materials.append(fabric(obj.name + '_m', rgb_top))

def cloth_volume(obj, thick=0.004):
    """衣服的厚度和松量：布料向外长出 4mm 厚度（不再贴肉，领口、袖口、下摆能看出边）。
    不用「沿法线外扩」：素材里个别方向异常的点会被推出去几十厘米，变成尖刺/横穿画面的长线"""
    s = obj.modifiers.new('v11_thickness', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0; s.use_even_offset = False   # 不开均匀厚度：素材里压扁的小三角面会被放大几百倍，顶点飞出好几米

def shirt_details(cid, rig, shirt, pocket=True):
    """衬衫细节：门襟一排纽扣 + 左胸口袋（贴在衬衫表面，挂在胸椎骨骼上随身体动）"""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get(); ev = shirt.evaluated_get(dg); me = ev.to_mesh()
    tree = BVHTree.FromPolygons([shirt.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); ev.to_mesh_clear()
    pb = rig.pose.bones; M = rig.matrix_world
    top, low = (M @ pb['neck01'].head).z - 0.07, (M @ pb['root'].head).z + 0.03
    btn_mat = mat('btn_%s' % cid, (0.92, 0.91, 0.88), 0.3)
    z = top; k = 0
    while z > low:
        hit = tree.ray_cast(Vector((0, -1.0, z)), Vector((0, 1, 0)), 2.0)
        if hit[0] is not None:
            loc, nrm = hit[0], hit[1]
            bpy.ops.mesh.primitive_cylinder_add(radius=0.0055, depth=0.0025, vertices=12, location=loc + nrm * 0.0015)
            b = bpy.context.object; b.name = '%s_button%d' % (cid, k); b.rotation_euler = nrm.to_track_quat('Z', 'Y').to_euler()
            b.data.materials.append(btn_mat); bone_child(b, rig, 'spine01' if z > (M @ pb['spine03'].head).z else 'spine03'); k += 1
        z -= 0.085
    if pocket:   # 角色左胸（+X）
        zc = (M @ pb['spine01'].head).z + 0.02
        hit = tree.ray_cast(Vector((0.09, -1.0, zc)), Vector((0, 1, 0)), 2.0)
        if hit[0] is not None:
            loc, nrm = hit[0], hit[1]
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc + nrm * 0.0012)
            p = bpy.context.object; p.name = cid + '_pocket'; p.scale = (0.10, 0.11, 0.0015)
            p.rotation_euler = nrm.to_track_quat('Z', 'Y').to_euler()
            src = shirt.material_slots[0].material if shirt.material_slots else None
            p.data.materials.append(src); bone_child(p, rig, 'spine01')
    print('SHIRT DETAILS', cid, k, 'buttons', flush=True)

def darken_hair(obj, tint=(0.18, 0.15, 0.13)):
    """头发：保留资产的写实发丝纹理，乘上深色，接近东亚人的自然黑发"""
    for slot in obj.material_slots:
        m = slot.material
        if not m or not m.use_nodes: continue
        nt = m.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not b: continue
        src = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
        mix.inputs[7].default_value = (*tint, 1)
        if src: nt.links.new(src, mix.inputs[6])
        else: mix.inputs[6].default_value = b.inputs['Base Color'].default_value
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])

def add(body, rel, kind):
    path = os.path.join(config.MH_COMMUNITY, rel[len('community:'):]) if rel.startswith('community:') else os.path.join(ASSET, rel)
    return HumanService.add_mhclo_asset(path, body, asset_type=kind, subdiv_levels=1 if kind in ('Clothes', 'Hair') else 0)

def hide_under(under, over, margin=None):
    """内层衣服被外层盖住的那一截直接隐藏（遮罩修改器）：裙腰/裤腰藏在毛衣下摆里、衬衫下摆藏在裤腰里。
    按身体周围 36 个方位分别求外层的边缘高度（上衣取下摆最低点，扎进去的裤子取裤腰最高点），
    内层超过边缘 margin 的顶点隐藏。原先「往里收」的置换做法会把裙腰扯出一条条竖缝"""
    import math as _m
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = over.evaluated_get(dg); me = ev.to_mesh(); ov = [over.matrix_world @ v.co for v in me.vertices]; ev.to_mesh_clear()
    uv = [under.matrix_world @ v.co for v in under.data.vertices]
    cx = sum(v.x for v in uv) / len(uv); cy = sum(v.y for v in uv) / len(uv)
    over_is_lower = sum(v.z for v in ov) / len(ov) < sum(v.z for v in uv) / len(uv)   # 外层是下装（衬衫扎进裤子）
    if margin is None:   # 裙子的裙腰一直顶到下摆处（留 1.2cm）；裤子、衬衫多留一段——裆部、后腰那里身体没被遮住，藏多了会露肉
        margin = 0.012 if 'skirt' in under.name else 0.045
    sec = lambda v: int((_m.atan2(v.y - cy, v.x - cx) + _m.pi) / (2 * _m.pi) * 36) % 36
    zu0, zu1 = min(v.z for v in uv), max(v.z for v in uv)
    rad = {}                                                            # 内层每个方位的最大半径：外层只算贴着它的那一圈（排除垂在身侧的袖子）
    for v in uv:
        if (v.z < zu0 + 0.10) if over_is_lower else (v.z > zu1 - 0.10):   # 只量重叠的那一段（裙腰/衬衫下摆），不量张开的裙摆
            s = sec(v); rad[s] = max(rad.get(s, 0), _m.hypot(v.x - cx, v.y - cy))
    edge = {}
    for v in ov:
        s = sec(v)
        if not (zu0 - 0.05 < v.z < zu1 + 0.05) or _m.hypot(v.x - cx, v.y - cy) > rad.get(s, 0) + 0.06: continue
        edge[s] = max(edge.get(s, -9), v.z) if over_is_lower else min(edge.get(s, 9), v.z)
    hid = []
    for i, v in enumerate(uv):
        e = edge.get(sec(v))
        if e is None: continue
        if (v.z < e - margin) if over_is_lower else (v.z > e + margin): hid.append(i)
    vg = under.vertex_groups.new(name='v11_covered'); vg.add(hid, 1.0, 'REPLACE')
    m = under.modifiers.new('v11_covered', 'MASK'); m.vertex_group = vg.name; m.invert_vertex_group = True
    i = next((k for k, mm in enumerate(under.modifiers) if mm.type == 'ARMATURE'), -1)
    under.modifiers.move(len(under.modifiers) - 1, i + 1)
    print('HIDE', under.name, 'under', over.name, len(hid), 'verts', 'lower-outer' if over_is_lower else 'upper-outer', flush=True)

def hide_body_under(body, garment, reach=0.025):
    """裤子盖住的腿部皮肤隐藏：从皮肤顶点沿法线向外 2.5cm 内碰到裤子 = 被盖住。
    素材自带的删除区域常漏掉膝盖，坐下弯腿时膝盖会从裤子里顶出来。
    只用于下装、只处理胯部到脚踝之间：上衣会误伤下巴（领口）、袖口处会露出窟窿（实测）"""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = garment.evaluated_get(dg); me = ev.to_mesh()
    tree = BVHTree.FromPolygons([garment.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); ev.to_mesh_clear()
    M = body.matrix_world; N = M.to_3x3().inverted().transposed(); hid = []
    gz = [garment.matrix_world @ v.co for v in garment.data.vertices]
    z_lo, z_hi = min(v.z for v in gz) + 0.10, max(v.z for v in gz) - 0.06       # 离开裤脚、裤腰各一段：边口处藏了皮肤会透空
    for v in body.data.vertices:
        p = M @ v.co
        if not (z_lo < p.z < z_hi): continue
        if tree.ray_cast(p, (N @ v.normal).normalized(), reach)[0] is not None: hid.append(v.index)
    name = 'v11_under_' + garment.name[-20:]
    vg = body.vertex_groups.new(name=name); vg.add(hid, 1.0, 'REPLACE')
    m = body.modifiers.new(name, 'MASK'); m.vertex_group = name; m.invert_vertex_group = True
    i = next((k for k, mm in enumerate(body.modifiers) if mm.type == 'ARMATURE'), -1)
    body.modifiers.move(len(body.modifiers) - 1, i + 1)
    print('BODY HIDE', garment.name, len(hid), flush=True)

def tuck_under(under, over, depth=0.007):
    """内层衣服被外层盖住的部分往里收（裙腰、裤腰藏进毛衣/卫衣下摆里）：
    沿法线向外 6cm 内碰到外层 = 被盖住，往里缩 depth；沿法线向里 3cm 内碰到外层 = 跑到外层外面了（下摆漏出），
    按实际距离收到外层里面。用置换修改器（权重 = 各顶点需要收的距离）"""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = over.evaluated_get(dg); me = ev.to_mesh()
    tree = BVHTree.FromPolygons([over.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); ev.to_mesh_clear()
    vg = under.vertex_groups.new(name='v11_tucked'); M = under.matrix_world; N = M.to_3x3().inverted().transposed()
    need = {}
    for v in under.data.vertices:
        p = M @ v.co; n = (N @ v.normal).normalized()
        if tree.ray_cast(p, n, 0.06)[0] is not None: need[v.index] = depth          # 被外层盖住：往里收 depth
        else:
            h = tree.ray_cast(p, -n, 0.03)                                            # 跑到外层外面去了（下摆处漏出来）：收到外层里面再多 depth
            if h[0] is not None: need[v.index] = h[3] + depth
    top = max(need.values(), default=depth)
    for i, a in need.items(): vg.add([i], a / top, 'REPLACE')
    hits = list(need)
    d = under.modifiers.new('v11_tuck', 'DISPLACE'); d.direction = 'NORMAL'; d.strength = -top; d.mid_level = 0.0; d.vertex_group = vg.name
    i = next((k for k, m in enumerate(under.modifiers) if m.type == 'ARMATURE'), -1)
    under.modifiers.move(len(under.modifiers) - 1, i + 1)   # 紧跟在绑骨之前的形状上做（在细分、厚度之前）
    print('TUCK', under.name, 'under', over.name, len(hits), 'verts', flush=True)

def bone_child(obj, rig, bone):
    """把程序建模的配件挂到骨骼上（随头/脖子运动）"""
    bpy.context.view_layer.update()                    # 先刷新：刚设的缩放/旋转要先算进 matrix_world（否则口袋会变成 1 米大方块）
    mw = obj.matrix_world.copy()
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = bone
    obj.matrix_world = mw

def glasses(rig):
    """陈瑶的黑色细框眼镜：两个镜框环 + 鼻梁"""
    pb = rig.pose.bones; L = rig.matrix_world @ pb['eye.L'].head; R = rig.matrix_world @ pb['eye.R'].head
    c = (L + R) / 2; half = (L - R).length / 2; parts = []
    for p in (L, R):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.019, minor_radius=0.0018, location=(p.x, p.y - 0.022, p.z), rotation=(math.radians(90), 0, 0))
        parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0016, depth=half * 2 - 0.036, location=(c.x, c.y - 0.022, c.z + 0.004), rotation=(0, math.radians(90), 0))
    parts.append(bpy.context.object)
    for side, p in ((1, L), (-1, R)):   # 镜腿
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0014, depth=0.10, location=(p.x + side * 0.02, p.y + 0.028, p.z), rotation=(math.radians(90), 0, 0))
        parts.append(bpy.context.object)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts: o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]; bpy.ops.object.join()
    g = bpy.context.object; g.name = 'chen_glasses'; g.data.materials.append(mat('glasses_black', (0.02, 0.02, 0.02), 0.3))
    bone_child(g, rig, 'head'); return g

def hood(rig, rgb):
    """林晓的卫衣帽子：脖子后方的半环褶"""
    n = rig.matrix_world @ rig.pose.bones['neck01'].head
    bpy.ops.mesh.primitive_torus_add(major_radius=0.085, minor_radius=0.035, location=(n.x, n.y + 0.035, n.z + 0.01), rotation=(math.radians(75), 0, 0))
    h = bpy.context.object; h.name = 'lin_hood'; h.scale = (1.15, 1.0, 0.8)
    bpy.ops.object.transform_apply(scale=True)
    h.data.materials.append(fabric('lin_hood_m', rgb)); bone_child(h, rig, 'neck01'); return h

# 成品发型素材（MakeHuman 社区高精度发型，CC-BY，作者署名见 THIRD_PARTY_LICENSES.md）；其余角色用代码生成的发丝
HAIR_ASSET = {}   # 成品雕刻发型实测像塑料假发、款式复古，不直接使用（2026-11-14）
# 发型轮廓素材：只用来定义发型外形，真实发丝沿着它生成（林母的微卷短发）
HAIR_SHAPE = {'mom': 'mh_community/hair02/hair/elvs_wavy_bob/elvs_wavy_bob.mhclo'}   # 用正斜杠：Windows、Linux（云端）都认
HAIR_COLOR = {'mom': (0.030, 0.027, 0.026)}   # 林母：黑发里带一点灰；其余为自然黑发

def recolor_asset_hair(obj, rgb=(0.014, 0.011, 0.009)):
    """成品发型改成自然黑发：保留贴图的明暗与发丝细节（转灰度），只替换颜色"""
    for slot in obj.material_slots:
        m = slot.material
        if not m or not m.use_nodes: continue
        nt = m.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not b: continue
        src = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
        bw = nt.nodes.new('ShaderNodeRGBToBW'); mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 1.8
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs[6].default_value = (*rgb, 1); mix.inputs[7].default_value = (1, 1, 1, 1)
        if src: nt.links.new(src, bw.inputs['Color']); nt.links.new(bw.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], mix.inputs['Factor'])
        else: mix.inputs['Factor'].default_value = 0.6
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.42
        if 'Coat Weight' in b.inputs: b.inputs['Coat Weight'].default_value = 0.15

def build(cid):
    name, g, age, wt, mu, ht, pr, suit, hair_name, top, bottom = CAST[cid]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)
    macro = {'gender': g, 'age': age, 'muscle': mu, 'weight': wt, 'proportions': pr, 'height': ht, 'cupsize': 0.5, 'firmness': 0.5, 'race': ASIAN}
    probe = HumanService.create_human(macro_detail_dict=macro)          # 先量自然身高，再按比例重新生成（配件随基础网格同比例贴合）
    s = HEIGHT[cid] / probe.dimensions.z
    bpy.data.objects.remove(probe, do_unlink=True)
    body = HumanService.create_human(macro_detail_dict=macro)
    body.name = cid + '_body'
    apply_face(body, cid)   # 先定脸型，再绑骨、穿戴（配件按最终脸型贴合）
    rig = HumanService.add_builtin_rig(body, 'default'); rig.name = cid + '_rig'
    skin = SKINS[cid]   # MakeHuman 写实皮肤（含纹理、次表面散射）
    HumanService.set_character_skin(os.path.join(ASSET, 'skins', skin, skin + '.mhmat'), body, skin_type='ENHANCED_SSS')
    tint_skin(body, SKIN_TINT[cid])
    if cid in LIP_TINT: tint_skin(body, LIP_TINT[cid], only='lips', warm=False)
    if cid in STOCKINGS: stockings(body, STOCKINGS[cid])
    parts = {}
    shoe = SHOES.get(cid, 'shoes02')
    shoe_rel = ('community:' + shoe) if '/' in shoe else 'clothes/%s/%s.mhclo' % (shoe, shoe)
    wear = [('community:' + rel, 'Clothes') for rel, _ in OUTFIT[cid]] if cid in OUTFIT else [('clothes/%s/%s.mhclo' % (suit, suit), 'Clothes')]
    for rel, kind in [('eyes/high-poly/high-poly.mhclo', 'Eyes'), ('eyebrows/%s/%s.mhclo' % (EYEBROW[cid], EYEBROW[cid]), 'Eyebrows'),
                      ('eyelashes/eyelashes01/eyelashes01.mhclo', 'Eyelashes'), ('teeth/teeth_base/teeth_base.mhclo', 'Teeth'),
                      ('hair/%s/%s.mhclo' % (hair_name, hair_name), 'Hair')] + wear + [(shoe_rel, 'Clothes')]:
        try: parts[rel] = add(body, rel, kind)
        except Exception as e: print('ASSET FAIL', cid, rel, e, flush=True)
    color_of = {'community:' + rel: rgb for rel, rgb in OUTFIT.get(cid, [])}
    for rel, o in parts.items():
        if o is None: continue
        asset = os.path.basename(rel)[:-6]
        if 'eyebrow' in rel: darken_hair(o)
        elif rel.startswith('hair/'): pass   # 头发由 hair.build 处理（发帽 + 发丝）
        elif 'eyes' in rel and cid in IRIS: iris_edit(o, **IRIS[cid])
        elif 'teeth' in rel:   # 牙齿往后收 6 毫米：MakeHuman 默认嘴唇微张，闭嘴时唇缝里会露白牙尖（说话张嘴时照样看得见）
            for v in o.data.vertices: v.co.y += 0.006
        elif 'eyelash' in rel or 'eyes' in rel: pass   # 保留资产自带的写实材质
        elif rel == shoe_rel: pass   # 鞋子保留原贴图
        elif rel in color_of:        # 分件服装：按件染色（None = 保留原配色）
            if color_of[rel] is not None: recolor(o, color_of[rel], asset=asset)
            cloth_volume(o, 0.003); o['v11_cloth'] = True
        else: recolor(o, top, bottom, asset=asset); cloth_volume(o)
        o.name = '%s_%s' % (cid, asset)
    if cid in OUTFIT:   # 第一件是外层，其余收进去
        layers = [parts.get('community:' + rel) for rel, _ in OUTFIT[cid]]
        for under in layers[1:]:
            if layers[0] is not None and under is not None: hide_under(under, layers[0])
        for g_ in layers:   # 只处理长裤（裙子下面是黑丝腿，不藏）
            if g_ is not None and any(k in g_.name for k in ('pants', 'trouser', 'jeans')): hide_body_under(body, g_)
    shell = parts.get('hair/%s/%s.mhclo' % (hair_name, hair_name))   # 真实发丝：以发片为发型轮廓生长
    if cid in HAIR_ASSET:   # 成品发型：替换系统发片，不生成发丝
        if shell is not None: bpy.data.objects.remove(shell, do_unlink=True); shell = None
        ha = HumanService.add_mhclo_asset(os.path.join(config.TOOLS, HAIR_ASSET[cid]), body, asset_type='Hair', subdiv_levels=1)
        ha.name = cid + '_hair'; recolor_asset_hair(ha, HAIR_COLOR.get(cid, (0.014, 0.011, 0.009)))
    if cid in HAIR_SHAPE:   # 用社区发型做轮廓（替换系统发片），发丝沿着它生成
        if shell is not None: bpy.data.objects.remove(shell, do_unlink=True)
        shell = HumanService.add_mhclo_asset(os.path.join(config.TOOLS, HAIR_SHAPE[cid]), body, asset_type='Hair', subdiv_levels=1); shell.name = cid + '_hairshape'
        hair_name = 'wavybob'
    if cid in hair_cards.CARDS:   # 照定妆照建的发型（主体 + 发片），替换系统发片与程序发丝
        bpy.context.view_layer.update(); hair_cards.build(cid, rig, body, shell, seed=sum(map(ord, cid)))
        if shell is not None: bpy.data.objects.remove(shell, do_unlink=True)
    elif shell is not None and cid in EXTRAS:   # 路人：发片直接当头发（远景足够），染成深色
        recolor_asset_hair(shell)
    elif shell is not None and os.environ.get('V11_STRANDS', '1') == '1':
        bpy.context.view_layer.update(); hair.build(cid, rig, body, shell, hair_name, seed=sum(map(ord, cid)))
    sd = body.modifiers.new('subdiv', 'SUBSURF'); sd.levels = 0; sd.render_levels = 2   # 渲染时细分，去掉多边形棱角
    if cid == 'chen': glasses(rig)
    # 程序拼的帽子（圆环）看起来很假，已停用

    # 按实际头顶高度（含修改器后的网格）缩放整个骨架对象：子物体随父级同比例，动画只用旋转与对象位移，不受影响
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    top = max((ev.matrix_world @ v.co).z for v in ev.to_mesh().vertices); ev.to_mesh_clear()
    k = HEIGHT[cid] / top; rig.scale = (k, k, k)
    body['v11_char'] = name
    rig['v11_female'] = g < 0.5
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, cid + '.blend'))
    print('CAST OK', cid, name, 'height %.2fm (scale %.3f)' % (top * k, k), 'parts', len([p for p in parts.values() if p]), flush=True)

def lineup():
    """7 个角色并排，Eevee 渲染白模对比图（正面 + 侧面）"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for i, cid in enumerate(CAST):
        if not os.path.exists(os.path.join(OUT, cid + '.blend')): continue   # 暂存目录里只建了部分角色
        with bpy.data.libraries.load(os.path.join(OUT, cid + '.blend')) as (src, dst):
            dst.objects = [n for n in src.objects]
        for o in dst.objects:
            sc.collection.objects.link(o)
            if o.parent is None: o.location.x += (i - 3) * 0.8
    bpy.ops.mesh.primitive_plane_add(size=30)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
    cam.location = (0, -8.0, 1.05); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 42; sc.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30)); sc.collection.objects.link(sun)
    sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.3, 0.3, 0.32)
    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA')); key.data.energy = 700; key.data.size = 4
    key.location = (3, -6, 4); key.rotation_euler = (math.radians(55), 0, math.radians(25)); sc.collection.objects.link(key)
    sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = 1700, 720
    sc.eevee.use_raytracing = True; sc.eevee.taa_render_samples = 64; sc.view_settings.view_transform = 'AgX'
    sc.render.filepath = os.path.join(config.RENDERS, 'cast_lineup.png')
    bpy.ops.render.render(write_still=True)
    print('LINEUP OK', flush=True)

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for cid in (argv or list(CAST)):
        build(cid)
    if os.environ.get('V11_NO_LINEUP') != '1': lineup()   # 云端多进程并行建人时跳过合影图
