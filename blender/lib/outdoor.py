# -*- coding: utf-8 -*-
"""外景配件库：让户外场景不再单调——
  天空（渐变 + 云）、不同形状/大小/颜色的树、灌木与绿篱、带窗格和楼层线的教学楼/宿舍楼、路灯、长椅、垃圾桶、
  自行车与车棚、花坛、路缘石、校园指示牌，以及在背景里走动的路人学生（见 shoot.py 的 walkers）。
命名沿用 ext_ 前缀（机位遮挡时可临时移走：ext_trunk / ext_crown / ext_lamp / ext_bike ...）。
"""
import math, random
import bpy
from mathutils import Vector
from sets import box, cyl, sphere, light, mat, C, proto, _place

def _wheel():
    import bmesh
    def build(bm):   # 圆环：24 段 x 6 段截面
        segs, ring, R, r = 24, 6, 0.33, 0.025
        vs = [[bm.verts.new(((R + r * math.cos(b * 2 * math.pi / ring)) * math.cos(a * 2 * math.pi / segs),
                             (R + r * math.cos(b * 2 * math.pi / ring)) * math.sin(a * 2 * math.pi / segs),
                             r * math.sin(b * 2 * math.pi / ring))) for b in range(ring)] for a in range(segs)]
        for a in range(segs):
            for b in range(ring):
                bm.faces.new((vs[a][b], vs[(a + 1) % segs][b], vs[(a + 1) % segs][(b + 1) % ring], vs[a][(b + 1) % ring]))
    return proto('wheel', build)

def _flower():
    import bmesh
    return proto('flower', lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1))

def sky(kind='day', strength=1.0):
    """天空：地平线到天顶的渐变 + 程序云。kind = day / dusk / night"""
    w = bpy.data.worlds.get('v11_world') or bpy.data.worlds.new('v11_world'); w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear(); N = nt.nodes.new; L = nt.links.new
    tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Generated'], sep.inputs[0])
    ramp = N('ShaderNodeValToRGB'); L(sep.outputs['Z'], ramp.inputs['Fac'])
    cols = {'day': ((0.80, 0.86, 0.95), (0.35, 0.55, 0.90)), 'dusk': ((1.0, 0.62, 0.42), (0.30, 0.28, 0.50)),
            'night': ((0.06, 0.08, 0.16), (0.01, 0.015, 0.04))}[kind]
    ramp.color_ramp.elements[0].position = 0.5; ramp.color_ramp.elements[0].color = (*cols[0], 1)
    ramp.color_ramp.elements[1].position = 0.85; ramp.color_ramp.elements[1].color = (*cols[1], 1)
    noise = N('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 3.0; noise.inputs['Detail'].default_value = 6
    L(tc.outputs['Generated'], noise.inputs['Vector'])
    cl = N('ShaderNodeMapRange'); cl.inputs['From Min'].default_value = 0.55; cl.inputs['From Max'].default_value = 0.75
    L(noise.outputs['Fac'], cl.inputs['Value'])
    above = N('ShaderNodeMath'); above.operation = 'GREATER_THAN'; above.inputs[1].default_value = 0.52; L(sep.outputs['Z'], above.inputs[0])
    amt = N('ShaderNodeMath'); amt.operation = 'MULTIPLY'; L(cl.outputs['Result'], amt.inputs[0]); L(above.outputs[0], amt.inputs[1])
    mix = N('ShaderNodeMix'); mix.data_type = 'RGBA'; L(amt.outputs[0], mix.inputs['Factor']); L(ramp.outputs['Color'], mix.inputs[6])
    cloud = {'day': (0.95, 0.95, 0.97), 'dusk': (1.0, 0.75, 0.6), 'night': (0.08, 0.09, 0.14)}[kind]
    mix.inputs[7].default_value = (*cloud, 1)
    bg = N('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength; L(mix.outputs[2], bg.inputs['Color'])
    out = N('ShaderNodeOutputWorld'); L(bg.outputs[0], out.inputs['Surface'])
    bpy.context.scene.world = w

SEASON = {'summer': [(0.18, 0.40, 0.13), (0.24, 0.46, 0.16), (0.14, 0.33, 0.12), (0.28, 0.48, 0.20)],
          'autumn': [(0.62, 0.45, 0.14), (0.55, 0.36, 0.12), (0.30, 0.42, 0.16), (0.70, 0.55, 0.20)]}

def tree(loc, rnd, col, season='summer', scale=1.0):
    """一棵树：粗细不同的树干 + 3~6 团大小不一的叶簇，颜色和高度都有变化"""
    h = rnd.uniform(2.6, 4.2) * scale; r = rnd.uniform(0.14, 0.24) * scale
    cyl('ext_trunk', r, h, loc, (0.28 + rnd.uniform(-0.04, 0.04), 0.20, 0.14), col, verts=10)
    color = rnd.choice(SEASON[season])
    for k in range(rnd.randint(2, 4)):
        off = Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(-0.4, 0.9))) * scale
        sphere('ext_crown', rnd.uniform(1.2, 2.1) * scale, (loc[0] + off.x, loc[1] + off.y, loc[2] + h + 0.8 * scale + off.z),
               tuple(min(1, c * rnd.uniform(0.85, 1.15)) for c in color), col, scale=(1, 1, rnd.uniform(0.75, 1.0)))

def bush(loc, rnd, col, r=0.6):
    sphere('ext_crown_bush', r * rnd.uniform(0.8, 1.2), (loc[0], loc[1], loc[2] + r * 0.55), (0.16, 0.34, 0.12), col, scale=(1.3, 1, 0.7))

def hedge(p0, p1, col, h=0.8, w=0.6):
    d = Vector(p1) - Vector(p0); c = (Vector(p0) + Vector(p1)) / 2
    box('ext_hedge', (d.length, w, h), (c.x, c.y, 0), (0.15, 0.32, 0.12), col, rot_z=math.atan2(d.y, d.x))

def lamppost(loc, col, rot=0.0, night=False, h=4.5):
    cyl('ext_lamppost', 0.06, h, loc, (0.25, 0.26, 0.28), col, verts=10)
    ax, ay = math.cos(rot) * 0.5, math.sin(rot) * 0.5
    box('ext_lamparm', (0.9, 0.06, 0.06), (loc[0] + ax, loc[1] + ay, h - 0.05), (0.25, 0.26, 0.28), col, rot_z=rot)
    box('ext_lamphead', (0.45, 0.22, 0.10), (loc[0] + ax * 1.8, loc[1] + ay * 1.8, h - 0.14), (1.0, 0.85, 0.6) if night else (0.85, 0.85, 0.82), col,
        rot_z=rot, emit=8.0 if night else 0.0)
    if night:
        l = light('light_lamp', 'SPOT', (loc[0] + ax * 1.8, loc[1] + ay * 1.8, h - 0.2), 900, (1.0, 0.78, 0.5), (0, 0, 0), 0.25, col)
        l.data.spot_size = math.radians(120)

def bench(loc, col, rot=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    def P(dx, dy): return (loc[0] + dx * ca - dy * sa, loc[1] + dx * sa + dy * ca)
    for k in range(3):   # 座面木条
        x, y = P(0, -0.12 + k * 0.12); box('ext_bench_seat', (1.6, 0.09, 0.04), (x, y, 0.43), 'wood', col, rot_z=rot)
    for k in range(2):   # 靠背木条
        x, y = P(0, 0.22); box('ext_bench_back', (1.6, 0.04, 0.09), (x, y, 0.58 + k * 0.14), 'wood', col, rot_z=rot)
    for dx in (-0.7, 0.7):
        x, y = P(dx, 0.02); box('ext_bench_leg', (0.06, 0.45, 0.43), (x, y, 0), (0.15, 0.15, 0.16), col, rot_z=rot)

def trash_bin(loc, col):
    cyl('ext_bin', 0.22, 0.85, (loc[0], loc[1], 0), (0.20, 0.38, 0.30), col, verts=14)
    cyl('ext_binlid', 0.24, 0.06, (loc[0], loc[1], 0.85), (0.15, 0.15, 0.16), col, verts=14)

def bike(loc, col, rot=0.0, color=(0.15, 0.25, 0.45)):
    ca, sa = math.cos(rot), math.sin(rot)
    for d in (-0.52, 0.52):   # 两个车轮（共享一个圆环网格）
        _place('ext_bike_wheel', _wheel(), (loc[0] + d * ca, loc[1] + d * sa, 0.35), (1, 1, 1), (math.radians(90), 0, rot), (0.05, 0.05, 0.05), col)
    box('ext_bike_frame', (1.0, 0.04, 0.04), (loc[0], loc[1], 0.62), color, col, rot_z=rot)
    box('ext_bike_down', (0.55, 0.04, 0.04), (loc[0] + 0.05 * ca, loc[1] + 0.05 * sa, 0.45), color, col, rot_z=rot)
    box('ext_bike_seat', (0.24, 0.10, 0.05), (loc[0] - 0.25 * ca, loc[1] - 0.25 * sa, 0.86), (0.05, 0.05, 0.05), col, rot_z=rot)
    box('ext_bike_bar', (0.06, 0.55, 0.04), (loc[0] + 0.45 * ca, loc[1] + 0.45 * sa, 0.95), (0.3, 0.3, 0.32), col, rot_z=rot)

def bike_rack(start, n, col, rnd, rot=0.0, step=0.75):
    """一排停放的自行车（颜色各异，个别歪着）"""
    palette = [(0.15, 0.25, 0.45), (0.55, 0.12, 0.10), (0.85, 0.85, 0.82), (0.1, 0.1, 0.1), (0.25, 0.45, 0.30), (0.75, 0.55, 0.15)]
    for i in range(n):
        if rnd.random() < 0.15: continue
        bike((start[0] + i * step * math.sin(rot), start[1] - i * step * math.cos(rot)), col, rot + rnd.uniform(-0.12, 0.12), rnd.choice(palette))

def flowerbed(center, size, col, rnd):
    box('ext_flowerbed', (size[0], size[1], 0.35), (center[0], center[1], 0), 'stone', col)
    box('ext_soil', (size[0] - 0.1, size[1] - 0.1, 0.02), (center[0], center[1], 0.35), (0.25, 0.18, 0.12), col)
    for k in range(int(size[0] * size[1] * 6)):
        c = rnd.choice([(0.85, 0.2, 0.25), (0.95, 0.75, 0.2), (0.9, 0.9, 0.85), (0.7, 0.3, 0.7), (0.2, 0.45, 0.15)])
        s = rnd.uniform(0.05, 0.1)
        _place('ext_flower', _flower(), (center[0] + rnd.uniform(-0.45, 0.45) * size[0], center[1] + rnd.uniform(-0.45, 0.45) * size[1], 0.42),
               (s, s, s), (0, 0, 0), c, col)

def curb(p0, p1, col):
    d = Vector(p1) - Vector(p0); c = (Vector(p0) + Vector(p1)) / 2
    box('ext_curb', (d.length, 0.15, 0.12), (c.x, c.y, 0), (0.70, 0.70, 0.68), col, rot_z=math.atan2(d.y, d.x))

def sign(loc, col, rot=0.0):
    """校园指示牌（文字后期贴）"""
    for dx in (-0.55, 0.55):
        box('ext_signpost', (0.06, 0.06, 1.9), (loc[0] + dx * math.cos(rot), loc[1] + dx * math.sin(rot), 0), (0.3, 0.3, 0.32), col, rot_z=rot)
    box('prop_signboard', (1.3, 0.05, 0.7), (loc[0], loc[1], 1.2), (0.12, 0.30, 0.55), col, rot_z=rot)

def building(name, size, loc, col, rnd, color=(0.82, 0.78, 0.70), floors=None, lit=0.0, face='-Y', win=(0.28, 0.33, 0.38)):
    """楼：主体 + 正立面窗格（窗框/玻璃，夜晚部分亮灯）+ 每层楼层线 + 女儿墙 + 入口雨棚。
    size=(宽,深,高)；loc=(中心x, 中心y, 底z)；face：正立面朝向（-Y 朝镜头）"""
    W, D, H = size
    box(name, size, loc, color, col)
    floors = floors or max(2, int(H / 3.2))
    fh = H / floors; nwin = max(3, int(W / 3.0))
    fy = loc[1] - D / 2 - 0.02 if face == '-Y' else loc[1] + D / 2 + 0.02
    for fl in range(floors):
        box(name + '_band', (W + 0.1, 0.12, 0.18), (loc[0], fy, loc[2] + fl * fh), (min(1, color[0] * 1.08), min(1, color[1] * 1.08), min(1, color[2] * 1.06)), col)
        if fl == 0: continue
        for k in range(nwin):
            x = loc[0] - W / 2 + (k + 0.5) * W / nwin
            on = rnd.random() < lit
            box(name + '_window', (W / nwin * 0.55, 0.06, fh * 0.48), (x, fy, loc[2] + fl * fh + fh * 0.3),
                (1.0, 0.82, 0.55) if on else win, col, emit=5.0 if on else 0.0)
    box(name + '_parapet', (W + 0.3, D + 0.3, 0.6), (loc[0], loc[1], loc[2] + H), (color[0] * 0.9, color[1] * 0.9, color[2] * 0.9), col)
    box(name + '_canopy', (min(6, W * 0.25), 2.0, 0.2), (loc[0], fy - 1.0 if face == '-Y' else fy + 1.0, loc[2] + 3.2), (0.5, 0.5, 0.52), col)
    box(name + '_door', (min(3.2, W * 0.12), 0.08, 2.6), (loc[0], fy - 0.01 if face == '-Y' else fy + 0.01, loc[2]), (0.25, 0.32, 0.38), col)

def scatter_trees(col, rnd, n, xr, yr, avoid=(), season='summer', scale=(0.9, 1.2)):
    """在区域里撒树，避开道路/表演区（avoid：[(x0,x1,y0,y1), ...]）"""
    k = 0
    while k < n:
        x, y = rnd.uniform(*xr), rnd.uniform(*yr)
        if any(a[0] <= x <= a[1] and a[2] <= y <= a[3] for a in avoid): continue
        tree((x, y, 0), rnd, col, season, rnd.uniform(*scale)); k += 1
