# -*- coding: utf-8 -*-
"""场景白模：所有地点按真实尺寸用代码搭建（米，Z 向上）。同一地点在所有镜头里完全一致。
约定：房间原点在地面中心，+Y 指向房间深处（后墙/窗），-Y 是门一侧。
物体命名前缀用于后期生成遮罩：wall_/floor_/furn_/prop_/light_/ext_ 。
build(name) 返回 dict：marks（角色站位/座位等关键点）、cams（建议机位）。
"""
import math, random
import bpy

# ---------------- 基础工具 ----------------
_MATS = {}
def mat(name, rgb, emit=0.0, rough=0.85, alpha=1.0):
    key = (name, rgb, emit, alpha)
    if key in _MATS: return _MATS[key]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    lin = tuple(c ** 2.2 for c in rgb)   # 色值按屏幕色写的，换算成线性光
    b.inputs['Base Color'].default_value = (*lin, 1); b.inputs['Roughness'].default_value = rough
    if not emit: _surface(m, b, name.rsplit('_', 1)[-1], lin)
    if emit:
        b.inputs['Emission Color'].default_value = (*rgb, 1); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha; m.surface_render_method = 'BLENDED'
    _MATS[key] = m; return m

def _surface(m, b, key, lin):
    """按材质类别加程序纹理：木纹、地砖缝、墙面肌理、织物、金属、玻璃、石材、草木——让白模接近真实质感"""
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    tc = N('ShaderNodeTexCoord')
    def tone(fac, k1=0.8, k2=1.15):
        mix = N('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs[6].default_value = tuple(c * k1 for c in lin) + (1,); mix.inputs[7].default_value = tuple(min(1, c * k2) for c in lin) + (1,)
        L(fac, mix.inputs['Factor']); L(mix.outputs[2], b.inputs['Base Color'])
    def bump(h, s):
        bp = N('ShaderNodeBump'); bp.inputs['Strength'].default_value = s; L(h, bp.inputs['Height']); L(bp.outputs['Normal'], b.inputs['Normal'])
    k = key.lower()
    if 'wood' in k:
        w = N('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = 'X'; w.inputs['Scale'].default_value = 18; w.inputs['Distortion'].default_value = 5
        w.inputs['Detail'].default_value = 4; L(tc.outputs['Object'], w.inputs['Vector']); tone(w.outputs['Fac'], 0.82, 1.1); bump(w.outputs['Fac'], 0.03)
        b.inputs['Roughness'].default_value = 0.5
    elif 'floor' in k:
        br = N('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 1.6; br.inputs['Mortar Size'].default_value = 0.008
        br.offset = 0.0; br.inputs['Color1'].default_value = (*lin, 1); br.inputs['Color2'].default_value = tuple(c * 0.92 for c in lin) + (1,)
        br.inputs['Mortar'].default_value = tuple(c * 0.6 for c in lin) + (1,)
        L(tc.outputs['Object'], br.inputs['Vector']); L(br.outputs['Color'], b.inputs['Base Color']); bump(br.outputs['Fac'], 0.15)
        b.inputs['Roughness'].default_value = 0.35
    elif k in ('wall', 'white', 'stone'):
        n = N('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 60 if k != 'stone' else 8; n.inputs['Detail'].default_value = 8
        L(tc.outputs['Object'], n.inputs['Vector']); tone(n.outputs['Fac'], 0.92, 1.05); bump(n.outputs['Fac'], 0.08 if k != 'stone' else 0.3)
    elif k in ('fabric', 'sofa'):
        w = N('ShaderNodeTexWave'); w.inputs['Scale'].default_value = 300; L(tc.outputs['Object'], w.inputs['Vector']); bump(w.outputs['Fac'], 0.2)
        b.inputs['Sheen Weight'].default_value = 0.4; b.inputs['Roughness'].default_value = 0.9
    elif k == 'metal':
        b.inputs['Metallic'].default_value = 0.85; b.inputs['Roughness'].default_value = 0.35
    elif k == 'glass':
        b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['Roughness'].default_value = 0.03
    elif k in ('leaf', 'green') or (lin[1] > lin[0] * 1.3 and lin[1] > lin[2] * 1.3):
        n = N('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 25; n.inputs['Detail'].default_value = 10
        L(tc.outputs['Object'], n.inputs['Vector']); tone(n.outputs['Fac'], 0.6, 1.3); bump(n.outputs['Fac'], 0.5)

C = dict(wall=(0.80, 0.76, 0.68), floor=(0.55, 0.50, 0.44), wood=(0.52, 0.36, 0.22), white=(0.85, 0.85, 0.83),
         metal=(0.45, 0.46, 0.48), fabric=(0.70, 0.66, 0.58), dark=(0.08, 0.08, 0.09), glass=(0.6, 0.75, 0.85),
         green=(0.20, 0.36, 0.15), red=(0.62, 0.22, 0.16), stone=(0.62, 0.60, 0.56), black=(0.02, 0.02, 0.02),
         paper=(0.95, 0.95, 0.93), board=(0.10, 0.20, 0.15), sofa=(0.78, 0.70, 0.58), leaf=(0.18, 0.32, 0.12))

_cube = None
def _unit_cube():
    global _cube
    if _cube is None or _cube.name not in bpy.data.meshes:
        bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.object; _cube = o.data; _cube.name = 'unit_cube'
        bpy.data.objects.remove(o, do_unlink=True)
        _cube.materials.append(None)   # 预留一个材质槽
    return _cube

def coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(c)
    return c

def box(name, size, loc, color, col=None, rot_z=0.0, emit=0.0, alpha=1.0):
    """size=(x,y,z)；loc=(中心x, 中心y, 底面z)"""
    o = bpy.data.objects.new(name, _unit_cube())           # 所有方块共享一个网格，材质挂在物体上
    o.scale = size; o.location = (loc[0], loc[1], loc[2] + size[2] / 2); o.rotation_euler.z = rot_z
    (col or bpy.context.scene.collection).objects.link(o)
    rgb = color if isinstance(color, tuple) else C[color]
    o.material_slots[0].link = 'OBJECT'
    o.material_slots[0].material = mat(name.split('_')[0] + '_' + str(color), rgb, emit, alpha=alpha)
    return o

_PROTO = {}
def proto(key, build):
    """共享网格：同一种几何只建一次，之后每个物体都引用它（不再每次调用 bpy.ops——大场景里 ops 会逐个刷新整个场景，越建越慢）"""
    m = _PROTO.get(key)
    try: alive = m is not None and m.name in bpy.data.meshes
    except ReferenceError: alive = False               # 重置场景后旧网格已被删除
    if not alive:
        import bmesh
        bm = bmesh.new(); build(bm); m = bpy.data.meshes.new('proto_' + key); bm.to_mesh(m); bm.free()
        for p in m.polygons: p.use_smooth = True
        m.materials.append(None); _PROTO[key] = m
    return m

def _place(name, mesh, loc, scale, rot, color, col):
    o = bpy.data.objects.new(name, mesh); o.location = loc; o.scale = scale; o.rotation_euler = rot
    (col or bpy.context.scene.collection).objects.link(o)
    o.material_slots[0].link = 'OBJECT'
    o.material_slots[0].material = mat(name.split('_')[0] + '_' + str(color), color if isinstance(color, tuple) else C[color])
    return o

def cyl(name, r, h, loc, color, col=None, verts=16, rot=(0, 0, 0)):
    import bmesh
    m = proto('cyl%d' % verts, lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=1, radius2=1, depth=1))
    return _place(name, m, (loc[0], loc[1], loc[2] + h / 2), (r, r, h), rot, color, col)

def _crown_mesh(k):
    """树冠/绿植原型：几团不规则叶簇 + 顶点噪声起伏（4 种变体轮流用），避免卡通球"""
    import bmesh
    from mathutils import noise as mnoise, Vector as V3
    def build(bm):
        rnd = random.Random(100 + k)
        for i in range(5):
            off = V3((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.3, 0.4)))
            g = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=rnd.uniform(0.55, 0.8))
            for v in g['verts']: v.co += off
        for v in bm.verts:
            v.co += v.co.normalized() * (mnoise.noise(v.co * 2.6 + V3((k * 7.3, 0, 0))) * 0.35)
    return proto('crown%d' % k, build)

def sphere(name, r, loc, color, col=None, scale=(1, 1, 1)):
    if name.startswith('ext_crown') or name == 'prop_plant':
        k = int(abs(loc[0] * 13 + loc[1] * 7)) % 4
        return _place(name, _crown_mesh(k), loc, tuple(r * s for s in scale), (0, 0, (loc[0] * 3.1 + loc[1]) % 6.28), color, col)
    import bmesh
    m = proto('uvsphere', lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1))
    return _place(name, m, loc, tuple(r * s for s in scale), (0, 0, 0), color, col)

def light(name, kind, loc, energy, color=(1, 1, 1), rot=(0, 0, 0), size=0.5, col=None):
    l = bpy.data.lights.new(name, kind); l.energy = energy; l.color = color
    if kind == 'AREA': l.size = size
    if kind in ('POINT', 'SPOT'): l.shadow_soft_size = size
    o = bpy.data.objects.new(name, l); o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    (col or bpy.context.scene.collection).objects.link(o); return o

def world(rgb, strength=1.0):
    w = bpy.data.worlds.get('v11_world') or bpy.data.worlds.new('v11_world'); w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*rgb, 1); bg.inputs['Strength'].default_value = strength
    bpy.context.scene.world = w

def room(prefix, W, D, H, col, wall_c='wall', floor_c='floor', openings=()):
    """地面 + 天花 + 四面墙；openings: [(墙 'N/S/E/W', 中心偏移, 底高, 宽, 高)] 在墙上开洞（拆成墙块拼）"""
    box(prefix + 'floor_main', (W, D, 0.02), (0, 0, -0.02), floor_c, col)
    box(prefix + 'wall_ceiling', (W, D, 0.05), (0, 0, H), 'white', col)
    walls = {'N': ((W, 0.12), (0, D / 2)), 'S': ((W, 0.12), (0, -D / 2)), 'E': ((0.12, D), (W / 2, 0)), 'W': ((0.12, D), (-W / 2, 0))}
    for side, ((sx, sy), (cx, cy)) in walls.items():
        ops = [o for o in openings if o[0] == side]
        length = sx if side in 'NS' else sy
        if not ops:
            box('%swall_%s' % (prefix, side), (sx, sy, H), (cx, cy, 0), wall_c, col); continue
        # 沿墙方向切分：开洞左右墙块 + 洞上方/下方墙块
        cuts = sorted(ops, key=lambda o: o[1]); pos = -length / 2; k = 0
        for _, off, bottom, w, h in cuts:
            a, b = off - w / 2, off + w / 2
            seg = a - pos
            if seg > 0.01:
                c = (pos + a) / 2
                box('%swall_%s%d' % (prefix, side, k), (seg, sy, H) if side in 'NS' else (sx, seg, H),
                    (cx + c, cy, 0) if side in 'NS' else (cx, cy + c, 0), wall_c, col); k += 1
            if bottom > 0.01:
                box('%swall_%s%d' % (prefix, side, k), (w, sy, bottom) if side in 'NS' else (sx, w, bottom),
                    (cx + off, cy, 0) if side in 'NS' else (cx, cy + off, 0), wall_c, col); k += 1
            top = H - bottom - h
            if top > 0.01:
                box('%swall_%s%d' % (prefix, side, k), (w, sy, top) if side in 'NS' else (sx, w, top),
                    (cx + off, cy, bottom + h) if side in 'NS' else (cx, cy + off, bottom + h), wall_c, col); k += 1
            pos = b
        seg = length / 2 - pos
        if seg > 0.01:
            c = (pos + length / 2) / 2
            box('%swall_%s%d' % (prefix, side, k), (seg, sy, H) if side in 'NS' else (sx, seg, H),
                (cx + c, cy, 0) if side in 'NS' else (cx, cy + c, 0), wall_c, col)

def chair(name, loc, rot_z, col, color='wood'):
    x, y, z = loc; s, c = math.sin(rot_z), math.cos(rot_z)
    box(name + '_seat', (0.44, 0.44, 0.04), (x, y, 0.44), color, col, rot_z)
    box(name + '_back', (0.44, 0.04, 0.42), (x - s * 0.2, y + c * 0.2, 0.48), color, col, rot_z)
    for dx, dy in ((-0.19, -0.19), (0.19, -0.19), (-0.19, 0.19), (0.19, 0.19)):
        box(name + '_leg', (0.03, 0.03, 0.44), (x + dx * c - dy * s, y + dx * s + dy * c, 0), 'metal', col)

def table(name, size, loc, col, color='wood', h=0.75):
    x, y, _ = loc; w, d = size
    box(name + '_top', (w, d, 0.04), (x, y, h - 0.04), color, col)
    for dx in (-w / 2 + 0.05, w / 2 - 0.05):
        for dy in (-d / 2 + 0.05, d / 2 - 0.05):
            box(name + '_leg', (0.04, 0.04, h - 0.04), (x + dx, y + dy, 0), 'metal', col)

def books(name, n, loc, col, along='x', rnd=None):
    rnd = rnd or random.Random(hash(name) & 0xffff)
    x, y, z = loc; p = 0
    for i in range(n):
        t = rnd.uniform(0.02, 0.05); h = rnd.uniform(0.18, 0.28)
        cc = rnd.choice([(0.5, 0.2, 0.15), (0.15, 0.25, 0.45), (0.2, 0.4, 0.25), (0.75, 0.7, 0.55), (0.3, 0.3, 0.3)])
        box('%s_book%d' % (name, i), (t, 0.17, h) if along == 'x' else (0.17, t, h),
            (x + p, y, z) if along == 'x' else (x, y + p, z), cc, col); p += t + 0.002

def phone(name, loc, col, rot=(0, 0, 0), lying=True):
    """手机：机身 + 屏幕（单独物体 prop_screen_*，后期 Remotion 按它的位置贴真实界面）"""
    x, y, z = loc
    body = box('prop_phone_%s' % name, (0.075, 0.155, 0.008), (x, y, z), 'black', col)
    scr = box('prop_screen_%s' % name, (0.069, 0.148, 0.001), (x, y, z + 0.008), (0.05, 0.08, 0.12), col, emit=0.0)
    scr.parent = body; scr.matrix_parent_inverse = body.matrix_world.inverted()
    body.rotation_euler = rot
    return body

# ---------------- 宿舍（四人间，上床下桌） ----------------
def dorm(time='am'):
    col = coll('set_dorm'); W, D, H = 3.4, 6.0, 3.2   # 层高 3.2 m：上铺坐起来头顶留出空间
    room('dorm_', W, D, H, col, openings=[('N', 0.0, 0.9, 1.6, 1.5), ('S', 1.0, 0.0, 0.9, 2.1)])
    box('dorm_glass_window', (1.6, 0.02, 1.5), (0, D / 2, 0.9), 'glass', col, alpha=0.25)
    for sx in (-1, 1):   # 窗帘
        box('dorm_fabric_curtain', (0.35, 0.04, 2.0), (sx * 1.0, D / 2 - 0.1, 0.7), 'fabric', col)
    box('dorm_wood_door', (0.9, 0.05, 2.1), (1.45, -D / 2 + 0.45, 0), 'wood', col, rot_z=math.radians(80))   # 门半开
    marks = {}
    # 四个床位：左右各两组（床在 1.75m 高，下面是书桌+书架）
    units = {'lin': (-1, -0.6), 'other1': (-1, 1.5), 'chen': (1, -0.6), 'other2': (1, 1.5)}
    for who, (sx, cy) in units.items():
        x = sx * (W / 2 - 0.48)
        box('furn_bed_%s' % who, (0.95, 2.0, 0.12), (x, cy, 1.70), 'wood', col)
        box('furn_mattress_%s' % who, (0.9, 1.95, 0.10), (x, cy, 1.82), 'white', col)
        box('furn_quilt_%s' % who, (0.88, 1.3, 0.04), (x, cy + 0.25, 1.925), 'fabric', col)   # 比床垫高 5mm：底面和床垫面重合时，落座射线穿过被子后起点在床垫里面，漏掉床垫、把人压到床板上（2026-11-22）；4cm：原来 12cm 的被子方块把坐在床上的人下半身整个盖住，像陷进床里（2026-11-22）
        box('furn_pillow_%s' % who, (0.5, 0.3, 0.1), (x, cy - 0.75, 1.925), 'white', col)
        box('furn_rail_%s' % who, (0.04, 1.45, 0.3), (x - sx * 0.46, cy + 0.275, 1.82), 'metal', col)   # 护栏在梯子口留缺口（原来 2m 整条拦住梯子，下床时腿必穿过护栏）
        for dy in (-0.98, 0.98):
            for dx in (-0.45, 0.45):
                box('furn_post_%s' % who, (0.05, 0.05, 2.1), (x + dx, cy + dy, 0), 'metal', col)
        box('furn_desk_%s' % who, (0.6, 1.4, 0.04), (sx * (W / 2 - 0.3), cy + 0.25, 0.72), 'wood', col)
        # 桌上书架：开放式（背板 + 两侧板 + 三层隔板），书放在最下层隔板上。原来是 0.28×1.4×0.7 的实心方块、书嵌在里面，
        # 侧后方看就是一大块方木挡在人脸前，云端也会当成柜子（2026-11-23）
        bx = sx * (W / 2 - 0.15)
        box('furn_shelf_%s' % who, (0.02, 1.4, 0.48), (sx * (W / 2 - 0.02), cy + 0.25, 1.18), 'wood', col)
        for dy in (-0.69, 0.69):
            box('furn_shelfside_%s' % who, (0.28, 0.02, 0.48), (bx, cy + 0.25 + dy, 1.18), 'wood', col)
        for z in (1.18, 1.50):   # 第二层留够书高（书最高 28cm）；最下层离桌面 42cm（原来 24cm，人趴在桌上头卡进隔板，2026-11-23）；上铺床板在 1.70，再往上没地方
            box('furn_shelfboard_%s' % who, (0.28, 1.4, 0.02), (bx, cy + 0.25, z), 'wood', col)
        books('furn_%s' % who, 10, (sx * (W / 2 - 0.15), cy - 0.3, 1.20), col, along='y')
        for k in range(4):   # 梯子：靠过道、床头一侧
            box('furn_ladder_%s' % who, (0.04, 0.4, 0.03), (x - sx * 0.47, cy - 0.75, 0.35 + k * 0.4), 'metal', col)
        for dy in (-0.95, -0.55):
            box('furn_ladderrail_%s' % who, (0.04, 0.04, 1.85), (x - sx * 0.47, cy + dy, 0), 'metal', col)
        chair('furn_chair_%s' % who, (sx * (W / 2 - 0.85), cy + 0.25, 0), math.radians(90 * sx), col)
        marks[who + '_desk_seat'] = (sx * (W / 2 - 0.85), cy + 0.25, 0.0, 90 * sx)   # x,y,z,朝向°（0=面向-Y）
        marks[who + '_bed'] = (x, cy, 1.92, 0)
        marks[who + '_ladder_foot'] = (x - sx * 0.75, cy - 0.75, 0.0, 90 * sx)
    # 林晓桌上：显示器、外卖盒、手机；陈瑶桌上：单词书
    box('prop_monitor_lin', (0.05, 0.55, 0.35), (-W / 2 + 0.2, -0.35, 0.78), 'dark', col)
    box('prop_monitorscreen_lin',   # 不能叫 prop_screen_*：那是手机屏幕的前缀（机位检查放行、遮罩编号 15），显示器会挡在镜头前也不被移走
         (0.005, 0.5, 0.3), (-W / 2 + 0.23, -0.35, 0.80), (0.1, 0.12, 0.15), col)
    for i in range(3): box('prop_takeout_%d' % i, (0.18, 0.14, 0.07), (-W / 2 + 0.38, 0.1 + i * 0.2, 0.76), 'white', col)
    # 原来这里还摆了一部林晓的手机（枕边）：shoot 另外给每人一对 手上/放下 的手机按剧情切换显示，这部永远不藏，林晓拿着手机时床上还躺着一部（2026-11-25 衔接检查）。枕边那部改由 blocking.phones 的「放下」手机负责
    box('prop_wordbook_chen', (0.17, 0.24, 0.02), (W / 2 - 0.45, -0.45, 0.76), (0.85, 0.3, 0.2), col)
    # 门边洗手台 + 镜子
    box('furn_sink_cabinet', (0.55, 0.5, 0.82), (-W / 2 + 0.33, -D / 2 + 0.45, 0), 'white', col)
    box('furn_sink_basin', (0.42, 0.36, 0.05), (-W / 2 + 0.33, -D / 2 + 0.45, 0.82), 'metal', col)
    box('furn_mirror', (0.02, 0.5, 0.65), (-W / 2 + 0.07, -D / 2 + 0.45, 1.15), (0.75, 0.8, 0.85), col)
    box('prop_cup_toothbrush', (0.07, 0.07, 0.1), (-W / 2 + 0.2, -D / 2 + 0.25, 0.82), (0.3, 0.55, 0.8), col)
    marks['sink'] = (-W / 2 + 0.92, -D / 2 + 0.45, 0.0, -90)
    marks['door'] = (1.0, -D / 2 + 0.4, 0.0, 0)
    marks['window'] = (0.0, D / 2 - 0.6, 0.0, 0)
    # 灯光（按时间段）
    lc = coll('light_dorm')
    if time in ('am', 'pm'):
        ang = (55, 0, 200) if time == 'am' else (40, 0, 160)
        light('light_sun', 'SUN', (0, 5, 4), 4.0 if time == 'am' else 3.0, (1.0, 0.92, 0.8), ang, col=lc)
        light('light_fill', 'AREA', (0, 0, 2.9), 120, (1, 0.97, 0.92), (0, 0, 0), 2.5, lc)
        world((0.75, 0.82, 0.95), 0.6)
    else:
        for who, (sx, cy) in units.items():
            if who in ('lin', 'chen'):
                light('light_desklamp_%s' % who, 'POINT', (sx * (W / 2 - 0.3), cy, 1.3), 35 if time == 'nt' else 25, (1.0, 0.8, 0.55), size=0.1, col=lc)
                cyl('prop_lamp_%s' % who, 0.06, 0.4, (sx * (W / 2 - 0.3), cy, 0.76), 'metal', col)
        if time == 'dusk':
            light('light_sky', 'AREA', (0, D / 2 + 0.5, 1.6), 60, (0.9, 0.6, 0.5), (90, 0, 0), 1.5, lc)
            world((0.25, 0.18, 0.2), 0.3)
        else:   # 深夜：窗外冷色月光 + 很弱的环境光——暗，但人和动作看得清（原先只有两盏台灯，回忆段落整段全黑）
            light('light_moon', 'AREA', (0, D / 2 - 0.15, 1.7), 45, (0.55, 0.65, 1.0), (90, 0, 0), 1.6, lc)
            light('light_nightbounce', 'AREA', (0, 0, H - 0.1), 14, (0.55, 0.62, 0.9), (0, 0, 0), 3.0, lc)
            world((0.03, 0.04, 0.08), 0.35)
    cams = {'wide_from_door': ((0.9, -2.7, 1.6), (0.0, 1.5, 1.1), 24), 'wide_from_window': ((0.0, 2.6, 1.7), (0.0, -1.5, 1.1), 24)}
    return dict(marks=marks, cams=cams, bounds=(-W / 2, -D / 2, W / 2, D / 2))

# ---------------- 图书馆阅览室 ----------------
def lib():
    col = coll('set_lib'); W, D, H = 14.0, 10.0, 4.0
    room('lib_', W, D, H, col, openings=[('E', y, 0.8, 2.2, 2.6) for y in (-3, 0, 3)] + [('S', -4.5, 0, 1.6, 2.4)])
    for y in (-3, 0, 3): box('lib_glass_win%d' % y, (0.02, 2.2, 2.6), (W / 2, y, 0.8), 'glass', col, alpha=0.25)
    for i, y in enumerate((-3.5, 0, 3.5)):   # 三排长桌
        for j, x in enumerate((-3.5, 1.0)):
            table('furn_libtable_%d%d' % (i, j), (3.6, 1.2), (x, y, 0), col)
            for k in range(4):
                for side in (-1, 1):
                    chair('furn_libchair_%d%d%d%d' % (i, j, k, side), (x - 1.35 + k * 0.9, y + side * 0.8, 0), math.radians(180 if side < 0 else 0), col)
    for y in (-4, -1.5, 1, 3.5):   # 西墙书架
        box('furn_bookshelf', (0.4, 2.2, 2.3), (-W / 2 + 0.25, y, 0), 'wood', col)
        for z in (0.4, 0.95, 1.5, 2.05): books('furn_libbooks%d' % int(z * 10 + y * 100), 30, (-W / 2 + 0.35, y - 1.0, z), col, along='y')
    # 南北墙原来是空白墙面：二转三照着白模画成空房间，视频又自己补出书架，镜头之间背景来回跳（2026-11-25 用户定为严重失真，重做这一场）
    # → 南北墙都立满开放式书架（侧板、背板、层板、书），每张长桌放两盏台灯
    def shelf_unit(nm, cx, cy, wall, w=2.0, d=0.3, h=2.3):   # wall=+1：墙在 +y 一侧
        by = cy + wall * (d / 2 - 0.01)
        box(nm + '_back', (w, 0.02, h), (cx, by, 0), 'wood', col)
        for sx in (-1, 1): box(nm + '_side', (0.03, d, h), (cx + sx * w / 2, cy, 0), 'wood', col)
        for k, z in enumerate((0.02, 0.5, 0.98, 1.46, 1.94, 2.27)):
            box(nm + '_plank', (w, d, 0.025), (cx, cy, z), 'wood', col)
            if z < 2.2: books('%s_b%d' % (nm, k), 34, (cx - w / 2 + 0.05, cy + wall * (d / 2 - 0.11), z + 0.025), col, along='x')
    for i, x in enumerate((-5.5, -3.3, -1.1, 1.1, 3.3, 5.5)):
        shelf_unit('furn_bookshelf_n%d' % i, x, D / 2 - 0.16, +1)
    for i, x in enumerate((-1.6, 0.6, 2.8, 5.0)):   # 南墙避开门（x -5.3~-3.7）
        shelf_unit('furn_bookshelf_s%d' % i, x, -D / 2 + 0.16, -1)
    for i, y in enumerate((-3.5, 0, 3.5)):
        for j, x in enumerate((-3.5, 1.0)):
            for dx in (-0.9, 0.9):
                cyl('prop_desklamp_%d%d%d' % (i, j, dx > 0), 0.012, 0.36, (x + dx, y, 0.75), 'metal', col)
                box('prop_desklamp_shade_%d%d%d' % (i, j, dx > 0), (0.28, 0.12, 0.07), (x + dx, y - 0.04, 1.08), (0.12, 0.35, 0.22), col)
    table('furn_windowtable', (1.4, 0.7), (W / 2 - 0.6, 0.0, 0), col)   # 靠窗座位
    chair('furn_windowchair', (W / 2 - 0.6, -0.6, 0), math.pi, col)
    light('light_sun', 'SUN', (10, 0, 6), 4.0, (1, 0.95, 0.85), (50, 0, 100))
    light('light_fill', 'AREA', (0, 0, 3.9), 400, (1, 1, 1), size=8)
    world((0.8, 0.85, 0.95), 0.7)
    return dict(marks={'entrance': (-4.5, -D / 2 + 0.8, 0, 0), 'chen_seat': (-2.6, -3.5 - 0.8, 0, 0), 'saved_seat': (-1.7, -3.5 - 0.8, 0, 0),
                       'window_table': (W / 2 - 0.6, 0.0, 0.75, 0), 'window_seat': (W / 2 - 0.6, -0.6, 0, 0)},
                cams={'wide': ((-6.0, -4.5, 2.2), (2.0, 1.0, 1.0), 24)}, bounds=(-W / 2, -D / 2, W / 2, D / 2))

# ---------------- 图书馆门口（室外） ----------------
def libdoor():
    col = coll('set_libdoor')
    box('ext_ground', (60, 60, 0.02), (0, 0, -0.02), (0.45, 0.43, 0.40), col)
    for i in range(8):   # 8 级石阶
        box('ext_step%d' % i, (12, 0.45, 0.15 * (i + 1)), (0, 2.0 + i * 0.45, 0), 'stone', col)
    top = 1.2; box('ext_landing', (12, 3, top), (0, 6.6, 0), 'stone', col)
    box('ext_facade', (24, 1.0, 12), (0, 8.6, 0), (0.58, 0.55, 0.50), col)
    for x in (-4.5, -1.6, 1.6, 4.5): cyl('ext_column', 0.35, 6, (x, 7.6, top), 'stone', col)
    box('ext_lintel', (11, 1.2, 0.8), (0, 7.6, top + 6), 'stone', col)
    box('ext_glass_doorL', (1.0, 0.05, 2.6), (-0.52, 8.08, top), 'glass', col, alpha=0.4)
    box('ext_glass_doorR', (1.0, 0.05, 2.6), (0.52, 8.08, top), 'glass', col, alpha=0.4)
    box('ext_doorframe', (2.3, 0.08, 0.1), (0, 8.1, top + 2.6), 'dark', col)
    box('prop_notice', (0.21, 0.005, 0.297), (0.45, 8.05, top + 1.35), 'paper', col)   # A4 通知（文字后期贴）
    import outdoor as od
    rnd = random.Random(3)
    od.building('ext_libwing', (14, 10, 14), (-20, 14, 0), col, rnd, (0.60, 0.56, 0.50), lit=0.0)     # 两侧配楼（带窗格、楼层线）
    od.building('ext_libwing2', (14, 10, 14), (20, 14, 0), col, rnd, (0.60, 0.56, 0.50), lit=0.0)
    for x in range(-11, 12, 2):                                                                          # 门楣上方一排窗
        box('ext_facade_window', (1.2, 0.06, 2.2), (x, 8.08, top + 7.6), (0.30, 0.35, 0.40), col)
    od.scatter_trees(col, rnd, 22, (-26, 26), (-12, 6), avoid=[(-7.5, 7.5, -13, 9)], season='autumn')  # 秋天：黄绿相间、高矮不一
    for x in (-8.5, 8.5):
        od.flowerbed((x, 1.2), (3.0, 1.4), col, rnd); od.lamppost((x * 1.25, -1.0, 0), col, rot=math.pi if x > 0 else 0.0)
        od.bench((x * 0.95, -2.6, 0), col, rot=0.0); od.trash_bin((x * 0.95 + 1.2, -2.4), col)
    od.hedge((-26, -0.4), (-7.5, -0.4), col); od.hedge((7.5, -0.4), (26, -0.4), col)
    od.bike_rack((-14, -3.5), 9, col, rnd, rot=math.radians(90)); od.sign((10.5, -4.2), col, rot=0.0)
    for x in (-60, 60): od.curb((x, -6.0), (0, -6.0), col)
    light('light_sun', 'SUN', (0, -10, 10), 2.6, (1, 0.93, 0.82), (55, 0, -20))
    od.sky('day', 0.8)
    return dict(marks={'step_bottom': (0, 1.5, 0, 0), 'door': (0.2, 7.4, top, 0), 'step_sit': (0.8, 5.1, 1.05, 180)},
                cams={'wide': ((3.0, -6.0, 2.0), (0.0, 6.0, 2.0), 30)},
                walkers=[('extM2', (-22, -4.5), (22, -4.5), 0.0), ('extF1', (24, -5.2), (-20, -5.2), 1.5),   # 门前路上来往的学生
                         ('extF3', (-18, -7.5), (18, -7.5), 3.0), ('extM3', (16, -3.2), (-16, -3.2), 5.0)])

# ---------------- 食堂 ----------------
def canteen():
    col = coll('set_canteen'); W, D, H = 24.0, 16.0, 4.5
    room('can_', W, D, H, col, wall_c=(0.85, 0.85, 0.82), floor_c=(0.70, 0.70, 0.68),
         openings=[('S', x, 0.9, 3.0, 2.2) for x in (-6, 0, 6)] + [('W', 4, 0, 2.4, 2.6)])
    box('furn_counter', (16, 0.8, 1.0), (0, D / 2 - 1.2, 0), (0.75, 0.75, 0.78), col)
    box('furn_counter_glass', (16, 0.05, 0.6), (0, D / 2 - 1.5, 1.0), 'glass', col, alpha=0.3)
    for i in range(8): box('furn_window_sign%d' % i, (1.6, 0.05, 0.4), (-7 + i * 2, D / 2 - 0.1, 2.6), (0.85, 0.3, 0.2), col)
    for r, y in enumerate((-5, -2.5, 0, 2.5)):
        for c_, x in enumerate((-8, -4, 0, 4, 8)):
            table('furn_cantable_%d%d' % (r, c_), (1.8, 0.8), (x, y, 0), col, color=(0.85, 0.85, 0.82))
            for k in (-0.5, 0.5):
                for side in (-1, 1):
                    box('furn_stool', (0.35, 0.35, 0.45), (x + k, y + side * 0.65, 0), (0.75, 0.2, 0.2), col)
    # 东、西、南三面墙原来空白：关键帧画成空灰房间，视频又自己补出打饭窗口、蒸锅、满屋食客，镜头之间背景来回跳（2026-11-25 衔接检查，同图书馆）
    # → 东墙：饮料冷柜、餐具回收架、宣传画、横幅；西墙：洗手池+镜子、宣传画；南墙窗间：宣传画、绿植；北墙打饭窗口上方加菜单灯箱
    st, red, wht = (0.72, 0.73, 0.75), (0.78, 0.15, 0.12), (0.92, 0.92, 0.9)
    for k, y in enumerate((-0.6, 0.7)):
        box('furn_cooler%d' % k, (0.7, 1.2, 2.0), (W / 2 - 0.4, y, 0), st, col)
        box('furn_cooler%d_glass' % k, (0.02, 1.05, 1.6), (W / 2 - 0.76, y, 0.25), 'glass', col, alpha=0.35)
        for z in (0.5, 0.9, 1.3, 1.7):
            for j in range(6): cyl('furn_cooler%d_bottle%d%d' % (k, int(z * 10), j), 0.035, 0.24, (W / 2 - 0.55, y - 0.45 + j * 0.18, z), ((0.2, 0.5, 0.8), (0.9, 0.5, 0.1), (0.3, 0.7, 0.3))[j % 3], col)
    box('furn_trayrack', (0.55, 2.2, 1.7), (W / 2 - 0.3, -4.0, 0), st, col)
    for z in (0.3, 0.6, 0.9, 1.2, 1.5): box('furn_trayrack_trays%d' % int(z * 10), (0.45, 2.0, 0.06), (W / 2 - 0.33, -4.0, z), (0.55, 0.45, 0.35), col)
    for k, (x, y) in enumerate(((W / 2 - 0.075, 3.6), (W / 2 - 0.075, 5.4), (-W / 2 + 0.075, -1.2), (-W / 2 + 0.075, 1.0))):
        box('furn_poster%d' % k, (0.02, 0.9, 1.25), (x, y, 1.2), ((0.2, 0.45, 0.7), (0.85, 0.6, 0.2), (0.3, 0.6, 0.35), (0.75, 0.3, 0.25))[k], col)
    box('furn_banner_e', (0.02, 5.0, 0.55), (W / 2 - 0.075, -1.5, 3.1), red, col)
    box('furn_banner_w', (0.02, 5.0, 0.55), (-W / 2 + 0.075, -3.0, 3.1), red, col)
    box('furn_washbasin', (0.6, 3.0, 0.85), (-W / 2 + 0.3, -4.5, 0), wht, col)
    box('furn_washmirror', (0.02, 3.0, 1.0), (-W / 2 + 0.075, -4.5, 1.2), 'glass', col, alpha=0.6)
    for k, x in enumerate((-9.0, -3.0, 3.0, 9.0)):
        box('furn_poster_s%d' % k, (0.9, 0.02, 1.25), (x, -D / 2 + 0.075, 1.2), ((0.3, 0.55, 0.75), (0.8, 0.35, 0.25), (0.35, 0.6, 0.35), (0.85, 0.65, 0.25))[k], col)
    for k, x in enumerate((-10.5, -1.5, 1.5, 10.5)):
        cyl('furn_plantpot%d' % k, 0.22, 0.45, (x, -D / 2 + 0.4, 0), (0.45, 0.3, 0.22), col)
        cyl('furn_plant%d' % k, 0.35, 0.9, (x, -D / 2 + 0.4, 0.45), (0.2, 0.45, 0.2), col)
    box('furn_menuboard', (14, 0.06, 0.7), (0, D / 2 - 0.1, 3.2), (0.15, 0.15, 0.15), col)
    for i in range(10): light('light_tube%d' % i, 'AREA', (-9 + i * 2, 0, H - 0.05), 150, (1, 1, 0.98), size=1.2)
    world((0.85, 0.88, 0.92), 0.6)
    return dict(marks={'queue': (0, D / 2 - 2.6, 0, 0), 'lin_table': (0, -2.5, 0, 0), 'classB_seat': (4, -2.5 - 0.65, 0, 0),
                       'exit': (-W / 2 + 1, 4, 0, -90)},
                cams={'wide': ((-9, -7, 2.4), (2, 3, 1.0), 24)}, bounds=(-W / 2, -D / 2, W / 2, D / 2))

# ---------------- 夜晚操场 ----------------
def track():
    col = coll('set_track')
    box('ext_ground', (200, 200, 0.02), (0, 0, -0.03), (0.15, 0.25, 0.12), col)
    box('ext_track_straight', (100, 9.8, 0.02), (0, 0, -0.01), C['red'], col)
    for i in range(9): box('ext_lane%d' % i, (100, 0.05, 0.005), (0, -4.88 + i * 1.22, 0.01), 'white', col)
    for x in range(-45, 50, 15):   # 跑道外侧路灯
        cyl('ext_lamppost', 0.08, 7, (x, -7.0, 0), 'metal', col)
        l = light('light_streetlamp%d' % x, 'SPOT', (x, -6.4, 6.8), 6000, (1.0, 0.75, 0.45), (0, 0, 0), 0.3); l.data.spot_size = math.radians(130)
        sphere('ext_lampglow', 0.25, (x, -6.6, 6.9), (1.0, 0.8, 0.5), col)
    for k in range(6):   # 看台
        box('ext_stand%d' % k, (60, 1.0, 0.5 * (k + 1)), (0, 12 + k * 1.0, 0), (0.55, 0.55, 0.58), col)
    for x in (-25, 25): light('light_floodlight', 'SPOT', (x, 18, 14), 20000, (0.9, 0.95, 1.0), (-55, 0, 0), 0.5)
    light('light_moon', 'SUN', (0, 0, 20), 0.15, (0.6, 0.7, 1.0), (60, 0, 30))
    import outdoor as od
    rnd = random.Random(21)
    box('ext_field', (90, 20, 0.02), (0, 15.5 - 10, -0.02), (0.18, 0.34, 0.14), col)                  # 跑道内侧的足球场草皮
    for x in (-40, 40):                                                                                    # 球门
        for dy in (-3.66, 3.66): cyl('ext_goalpost', 0.06, 2.44, (x, 7.0 + dy, 0), 'white', col, verts=8)
        box('ext_goalbar', (0.12, 7.32, 0.12), (x, 7.0, 2.38), 'white', col)
    for k in range(-50, 51, 4): box('ext_fence', (0.06, 0.06, 1.8), (k, -9.0, 0), (0.25, 0.30, 0.28), col)   # 跑道外侧护栏
    box('ext_fence_rail', (100, 0.05, 0.05), (0, -9.0, 1.75), (0.25, 0.30, 0.28), col)
    od.scatter_trees(col, rnd, 26, (-55, 55), (-22, -11), season='summer')                              # 护栏外的树
    for x in (-36, -6, 26):
        od.building('ext_teachbldg', (24, 14, 18), (x, -42, 0), col, rnd, (0.55, 0.53, 0.50), lit=0.35, face='+Y')   # 远处亮着灯的教学楼
    od.sky('night', 0.5)
    return dict(marks={'walk_start': (-12, -3.0, 0, 90), 'walk_end': (12, -3.0, 0, 90)},
                cams={'wide': ((-2, -16, 2.0), (0, -3, 1.2), 35)},
                walkers=[('extF2', (30, 3.6), (-40, 3.6), 0.0), ('extM3', (-38, 2.4), (30, 2.4), 4.0),    # 夜跑/散步的人（在远侧跑道）
                         ('extM1', (40, 4.6), (-30, 4.6), 9.0)])

# ---------------- 学院活动室（茶话会） ----------------
def classroom():
    col = coll('set_class'); W, D, H = 10.0, 8.0, 3.2
    room('cls_', W, D, H, col, openings=[('E', y, 0.9, 1.8, 1.8) for y in (-2, 1.5)] + [('S', -3.5, 0, 1.0, 2.1)])
    for y in (-2, 1.5): box('cls_glass_win', (0.02, 1.8, 1.8), (W / 2, y, 0.9), 'glass', col, alpha=0.25)
    box('furn_blackboard', (4.0, 0.05, 1.2), (0, D / 2 - 0.08, 0.9), 'board', col)
    box('prop_chalktitle', (2.6, 0.01, 0.3), (0, D / 2 - 0.11, 1.65), (0.9, 0.9, 0.9), col)   # 黑板标题（文字后期贴）
    marks = {}
    order = ['wang', 'lin', 'chen', 'zhou', 'classA', 'classB', 'x1', 'x2', 'x3', 'x4', 'x5', 'x6']
    R = 2.6
    for i, who in enumerate(order):   # 椅子围成一圈，面向圆心
        a = math.radians(90 + i * 360 / len(order)); x, y = R * math.cos(a), R * math.sin(a) - 0.3
        rot = a - math.radians(90)
        chair('furn_circlechair_%s' % who, (x, y, 0), rot, col)
        marks[who + '_seat'] = (x, y, 0, math.degrees(rot))
    # 西墙、南墙原来空白：视频自己补出窗户、海报，镜头之间背景来回跳（2026-11-25 衔接检查，同图书馆/食堂）
    # → 围圈开班会时课桌推到墙边（西墙一排、南墙门右侧一排）；南墙后黑板报、西墙软木公告栏和宣传画、黑板上方挂钟
    for k, y in enumerate((-2.7, -1.5, -0.3, 0.9, 2.1)):
        table('furn_pushdesk_w%d' % k, (0.6, 1.1), (-W / 2 + 0.4, y, 0), col)
    for k, x in enumerate((-1.6, -0.4, 0.8, 2.0, 3.2)):
        table('furn_pushdesk_s%d' % k, (1.1, 0.6), (x, -D / 2 + 0.4, 0), col)
    box('furn_backboard', (3.6, 0.04, 1.2), (0.8, -D / 2 + 0.08, 1.15), (0.2, 0.32, 0.25), col)
    for k, (x, c_) in enumerate(((-0.4, (0.85, 0.4, 0.3)), (0.5, (0.9, 0.8, 0.4)), (1.5, (0.4, 0.6, 0.85)), (2.2, (0.95, 0.95, 0.9)))):
        box('furn_backboard_paper%d' % k, (0.5, 0.01, 0.4), (x, -D / 2 + 0.105, 1.45 - (k % 2) * 0.5), c_, col)
    box('furn_noticeboard', (0.03, 1.8, 1.0), (-W / 2 + 0.075, 0.0, 1.25), (0.65, 0.5, 0.32), col)
    for k, y in enumerate((-0.5, 0.2, 0.6)):
        box('furn_noticeboard_paper%d' % k, (0.01, 0.3, 0.4), (-W / 2 + 0.095, y, 1.45 - (k % 2) * 0.45), (0.95, 0.95, 0.9), col)
    for k, y in enumerate((-2.6, 2.4)):
        box('furn_poster%d' % k, (0.02, 0.6, 0.85), (-W / 2 + 0.075, y, 1.35), ((0.3, 0.5, 0.75), (0.8, 0.35, 0.25))[k], col)
    cyl('furn_clock', 0.16, 0.04, (0, D / 2 - 0.08, 2.55), (0.95, 0.95, 0.95), col, rot=(math.radians(90), 0, 0))
    light('light_sun', 'SUN', (8, 0, 5), 3.5, (1, 0.93, 0.82), (45, 0, 110))
    light('light_fill', 'AREA', (0, 0, 3.1), 250, size=5)
    world((0.85, 0.85, 0.9), 0.6)
    return dict(marks=marks, cams={'wide': ((-4.2, -3.6, 2.2), (0.5, 0.5, 0.8), 24)}, bounds=(-W / 2, -D / 2, W / 2, D / 2))

# ---------------- 家里客厅 ----------------
def home(time='pm'):
    col = coll('set_home'); W, D, H = 6.0, 5.0, 2.8
    room('home_', W, D, H, col, wall_c=(0.88, 0.84, 0.76), floor_c=(0.60, 0.45, 0.32), openings=[('N', 1.5, 0.6, 1.8, 1.7)])
    box('furn_sofa_base', (2.2, 0.9, 0.42), (0, -1.6, 0), 'sofa', col)
    box('furn_sofa_back', (2.2, 0.25, 0.5), (0, -2.0, 0.42), 'sofa', col)
    for sx in (-1, 1): box('furn_sofa_arm', (0.2, 0.9, 0.6), (sx * 1.1, -1.6, 0), 'sofa', col)
    table('furn_coffeetable', (1.1, 0.6), (0, -0.4, 0), col, h=0.42)
    box('furn_tvcabinet', (1.8, 0.4, 0.5), (0, D / 2 - 0.3, 0), 'wood', col)
    cyl('prop_plantpot', 0.18, 0.4, (-2.4, -1.9, 0), (0.6, 0.55, 0.5), col); sphere('prop_plant', 0.45, (-2.4, -1.9, 0.9), 'leaf', col, (1, 1, 1.4))
    cyl('prop_floorlamp', 0.02, 1.5, (1.5, -1.9, 0), 'metal', col); cyl('prop_lampshade', 0.2, 0.25, (1.5, -1.9, 1.5), 'paper', col)
    if time == 'pm':
        light('light_sun', 'SUN', (2, 6, 4), 3.0, (1, 0.9, 0.75), (50, 0, 170)); light('light_fill', 'AREA', (0, 0, 2.7), 100, size=3)
        world((0.8, 0.8, 0.85), 0.5)
    else:
        light('light_floorlamp', 'POINT', (1.5, -1.9, 1.55), 250, (1, 0.78, 0.5), size=0.15); light('light_bounce', 'AREA', (0, 0, 2.7), 25, (1, 0.85, 0.65), size=3); world((0.02, 0.02, 0.04), 0.3)
    return dict(marks={'sofa_seat': (0.0, -1.55, 0.0, 0)}, cams={'wide': ((2.2, 1.8, 1.5), (0, -1.6, 0.8), 28)}, bounds=(-W / 2, -D / 2, W / 2, D / 2))

# ---------------- 初夏草坪 ----------------
def lawn():
    col = coll('set_lawn')
    box('ext_grass', (120, 120, 0.02), (0, 0, -0.02), (0.30, 0.55, 0.20), col)
    box('ext_path', (3, 120, 0.02), (-8, 0, -0.01), (0.7, 0.68, 0.62), col)
    import outdoor as od
    rnd = random.Random(7)
    box('ext_path2', (120, 2.5, 0.02), (0, 32, -0.01), (0.7, 0.68, 0.62), col)                       # 横穿草坪的小路
    # 11-27 用户指出「现实里根本没有这样平坦开阔空旷的地方」：原来楼在 70 米外、树稀稀拉拉、人物站的一大片刻意空着。
    # → 改成真实校园里被楼和树围起来的院落式草坪：楼拉近到草坪边、四周成排行道树、路边绿篱、更多来往的学生；人物站位和走位路线不动。
    od.scatter_trees(col, rnd, 30, (-34, 34), (6, 38), avoid=[(-10.5, -5.5, -60, 60), (-60, 60, 30, 34), (-7, 7, -2, 29)])
    for x in list(range(-34, -11, 4)) + list(range(-3, 35, 4)):                                             # 横路两侧成排的行道树（香樟）
        if abs(x) > 7: od.tree((x, 29.2, 0), rnd, col, scale=1.15)
        od.tree((x + 2, 35.6, 0), rnd, col, scale=1.2)
    for y in range(-12, 46, 5):                                                                            # 竖路两侧行道树
        od.tree((-12.6, y, 0), rnd, col, scale=1.1); od.tree((-3.6, y + 2.5, 0), rnd, col, scale=1.05) if y < -3 or y > 30 else None
    od.hedge((-40, 30.6, 0), (-11, 30.6, 0), col); od.hedge((-5, 30.6, 0), (40, 30.6, 0), col)              # 路边绿篱
    od.hedge((-40, 33.9, 0), (-11, 33.9, 0), col); od.hedge((-5, 33.9, 0), (40, 33.9, 0), col)
    for y in range(-20, 50, 9):                                                                            # 沿路：路灯、长椅、垃圾桶
        od.lamppost((-10.2, y, 0), col, rot=0.0)
        if y % 2: od.bench((-11.2, y + 3, 0), col, rot=math.radians(-90)); od.trash_bin((-11.0, y + 4.6), col)
    for x, y in ((-16, 12), (12, 18), (22, 8), (-25, 22), (16, 4), (-22, 6), (26, 22)):
        for k in range(rnd.randint(3, 5)): od.bush((x + rnd.uniform(-1.5, 1.5), y + rnd.uniform(-1, 1), 0), rnd, col)
    od.flowerbed((6, 30), (4, 1.6), col, rnd); od.flowerbed((-20, 30), (4, 1.6), col, rnd)
    for x, y in ((10, -3), (13, 3), (-15, -2), (9.5, 9), (16, -6)):                                         # 镜头两侧近处的树，给画面前景层次
        od.tree((x, y, 0), rnd, col, scale=1.1)
        for k in range(2): od.bush((x + rnd.uniform(-1.2, 1.2), y + rnd.uniform(-1, 1), 0), rnd, col)
    for k, x in enumerate((-28, 0, 28)):                                                                   # 教学楼/宿舍楼拉近到草坪边（原来在 70 米外）
        od.building('ext_building%d' % k, (24, 14, 18), (x, 46, 0), col, rnd, ((0.85, 0.82, 0.76), (0.78, 0.74, 0.70), (0.82, 0.80, 0.78))[k])
    for k, sx in enumerate((-1, 1)):                                                                       # 两侧稍靠前的楼，围成院落（building 只支持正立面朝 ±Y，正面朝镜头）
        od.building('ext_building_side%d' % k, (20, 12, 15), (sx * 44, 22, 0), col, rnd, ((0.80, 0.77, 0.72), (0.84, 0.81, 0.75))[k])
    od.bike_rack((-14.5, 38), 14, col, rnd, rot=math.radians(90))
    light('light_sun', 'SUN', (0, -10, 10), 5.0, (1, 0.96, 0.88), (45, 0, -30))
    od.sky('day', 1.0)
    return dict(marks={'trio': (0, 0, 0, 0), 'walk_to': (0, 25, 0, 0)}, cams={'wide': ((3, -8, 1.6), (0, 2, 1.2), 30)},
                walkers=[('extF1', (-7.5, 45), (-7.5, -15), 0.0), ('extM1', (-8.6, -12), (-8.6, 45), 2.0),     # 小路上来往
                         ('extF3', (-30, 31.5), (25, 31.5), 1.0), ('extM2', (28, 32.5), (-25, 32.5), 6.0),
                         ('extM3', (-7.2, 40), (-7.2, -15), 8.0), ('extF2', (-40, 31), (20, 31), 10.0)])

# ---------------- 建立镜头用的外景 ----------------
def ext_dorm(time='am'):
    col = coll('set_extdorm')
    box('ext_ground', (150, 150, 0.02), (0, 0, -0.02), (0.4, 0.4, 0.38), col)
    box('ext_dormbuilding', (40, 12, 18), (0, 15, 0), (0.80, 0.76, 0.70), col)
    rnd = random.Random(11)
    for fl in range(6):
        for k in range(16):
            lit = (time == 'nt' and rnd.random() < 0.12) or (time == 'am' and rnd.random() < 0.25)
            box('ext_window', (1.4, 0.05, 1.3), (-18.5 + k * 2.47, 8.97, 1.2 + fl * 2.9), (1.0, 0.8, 0.5) if lit else (0.25, 0.3, 0.35),
                col, emit=6.0 if lit else 0.0)
    import outdoor as od
    for fl in range(1, 7):                                                                                 # 楼层线、阳台、屋顶
        box('ext_dorm_band', (40.2, 0.3, 0.15), (0, 8.85, fl * 2.9 + 0.1), (0.72, 0.68, 0.62), col)
    box('ext_dorm_parapet', (40.4, 12.4, 0.8), (0, 15, 18), (0.70, 0.66, 0.60), col)
    box('ext_dorm_canopy', (6, 2.2, 0.2), (0, 7.9, 3.0), (0.5, 0.5, 0.52), col); box('ext_dorm_door', (2.6, 0.1, 2.6), (0, 8.95, 0), (0.25, 0.30, 0.35), col)
    for x in range(-18, 20, 6):
        od.tree((x + rnd.uniform(-1, 1), 4 + rnd.uniform(-0.8, 0.8), 0), rnd, col, 'summer', rnd.uniform(0.9, 1.2))
    od.hedge((-20, 6.2), (-3.5, 6.2), col); od.hedge((3.5, 6.2), (20, 6.2), col)
    od.bike_rack((-16, 7.2), 14, col, rnd, rot=math.radians(90), step=0.7); od.bike_rack((6, 7.2), 12, col, rnd, rot=math.radians(90), step=0.7)
    box('ext_road', (150, 7, 0.02), (0, -2, -0.01), (0.33, 0.33, 0.34), col); od.curb((-75, 1.5), (75, 1.5), col); od.curb((-75, -5.5), (75, -5.5), col)
    for x in range(-24, 25, 12): od.lamppost((x, 2.0, 0), col, rot=math.radians(-90), night=(time == 'nt'))
    od.trash_bin((4.5, 5.6), col); od.sign((-6, 2.6), col)
    od.scatter_trees(col, rnd, 14, (-45, 45), (-25, -8))
    if time == 'am':
        light('light_sun', 'SUN', (0, -10, 10), 2.0, (1, 0.8, 0.65), (75, 0, -40)); od.sky('dusk', 0.7)   # 清晨：暖色低角度阳光
    elif time == 'pm':
        light('light_sun', 'SUN', (0, -10, 10), 4.0, (1, 0.93, 0.8), (50, 0, -60)); od.sky('day', 0.9)
    else:
        od.sky('night', 0.35)
    walkers = {'am': [('extM2', (-20, -0.5), (3, 6.0), 0.5), ('extF3', (2, 6.5), (24, -1.0), 2.0), ('extM1', (-24, -3.5), (24, -3.5), 0.0)],
               'pm': [('extF1', (22, -1.5), (-22, -1.5), 0.0), ('extM3', (-22, -3.0), (22, -3.0), 3.0)],
               'nt': [('extM2', (-22, -2.5), (22, -2.5), 1.0)]}.get(time, [])
    return dict(marks={}, cams={'wide': ((0, -25, 3), (0, 12, 8), 28)}, walkers=walkers)

def ext_campus(kind='library'):
    """校园道路：kind = library（通往图书馆的林荫道）/ canteen（食堂门口）/ dusk（傍晚路灯）/ corridor（教学楼走廊，室内）"""
    col = coll('set_campus_' + kind)
    if kind == 'corridor':
        room('cor_', 3.0, 30, 3.2, col, openings=[('E', y, 0.9, 2.0, 1.8) for y in range(-12, 14, 4)] + [('W', 8, 0, 1.0, 2.1)])
        light('light_sun', 'SUN', (8, 0, 5), 3.5, (1, 0.93, 0.8), (50, 0, 95)); world((0.85, 0.85, 0.9), 0.6)
        return dict(marks={}, cams={'wide': ((0, -13, 1.7), (0, 10, 1.4), 24)})
    import outdoor as od
    rnd = random.Random(sum(map(ord, kind)))   # 固定种子：每次搭出来完全一样
    box('ext_ground', (150, 150, 0.02), (0, 0, -0.02), (0.30, 0.45, 0.22), col)
    box('ext_road', (8, 150, 0.02), (0, 0, -0.01), (0.35, 0.35, 0.36), col)
    for sx in (-1, 1):                                                                                     # 人行道 + 路缘石
        box('ext_sidewalk', (2.4, 150, 0.03), (sx * 5.2, 0, -0.01), (0.62, 0.60, 0.56), col); od.curb((sx * 4.0, -75), (sx * 4.0, 75), col)
    for y in range(-30, 60, 7):                                                                            # 林荫道：两侧行道树（每棵不一样）
        for x in (-7, 7):
            od.tree((x + rnd.uniform(-0.3, 0.3), y + rnd.uniform(-1, 1), 0), rnd, col, 'summer', rnd.uniform(0.95, 1.25))
    for y in range(-26, 60, 14):
        od.lamppost((6.6, y, 0), col, rot=math.pi, night=(kind == 'dusk')); od.lamppost((-6.6, y + 7, 0), col, rot=0.0, night=(kind == 'dusk'))
        od.bench((-8.4, y + 3, 0), col, rot=math.radians(-90)); od.trash_bin((-8.2, y + 4.7), col)
    od.scatter_trees(col, rnd, 30, (-50, 50), (-30, 60), avoid=[(-10, 10, -80, 80)])
    od.sign((8.5, -6), col, rot=math.radians(90))
    if kind == 'library':
        od.building('ext_library', (36, 20, 20), (0, 70, 0), col, rnd, (0.82, 0.80, 0.76))
        od.building('ext_teach', (26, 14, 16), (-32, 40, 0), col, rnd, (0.78, 0.74, 0.70))
        light('light_sun', 'SUN', (0, -10, 10), 4.0, (1, 0.95, 0.85), (50, 0, -30)); od.sky('day', 0.9)
        walkers = [('extF1', (5.0, 30), (5.0, -14), 0.0), ('extM1', (-5.2, -14), (-5.2, 30), 1.0), ('extF2', (5.6, 40), (5.6, -10), 4.0)]
    elif kind == 'canteen':
        od.building('ext_canteenbldg', (30, 16, 9), (0, 30, 0), col, rnd, (0.85, 0.82, 0.75), floors=2)
        od.bike_rack((-14, 20.5), 18, col, rnd, rot=math.radians(90), step=0.8)
        od.flowerbed((9, 20), (4, 1.6), col, rnd)
        light('light_sun', 'SUN', (0, -10, 10), 4.5, (1, 0.96, 0.9), (30, 0, -30)); od.sky('day', 0.9)
        walkers = [('extM2', (-5.0, 0), (-1.0, 21.5), 0.0), ('extF3', (2.0, 21.5), (5.2, -12), 1.5), ('extM3', (5.4, -14), (1.5, 21.5), 3.0),
                   ('extF1', (-5.6, 20), (-5.6, -14), 5.0)]
    else:   # dusk
        od.building('ext_teach', (26, 14, 16), (-28, 45, 0), col, rnd, (0.72, 0.66, 0.62), lit=0.4)
        od.building('ext_dormb', (30, 12, 20), (26, 55, 0), col, rnd, (0.76, 0.70, 0.64), lit=0.5)
        light('light_sun', 'SUN', (0, 30, 3), 1.2, (1.0, 0.5, 0.35), (85, 0, 180)); od.sky('dusk', 0.6)
        walkers = [('extF2', (5.0, 35), (5.0, -14), 0.0), ('extM1', (-5.2, -14), (-5.2, 35), 2.5)]
    return dict(marks={}, cams={'wide': ((0, -15, 1.8), (0, 30, 3), 28)}, walkers=walkers)

BUILDERS = {
    'dorm_am': lambda: dorm('am'), 'dorm_pm': lambda: dorm('pm'), 'dorm_dusk': lambda: dorm('dusk'), 'dorm_nt': lambda: dorm('nt'),
    'lib': lib, 'libdoor': libdoor, 'canteen': canteen, 'track': track, 'class': classroom,
    'home': lambda: home('pm'), 'home_nt': lambda: home('nt'), 'lawn': lawn,
    'ext_dorm_am': lambda: ext_dorm('am'), 'ext_dorm_pm': lambda: ext_dorm('pm'), 'ext_dorm_nt': lambda: ext_dorm('nt'),
    'ext_library': lambda: ext_campus('library'), 'ext_canteen': lambda: ext_campus('canteen'),
    'ext_dusk': lambda: ext_campus('dusk'), 'ext_corridor': lambda: ext_campus('corridor'),
}

def build(name):
    return BUILDERS[name]()
