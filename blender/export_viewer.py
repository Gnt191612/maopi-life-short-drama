# -*- coding: utf-8 -*-
"""把人物导出给「人物审阅」小软件（viewer/）：每人一个 GLB（站姿、手指自然微屈、材质烘焙成贴图、发丝转成细管），
再包成 viewer/models/<id>.js（base64），双击 html 就能离线加载，不需要本地服务器。
blender -b --factory-startup -P blender/export_viewer.py -- [角色id ...]"""
import os, sys, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import bpy
import poses, realism, life

IDS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv and sys.argv[-1] != '--' else ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
OUT = os.path.join(config.ROOT, 'viewer', 'models'); os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(config.ROOT, 'build', 'viewer_tmp'); os.makedirs(TMP, exist_ok=True)

def principled(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None

def simple_texture(m):
    """底色直接来自一张贴图（眉毛、睫毛、鞋子原贴图）：网页可以原样读，不用烘焙"""
    b = principled(m)
    return b is not None and b.inputs['Base Color'].links and b.inputs['Base Color'].links[0].from_node.type == 'TEX_IMAGE'

def bake_object(o, size):
    """把这个物体所有材质的「漫反射颜色」烘焙进一张贴图，换成网页能读的简单材质"""
    img = bpy.data.images.new(o.name + '_col', size, size, alpha=False)
    olds = [s.material for s in o.material_slots]
    for m in olds:
        if not m or not m.use_nodes: continue
        n = m.node_tree.nodes.new('ShaderNodeTexImage'); n.image = img; m.node_tree.nodes.active = n
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=4, use_clear=True)
    p = os.path.join(TMP, o.name + '_col.jpg'); img.filepath_raw = p; img.file_format = 'JPEG'; img.save()
    for i, m in enumerate(olds):
        rough = principled(m).inputs['Roughness'].default_value if principled(m) else 0.6
        nm = bpy.data.materials.new(o.name + '_web%d' % i); nm.use_nodes = True
        b = nm.node_tree.nodes['Principled BSDF']; t = nm.node_tree.nodes.new('ShaderNodeTexImage'); t.image = img
        nm.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = rough
        o.material_slots[i].material = nm

def fix_eyes(o):
    """网页版眼睛：
    1) 删掉角膜外壳——它的 UV 落在贴图右下角那块蓝色圆里（Cycles 里是透明的，网页里不透明，会把黑眼珠整个盖住）
    2) 另存一张网页专用眼球贴图：原图虹膜是暗红色，改成自然的深棕（保留虹膜纹理明暗），眼白不动"""
    import bmesh, numpy as np
    bm = bmesh.new(); bm.from_mesh(o.data); uv = bm.loops.layers.uv.active
    dead = []
    for f in bm.faces:
        cu = sum(l[uv].uv.x for l in f.loops) / len(f.loops); cv = sum(l[uv].uv.y for l in f.loops) / len(f.loops)
        if cu > 0.82 and cv < 0.18: dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context='FACES'); bm.to_mesh(o.data); bm.free()
    img = next((n.image for s in o.material_slots if s.material and s.material.use_nodes for n in s.material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    nm = bpy.data.materials.new(o.name + '_web'); nm.use_nodes = True; b = nm.node_tree.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.12; b.inputs['Coat Weight'].default_value = 1.0
    if img:
        w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(h, w, 4)
        rgb = px[..., :3]; mx, mn = rgb.max(2), rgb.min(2); sat = (mx - mn) / np.maximum(mx, 1e-4)
        iris = (sat > 0.35) & (rgb[..., 0] > rgb[..., 1] * 1.2)                # 暗红的虹膜区域
        lum = rgb.mean(2, keepdims=True); ref = float(lum[iris].mean()) if iris.any() else 0.2
        brown = np.array([0.30, 0.19, 0.11], np.float32) * np.clip(lum / max(ref, 1e-3), 0.3, 1.8)
        rgb[iris] = brown[iris]
        out = bpy.data.images.new(o.name + '_eyeweb', w, h, alpha=True); out.pixels.foreach_set(px.ravel())
        p = os.path.join(TMP, o.name + '_eyeweb.png'); out.filepath_raw = p; out.file_format = 'PNG'; out.save()
        t = nm.node_tree.nodes.new('ShaderNodeTexImage'); t.image = out; nm.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
    o.data.materials.clear(); o.data.materials.append(nm)
    print('EYES', o.name, 'cornea faces removed', len(dead), flush=True)

def hair_to_tubes(o, keep=0.85, scale=1.8):
    """发丝曲线 -> 细管网格：保留大部分发丝、把管子做细，避免一根根等粗「塑料面条」感。
    发丝越细越密越接近真发，也能盖住发帽让发际线自然过渡。
    【稳定版】只用几何节点 + 纯色材质——实测顶点色/大 numpy 写入会在大网格上让 Blender 崩溃或导出漏掉发丝。"""
    ng = bpy.data.node_groups.new('hair_tubes', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    rnd = N.new('FunctionNodeRandomValue'); rnd.data_type = 'BOOLEAN'; rnd.inputs['Probability'].default_value = 1 - keep
    dl = N.new('GeometryNodeDeleteGeometry'); dl.domain = 'CURVE'
    circ = N.new('GeometryNodeCurvePrimitiveCircle'); circ.inputs['Resolution'].default_value = 3; circ.inputs['Radius'].default_value = 0.00016 * scale   # 截面半径 0.00029m ≈ 0.58mm 直径
    c2m = N.new('GeometryNodeCurveToMesh')
    rs = N.new('GeometryNodeResampleCurve'); rs.inputs['Count'].default_value = 8          # 每根发丝 8 个点
    sel = next(s for s in rnd.outputs if s.type == 'BOOLEAN' and s.enabled)                # 布尔输出（按类型找，不靠序号）
    L.new(gi.outputs[0], dl.inputs['Geometry']); L.new(sel, dl.inputs['Selection'])
    L.new(dl.outputs[0], rs.inputs['Curve'])
    L.new(rs.outputs[0], c2m.inputs['Curve']); L.new(circ.outputs[0], c2m.inputs['Profile Curve']); L.new(c2m.outputs[0], go.inputs[0])
    md = o.modifiers.new('tubes', 'NODES'); md.node_group = ng
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.convert(target='MESH')
    o = bpy.context.view_layer.objects.active
    m = bpy.data.materials.new(o.name + '_hairweb'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0.028, 0.021, 0.016, 1); b.inputs['Roughness'].default_value = 0.42
    o.data.materials.clear(); o.data.materials.append(m)
    return o

def export(cid):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    with bpy.data.libraries.load(os.path.join(config.CAST, cid + '.blend')) as (src, dst): dst.objects = list(src.objects)
    for o in dst.objects: sc.collection.objects.link(o)
    rig = bpy.data.objects[cid + '_rig']; realism.enhance_character(rig)
    poses.SUPPORT_ON = False
    poses.apply_state(rig, dict(pos=(0, 0, 0), yaw=0, base='stand', arms='down')); life.hands(rig, None); bpy.context.view_layer.update()
    keep = []
    for o in list(rig.children_recursive):   # 挂在骨骼上的部件（头发、发帽、眼镜、纽扣、口袋）：按当前姿势定住世界位置再脱离骨骼，
        if o.parent_type == 'BONE':            # 否则导出时它们回到骨骼静止位置，比摆好姿势的身体低几厘米（头发陷进头里）
            mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    bpy.context.view_layer.update()
    for o in [o for o in bpy.data.objects if o.name.startswith(cid + '_') and o.type in ('MESH', 'CURVES')]:
        if o.hide_render: continue
        if o.type == 'CURVES': keep.append(hair_to_tubes(o)); continue
        if o.type != 'MESH': continue
        if o.name.endswith('_teeth_base'): continue
        for md in o.modifiers:
            if md.type == 'SUBSURF': md.levels = 1                          # 网页里一级细分，曲面圆润又不太重
        if 'eyebrow' in o.name or 'eyelash' in o.name:   # 眉毛/睫毛：贴图里毛发之间是透明的，要接上透明通道（按透明度镂空），否则是一条实心黑块
            img = next((n.image for s in o.material_slots if s.material and s.material.use_nodes for n in s.material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
            nm = bpy.data.materials.new(o.name + '_web'); nm.use_nodes = True; b = nm.node_tree.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 0.6
            if img:
                t = nm.node_tree.nodes.new('ShaderNodeTexImage'); t.image = img
                b.inputs['Base Color'].default_value = (0.035, 0.028, 0.022, 1)   # 深黑褐色，只用贴图的透明度来决定毛发形状
                nm.node_tree.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
                nm.blend_method = 'CLIP'; nm.alpha_threshold = 0.06
            o.data.materials.clear(); o.data.materials.append(nm); keep.append(o); continue
        if all(simple_texture(s.material) for s in o.material_slots if s.material) and o.material_slots: keep.append(o); continue
        if o.name.endswith('_high-poly'):   # 眼睛：去掉透明角膜层（网页里会变成不透明的灰白壳，盖住黑眼珠），虹膜改成深棕
            fix_eyes(o); keep.append(o); continue
        if not o.data.uv_layers:   # 没有 UV（发帽、纽扣、口袋等程序建模的小件）：直接用纯色材质
            col = (0.030, 0.023, 0.018, 1) if 'scalpcap' in o.name else (principled(o.material_slots[0].material).inputs['Base Color'].default_value[:]
                                                                         if o.material_slots and principled(o.material_slots[0].material) else (0.8, 0.8, 0.8, 1))
            nm = bpy.data.materials.new(o.name + '_web'); nm.use_nodes = True; nm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = col
            o.data.materials.clear(); o.data.materials.append(nm); keep.append(o); continue
        bake_object(o, 2048 if o.name.endswith('_body') or 'suit' in o.name else 1024)
        keep.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in keep: o.select_set(True)
    glb = os.path.join(TMP, cid + '.glb')
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_image_format='AUTO', export_jpeg_quality=88, export_animations=False, export_skins=False)
    data = base64.b64encode(open(glb, 'rb').read()).decode('ascii')
    open(os.path.join(OUT, cid + '.js'), 'w', encoding='ascii').write("window.V11_MODELS=window.V11_MODELS||{};V11_MODELS['%s']='%s';\n" % (cid, data))
    print('VIEWER OK', cid, '%.1f MB' % (os.path.getsize(glb) / 1e6), flush=True)

for cid in IDS: export(cid)
