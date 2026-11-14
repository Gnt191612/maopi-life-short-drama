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

OUT = config.CAST
ASSET = config.mpfb_data()   # MakeHuman 素材（安装脚本放在 .tools/blender_user 下）
os.makedirs(OUT, exist_ok=True)
ASIAN = {'asian': 1.0, 'caucasian': 0.0, 'african': 0.0}
HEIGHT = {'lin': 1.72, 'chen': 1.82, 'zhou': 1.76, 'wang': 1.74, 'mom': 1.60, 'classA': 1.75, 'classB': 1.63}   # 目标身高（米）
# id: (中文名, 性别 1男0女, 年龄, 体重, 肌肉, 身高滑块, 比例, 服装, 发型, 上衣颜色, 裤子颜色)
CAST = {
 'lin':    ('林晓',   1.0, 0.50, 1.00, 0.30, 0.50, 0.40, 'male_casualsuit02',   'short02',    (0.22, 0.22, 0.24), (0.15, 0.18, 0.28)),  # 深灰卫衣
 'chen':   ('陈瑶',   1.0, 0.44, 0.30, 0.45, 0.80, 0.60, 'male_casualsuit01',   'short04',    (0.90, 0.90, 0.88), (0.12, 0.12, 0.14)),  # 白衬衫
 'zhou':   ('周明远', 1.0, 0.47, 0.25, 0.55, 0.60, 0.55, 'male_casualsuit05',   'short01',    (0.25, 0.28, 0.18), (0.10, 0.10, 0.10)),  # 橄榄夹克
 'wang':   ('王老师', 1.0, 0.56, 0.55, 0.45, 0.55, 0.50, 'male_casualsuit03',   'short04',    (0.62, 0.75, 0.90), (0.20, 0.20, 0.22)),  # 浅蓝衬衫
 'mom':    ('林母',   0.0, 0.69, 0.62, 0.40, 0.40, 0.45, 'female_elegantsuit01', 'bob01',     (0.82, 0.75, 0.62), (0.35, 0.30, 0.28)),  # 米色毛衣
 'classA': ('同学甲', 1.0, 0.44, 0.50, 0.62, 0.55, 0.50, 'male_casualsuit04',   'short01',    (0.08, 0.12, 0.35), (0.10, 0.10, 0.12)),  # 深蓝运动外套
 'classB': ('同学乙', 0.0, 0.43, 0.42, 0.45, 0.48, 0.55, 'female_casualsuit01', 'ponytail01', (0.85, 0.80, 0.70), (0.20, 0.22, 0.30)),  # 米色高领
}
from bl_ext.user_default.mpfb.services.targetservice import TargetService
LR = lambda name, v: {'l-' + name: v, 'r-' + name: v}
FACE = {   # 五官个性化（MakeHuman 形态目标，0~1）：每人不同的基础头型 + 大幅度的局部特征，避免「大众脸」
 'lin':    {'head-round': 1.0, 'head-fat-incr': 1.0, **LR('cheek-volume-incr', 1.0), 'neck-double-incr': 0.6, 'chin-height-decr': 0.5,
            **LR('eye-scale-decr', 0.4), **LR('eye-height2-decr', 0.4), 'nose-scale-horiz-incr': 0.5, 'nose-point-width-incr': 0.5,
            'mouth-scale-horiz-decr': 0.2, 'mouth-lowerlip-volume-incr': 0.6, **LR('ear-flap-incr', 0.3)},
 'chen':   {'head-oval': 0.9, 'head-scale-vert-incr': 0.5, 'head-scale-horiz-decr': 0.6, **LR('cheek-volume-decr', 0.4), **LR('cheek-bones-incr', 0.4),
            'chin-prominent-incr': 0.5, 'chin-width-decr': 0.5, 'chin-height-incr': 0.4, 'nose-scale-vert-incr': 0.5, 'nose-trans-forward': 0.4,
            'nose-point-width-decr': 0.4, **LR('eye-height2-decr', 0.3), 'mouth-scale-horiz-decr': 0.3, 'mouth-lowerlip-volume-decr': 0.4},
 'zhou':   {'head-rectangular': 0.9, 'head-fat-decr': 0.9, **LR('cheek-volume-decr', 1.0), **LR('cheek-bones-incr', 0.8), 'chin-bones-incr': 0.7,
            'chin-prominent-incr': 0.3, 'forehead-scale-vert-incr': 0.4, 'nose-hump-incr': 0.5, 'nose-scale-vert-incr': 0.3,
            **LR('eye-bag-incr', 0.4), **LR('eye-push2-in', 0.5), 'eyebrows-angle-down': 0.4, 'mouth-scale-horiz-incr': 0.2},
 'wang':   {'head-square': 0.9, 'head-age-incr': 0.6, 'chin-width-incr': 0.7, 'head-scale-horiz-incr': 0.3, 'nose-scale-horiz-incr': 0.5,
            'nose-flaring-incr': 0.5, 'mouth-laugh-lines-out': 0.9, 'mouth-scale-horiz-incr': 0.3, **LR('eye-bag-incr', 0.5),
            'forehead-scale-vert-incr': 0.5, 'eyebrows-angle-up': 0.3, 'neck-double-incr': 0.3},
 'mom':    {'head-round': 0.6, 'head-age-incr': 0.9, **LR('cheek-volume-incr', 0.5), **LR('cheek-trans-down', 0.5), 'mouth-laugh-lines-out': 1.0,
            **LR('eye-bag-incr', 0.8), 'mouth-angles-up': 0.4, 'nose-scale-horiz-incr': 0.3, 'eyebrows-angle-up': 0.3, 'neck-double-incr': 0.3},
 'classA': {'head-diamond': 0.9, 'chin-prominent-incr': 0.7, 'mouth-angles-up': 0.6, 'mouth-scale-horiz-incr': 0.4, 'nose-point-up': 0.5,
            **LR('eye-scale-decr', 0.3), **LR('eye-corner1-up', 0.5), 'eyebrows-angle-up': 0.6, **LR('ear-wing-incr', 0.7), **LR('cheek-bones-incr', 0.4)},
 'classB': {'head-oval': 0.8, 'head-scale-horiz-decr': 0.35, **LR('eye-scale-incr', 0.55), **LR('eye-height2-incr', 0.4), 'nose-scale-horiz-decr': 0.5,
            'nose-point-up': 0.3, 'mouth-cupidsbow-incr': 0.6, 'mouth-lowerlip-volume-incr': 0.4, 'chin-triangle': 0.7, **LR('cheek-bones-incr', 0.25)},
}
EYEBROW = {'lin': 'eyebrow005', 'chen': 'eyebrow009', 'zhou': 'eyebrow002', 'wang': 'eyebrow007', 'mom': 'eyebrow011',
           'classA': 'eyebrow004', 'classB': 'eyebrow010'}                                                    # 每人不同眉形
SKIN_TINT = {'lin': (1.03, 1.0, 0.98), 'chen': (1.04, 1.01, 1.0), 'zhou': (0.94, 0.92, 0.92), 'wang': (0.93, 0.88, 0.84),
             'mom': (1.0, 0.97, 0.95), 'classA': (0.88, 0.80, 0.72), 'classB': (1.06, 1.02, 1.0)}           # 肤色差异（乘在皮肤贴图上）

def tint_skin(body, rgb):
    for slot in body.material_slots:
        m = slot.material
        if not m or not m.use_nodes: continue
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not b or not b.inputs['Base Color'].links: continue
        src = b.inputs['Base Color'].links[0].from_socket; nt = m.node_tree
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
        mix.inputs[7].default_value = (*rgb, 1); nt.links.new(src, mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])

FACE_SCALE = 0.5   # 统一按 50% 生效：保留各人头型与特征组合，但回到现实中普通人的自然比例（满强度会像漫画）

def apply_face(body, cid):
    for name, v in FACE.get(cid, {}).items():
        try: TargetService.load_target(body, TargetService.target_full_path(name), weight=v * FACE_SCALE, name=name)
        except Exception as e: print('FACE WARN', cid, name, e, flush=True)
SKINS = {'lin': 'young_asian_male', 'chen': 'young_asian_male', 'zhou': 'young_asian_male', 'classA': 'young_asian_male',
         'wang': 'middleage_asian_male', 'mom': 'middleage_asian_female', 'classB': 'young_asian_female'}

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

def recolor(obj, rgb_top, rgb_bottom=None):
    """服装：按部位换成角色配色的布料材质（保留原资产的 UV/形状）"""
    for i, slot in enumerate(obj.material_slots):
        n = (slot.material.name if slot.material else '').lower()
        rgb = rgb_bottom if (rgb_bottom and any(k in n for k in ('jean', 'pant', 'trouser', 'skirt'))) else rgb_top
        slot.material = fabric('%s_%d' % (obj.name, i), rgb)
    if not obj.material_slots: obj.data.materials.append(fabric(obj.name + '_m', rgb_top))

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
    return HumanService.add_mhclo_asset(os.path.join(ASSET, rel), body, asset_type=kind, subdiv_levels=1 if kind in ('Clothes', 'Hair') else 0)

def bone_child(obj, rig, bone):
    """把程序建模的配件挂到骨骼上（随头/脖子运动）"""
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
    parts = {}
    for rel, kind in (('eyes/high-poly/high-poly.mhclo', 'Eyes'), ('eyebrows/%s/%s.mhclo' % (EYEBROW[cid], EYEBROW[cid]), 'Eyebrows'),
                      ('eyelashes/eyelashes01/eyelashes01.mhclo', 'Eyelashes'), ('teeth/teeth_base/teeth_base.mhclo', 'Teeth'),
                      ('hair/%s/%s.mhclo' % (hair_name, hair_name), 'Hair'), ('clothes/%s/%s.mhclo' % (suit, suit), 'Clothes'),
                      ('clothes/shoes02/shoes02.mhclo', 'Clothes')):
        try: parts[rel] = add(body, rel, kind)
        except Exception as e: print('ASSET FAIL', cid, rel, e, flush=True)
    for rel, o in parts.items():
        if o is None: continue
        if 'eyebrow' in rel: darken_hair(o)
        elif 'hair' in rel: pass   # 头发由 hair.build 处理（发帽 + 发丝）
        elif 'eyelash' in rel or 'eyes' in rel or 'teeth' in rel: pass   # 保留资产自带的写实材质
        elif 'clothes' in rel and 'shoes' not in rel: recolor(o, top, bottom)
        elif 'shoes' in rel: recolor(o, (0.9, 0.9, 0.9) if cid in ('chen', 'classB') else (0.08, 0.08, 0.08))
        o.name = '%s_%s' % (cid, rel.split('/')[1])
    shell = parts.get('hair/%s/%s.mhclo' % (hair_name, hair_name))   # 真实发丝：以发片为发型轮廓生长
    if shell is not None and os.environ.get('V11_STRANDS', '1') == '1':
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
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, cid + '.blend'))
    print('CAST OK', cid, name, 'height %.2fm (scale %.3f)' % (top * k, k), 'parts', len([p for p in parts.values() if p]), flush=True)

def lineup():
    """7 个角色并排，Eevee 渲染白模对比图（正面 + 侧面）"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for i, cid in enumerate(CAST):
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
    lineup()
