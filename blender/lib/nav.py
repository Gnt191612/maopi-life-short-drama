# -*- coding: utf-8 -*-
"""走路寻路：把场景里挡路的家具/墙投影到 10 cm 地面网格上（按人体半径加宽），A* 找绕开家具的路线，
再按「能直接看到」原则拉直成少数几个拐点。人物不再直线穿过床柱、水池、桌子。"""
import math, heapq
import bpy
from mathutils import Vector

CELL = 0.10
BODY_R = 0.24            # 人体半径（含手臂摆动）

def _is_obstacle(o):
    if o.type != 'MESH' or o.hide_render: return False
    if o.parent is not None and o.parent.type == 'ARMATURE': return False
    if o.name.startswith(('prop_', 'cam_', 'furn_quilt', 'furn_pillow', 'furn_mattress', 'ext_lane', 'ext_track', 'ext_path', 'ext_road')): return False
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    zlo, zhi = min(c.z for c in bb), max(c.z for c in bb)
    return zhi > 0.12 and zlo < 1.6 and (max(c.x for c in bb) - min(c.x for c in bb)) < 40 and (max(c.y for c in bb) - min(c.y for c in bb)) < 40

class Grid:
    def __init__(self, p0, p1, margin=4.0):
        lo = Vector((min(p0[0], p1[0]) - margin, min(p0[1], p1[1]) - margin)); hi = Vector((max(p0[0], p1[0]) + margin, max(p0[1], p1[1]) + margin))
        self.lo = lo; self.nx = int((hi.x - lo.x) / CELL) + 1; self.ny = int((hi.y - lo.y) / CELL) + 1
        self.block = bytearray(self.nx * self.ny)
        r = int(math.ceil(BODY_R / CELL))
        for o in bpy.context.scene.objects:
            if not _is_obstacle(o): continue
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            x0, x1 = min(c.x for c in bb), max(c.x for c in bb); y0, y1 = min(c.y for c in bb), max(c.y for c in bb)
            inv = o.matrix_world.inverted()
            blo = Vector([min(c[i] for c in o.bound_box) for i in range(3)]); bhi = Vector([max(c[i] for c in o.bound_box) for i in range(3)])
            zmid = (blo.z + bhi.z) / 2
            i0, i1 = self.ix(x0 - BODY_R), self.ix(x1 + BODY_R); j0, j1 = self.iy(y0 - BODY_R), self.iy(y1 + BODY_R)
            sx = o.matrix_world.to_scale()
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                for j in range(max(0, j0), min(self.ny, j1 + 1)):
                    q = inv @ Vector((self.lo.x + i * CELL, self.lo.y + j * CELL, 0))
                    q.z = zmid                                       # 只按水平投影判断
                    dx = max(blo.x - q.x, 0, q.x - bhi.x) * sx.x; dy = max(blo.y - q.y, 0, q.y - bhi.y) * sx.y
                    if math.hypot(dx, dy) < BODY_R: self.block[i * self.ny + j] = 1
        self.r = r

    def ix(self, x): return int(round((x - self.lo.x) / CELL))
    def iy(self, y): return int(round((y - self.lo.y) / CELL))
    def pos(self, c): return (self.lo.x + c[0] * CELL, self.lo.y + c[1] * CELL)
    def free(self, c): return 0 <= c[0] < self.nx and 0 <= c[1] < self.ny and not self.block[c[0] * self.ny + c[1]]

    def clear_around(self, c, rad=4):
        """起点/终点往往紧挨家具（坐在桌前、站在水池边）：把附近格子放开，让人能走出去"""
        for i in range(c[0] - rad, c[0] + rad + 1):
            for j in range(c[1] - rad, c[1] + rad + 1):
                if 0 <= i < self.nx and 0 <= j < self.ny and math.hypot(i - c[0], j - c[1]) <= rad: self.block[i * self.ny + j] = 0

    def los(self, a, b):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 1
        for k in range(n + 1):
            t = k / n; c = (int(round(a[0] + (b[0] - a[0]) * t)), int(round(a[1] + (b[1] - a[1]) * t)))
            if not self.free(c): return False
        return True

def plan(p0, p1):
    """返回从 p0 到 p1 的拐点列表 [(x,y), ...]（含首尾）；找不到路就走直线"""
    g = Grid(p0, p1)
    s, e = (g.ix(p0[0]), g.iy(p0[1])), (g.ix(p1[0]), g.iy(p1[1]))
    g.clear_around(s); g.clear_around(e)
    if g.los(s, e): return [tuple(p0[:2]), tuple(p1[:2])]
    openq = [(0, s)]; came = {s: None}; cost = {s: 0}
    while openq:
        _, c = heapq.heappop(openq)
        if c == e: break
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not di and not dj: continue
                nb = (c[0] + di, c[1] + dj)
                if not g.free(nb): continue
                nc = cost[c] + (1.414 if di and dj else 1.0)
                if nc < cost.get(nb, 1e9):
                    cost[nb] = nc; came[nb] = c
                    heapq.heappush(openq, (nc + math.hypot(e[0] - nb[0], e[1] - nb[1]), nb))
    if e not in came: return [tuple(p0[:2]), tuple(p1[:2])]
    path = [e]
    while came[path[-1]] is not None: path.append(came[path[-1]])
    path.reverse()
    pts = [path[0]]; k = 0                                           # 拉直：从当前点尽量直接看到更远的点
    while k < len(path) - 1:
        j = len(path) - 1
        while j > k + 1 and not g.los(path[k], path[j]): j -= 1
        pts.append(path[j]); k = j
    out = [tuple(p0[:2])] + [g.pos(c) for c in pts[1:-1]] + [tuple(p1[:2])]
    return out
