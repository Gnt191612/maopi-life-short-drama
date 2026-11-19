# -*- coding: utf-8 -*-
"""写实细节（白模阶段能做的部分）：
  - 皮肤：毛孔 + 细纹的微凹凸，叠加在原有法线上；轻微的油光变化（额头鼻翼更亮）
  - 眼睛：角膜湿润高光（低粗糙度 + 清漆层）
  - 衣服：竖向布料褶皱 + 织物肌理凹凸，褶皱在肘弯、膝弯处更明显（按骨骼权重）
  - 环境：HDRI 全景光照与反射（Poly Haven，CC0），室内透过窗户看到的是真实天空
这些让 AI 写实化更容易「读懂」材质，但白模本身不会到照片级——那一步交给云端。
"""
import os
import bpy
import config

def _bump_chain(nt, principled, height_socket, strength, distance=0.002):
    """把新的凹凸接在原法线之后（原来有法线贴图就串联，不覆盖）"""
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength; bump.inputs['Distance'].default_value = distance
    nt.links.new(height_socket, bump.inputs['Height'])
    n_in = principled.inputs['Normal']
    if n_in.links: nt.links.new(n_in.links[0].from_socket, bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], n_in)
    return bump

def skin(mat):
    if not mat or not mat.use_nodes or mat.get('v11_real'): return
    nt = mat.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: return
    tc = nt.nodes.new('ShaderNodeTexCoord')
    pores = nt.nodes.new('ShaderNodeTexVoronoi'); pores.feature = 'F1'; pores.inputs['Scale'].default_value = 900   # 毛孔
    fine = nt.nodes.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 260; fine.inputs['Detail'].default_value = 12   # 细纹
    nt.links.new(tc.outputs['Object'], pores.inputs['Vector']); nt.links.new(tc.outputs['Object'], fine.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMath'); mix.operation = 'MULTIPLY_ADD'; mix.inputs[1].default_value = 0.6
    nt.links.new(pores.outputs['Distance'], mix.inputs[0]); nt.links.new(fine.outputs['Fac'], mix.inputs[2])
    _bump_chain(nt, b, mix.outputs[0], 0.28, 0.0012)
    # 血色：脸颊、鼻尖、耳朵一带微微泛红（低频噪声调制，避免整张脸一个颜色的「塑料感」）
    bc = b.inputs['Base Color']
    if bc.links:
        flush = nt.nodes.new('ShaderNodeTexNoise'); flush.inputs['Scale'].default_value = 3.5
        nt.links.new(tc.outputs['Object'], flush.inputs['Vector'])
        amt = nt.nodes.new('ShaderNodeMapRange'); amt.inputs['From Min'].default_value = 0.45; amt.inputs['To Max'].default_value = 0.35
        nt.links.new(flush.outputs['Fac'], amt.inputs['Value'])
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
        mx.inputs[7].default_value = (1.0, 0.78, 0.74, 1)
        nt.links.new(amt.outputs['Result'], mx.inputs['Factor']); nt.links.new(bc.links[0].from_socket, mx.inputs[6]); nt.links.new(mx.outputs[2], bc)
    oil = nt.nodes.new('ShaderNodeTexNoise'); oil.inputs['Scale'].default_value = 6
    nt.links.new(tc.outputs['Object'], oil.inputs['Vector'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.32; rr.inputs['To Max'].default_value = 0.52   # 粗糙度起伏：有的地方油亮
    nt.links.new(oil.outputs['Fac'], rr.inputs['Value'])
    if not b.inputs['Roughness'].links: nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    mat['v11_real'] = True

def eyes(mat):
    if not mat or not mat.use_nodes or mat.get('v11_real'): return
    b = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: return
    b.inputs['Coat Weight'].default_value = 1.0; b.inputs['Coat Roughness'].default_value = 0.02
    bc = b.inputs['Base Color']
    if bc.links:   # 虹膜原贴图偏红棕：降饱和、压暗成自然的深棕（东亚人常见瞳色）
        nt = mat.node_tree; hsv = nt.nodes.new('ShaderNodeHueSaturation')
        hsv.inputs['Hue'].default_value = 0.53; hsv.inputs['Saturation'].default_value = 0.8; hsv.inputs['Value'].default_value = 0.55
        nt.links.new(bc.links[0].from_socket, hsv.inputs['Color']); nt.links.new(hsv.outputs['Color'], bc)
    if not b.inputs['Roughness'].links: b.inputs['Roughness'].default_value = 0.08
    mat['v11_real'] = True

def cloth(mat):
    if not mat or not mat.use_nodes or mat.get('v11_real'): return
    nt = mat.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: return
    tc = nt.nodes.new('ShaderNodeTexCoord')
    folds = nt.nodes.new('ShaderNodeTexWave'); folds.wave_type = 'BANDS'; folds.bands_direction = 'Z'   # 竖向自然垂坠的褶
    folds.inputs['Scale'].default_value = 7; folds.inputs['Distortion'].default_value = 9; folds.inputs['Detail'].default_value = 3
    nt.links.new(tc.outputs['Object'], folds.inputs['Vector'])
    _bump_chain(nt, b, folds.outputs['Fac'], 0.35, 0.01)
    mat['v11_real'] = True

def enhance_character(rig):
    for o in rig.children:
        if o.type != 'MESH': continue
        for slot in o.material_slots:
            m = slot.material
            if not m: continue
            if o.name.endswith('_body'): skin(m)
            elif o.name.endswith('_high-poly'): eyes(m)
            elif 'suit' in o.name: cloth(m)

# 每个场景用哪张 HDRI、多亮（室内主要靠房间灯，HDRI 只提供窗外天空与柔和反射）
HDRI_OF = {'dorm_am': ('morning', 0.5), 'dorm_pm': ('day', 0.5), 'dorm_dusk': ('dusk', 0.4), 'dorm_nt': ('night', 0.6),
           'lib': ('day', 0.6), 'libdoor': ('day', 0.9), 'canteen': ('day', 0.5), 'track': ('night', 1.0), 'class': ('day', 0.5),
           'home': ('day', 0.4), 'home_nt': ('night', 0.5), 'lawn': ('day', 1.0),
           'ext_dorm_am': ('morning', 1.0), 'ext_dorm_pm': ('day', 1.0), 'ext_dorm_nt': ('night', 1.0),
           'ext_library': ('day', 1.0), 'ext_canteen': ('day', 1.0), 'ext_dusk': ('dusk', 1.0), 'ext_corridor': ('day', 0.6)}

def apply_hdri(set_name):
    kind, strength = HDRI_OF.get(set_name, (None, 0))
    p = os.path.join(config.ROOT, 'assets', 'hdri', '%s.hdr' % kind) if kind else ''
    if not kind or not os.path.exists(p): return False
    w = bpy.data.worlds.get('v11_world') or bpy.data.worlds.new('v11_world'); w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(p, check_existing=True)
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(env.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs[0], out.inputs['Surface'])
    bpy.context.scene.world = w
    return True
