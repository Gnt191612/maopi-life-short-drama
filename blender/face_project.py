# -*- coding: utf-8 -*-
"""把用户选定的标准长相照片投影成角色的脸部贴图（让白模的脸就是「这个人」）。
1) 白模上取 6 个关键点（两眼中心、鼻尖、两嘴角、下巴），在正面正交镜头里投影成像素坐标；
2) 照片上的同名关键点（assets/identity/<cid>_landmarks.json，人工标注）→ 薄板样条变形，把照片对齐到镜头画面；
3) 从镜头把对齐后的照片投影到脸上，按「朝向镜头的程度 × 脸部范围 × 避开眼球」做遮罩，与原皮肤颜色混合，烘焙成新的皮肤贴图；
   原 3D 眉毛删掉（照片里有眉毛）。结果直接存回角色 .blend。
blender -b assets/cast_next/<cid>.blend -P blender/face_project.py -- <cid>"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import bpy, numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

RES = 2048   # 投影画面（变形后照片）分辨率：照片里脸约 440 像素宽，画面里脸约占一半宽
IDDIR = os.path.join(config.ROOT, 'assets', 'identity')
KEYS = ('eye_R', 'eye_L', 'nose', 'mouth_R', 'mouth_L', 'chin')

def fit_info(cid):
    p = os.path.join(IDDIR, cid + '_face_fit.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None

def photo_landmarks(cid):
    """完整标注（<cid>_landmarks_full.json）展开成 {名字: [x, y]}，轮廓点按 contour_R_0… 命名，与脸型拟合一致"""
    lm = json.load(open(os.path.join(IDDIR, cid + '_landmarks_full.json'), encoding='utf-8')); out = {}
    for k, v in lm.items():
        if k.startswith('_') or k in ('eye_R', 'eye_L'): continue
        if k.startswith('contour'):
            for i, (y, x) in enumerate(v): out['%s_%d' % (k, i)] = [x, y]
        else: out[k] = v
    return out

def landmarks_fit(rig, body, fit):
    """按脸型拟合给出的顶点序号取关键点（求值时关掉遮罩修改器，顶点序号才与基础网格一致）"""
    masks = [m for m in body.modifiers if m.type == 'MASK' and m.show_viewport]
    for m in masks: m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); M = body.matrix_world
    pts = {k: M @ me.vertices[i].co for k, i in fit['landmark_verts'].items()}
    ev.to_mesh_clear()
    for m in masks: m.show_viewport = True
    pb = rig.pose.bones; MW = rig.matrix_world
    eL, eR = MW @ pb['eye.L'].head, MW @ pb['eye.R'].head
    return pts, (eL + eR) / 2, (eL - eR).length

def landmarks3d(rig, body):
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); M = body.matrix_world
    P = [M @ v.co for v in me.vertices]
    pb = rig.pose.bones; MW = rig.matrix_world
    eL, eR = MW @ pb['eye.L'].head, MW @ pb['eye.R'].head
    c = (eL + eR) / 2; iod = (eL - eR).length                                 # 两眼间距：所有尺寸按它换算
    nose = min((p for p in P if abs(p.x - c.x) < iod * 0.12 and c.z - iod * 1.1 < p.z < c.z - iod * 0.2), key=lambda p: p.y)
    li = next(i for i, s in enumerate(body.material_slots) if s.material and 'lips' in s.material.name.lower())
    lv = {i for poly in me.polygons if poly.material_index == li for i in poly.vertices}
    LP = [P[i] for i in lv]
    mR, mL = min(LP, key=lambda p: p.x), max(LP, key=lambda p: p.x)           # 角色右侧 = -X
    mz = sum(p.z for p in LP) / len(LP); my = min(p.y for p in LP)
    chin = min((p for p in P if abs(p.x - c.x) < iod * 0.1 and mz - iod * 2.0 < p.z < mz - iod * 0.3 and p.y < my + iod * 0.6), key=lambda p: p.z)
    ev.to_mesh_clear()
    return dict(eye_R=eR, eye_L=eL, nose=nose, mouth_R=mR, mouth_L=mL, chin=chin), c, iod

def view_dir(yaw_deg=0.0, pitch_deg=0.0):
    """照片视角：脸型拟合里模型先绕 Z 转 yaw、再绕 X 转 pitch 后从正面（朝 +Y）看；换成世界坐标里的视线方向与画面上方向"""
    from mathutils import Matrix
    R = Matrix.Rotation(math.radians(pitch_deg), 3, 'X') @ Matrix.Rotation(math.radians(yaw_deg), 3, 'Z')
    Rt = R.transposed(); return Rt @ Vector((0, 1, 0)), Rt @ Vector((0, 0, 1))

def make_camera(c, iod, yaw_deg=0.0, pitch_deg=0.0):
    cam = bpy.data.objects.new('v11_projcam', bpy.data.cameras.new('v11_projcam')); bpy.context.scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = iod * 4.4
    d, up = view_dir(yaw_deg, pitch_deg)
    from mathutils import Matrix
    Z = -d; X = up.cross(Z).normalized(); Y = Z.cross(X)               # 镜头本地 -Z = 视线，Y = 画面上方
    cam.rotation_euler = Matrix((X, Y, Z)).transposed().to_euler()
    cam.location = c - d * 1.0 - up * iod * 0.7
    sc = bpy.context.scene; sc.camera = cam; sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1
    bpy.context.view_layer.update()
    return cam

def to_px(cam, p):
    u, v, _ = world_to_camera_view(bpy.context.scene, cam, p); return (u * RES, (1 - v) * RES)

def tps_warp(photo, src, dst):
    """输出画面像素 x → 照片像素 f(x)：以画面关键点 src 为控制点、照片关键点 dst 为目标的薄板样条（外加四角的仿射锚点稳住边缘）"""
    src = np.asarray(src, float); dst = np.asarray(dst, float)
    A = np.c_[src, np.ones(len(src))]; aff = np.linalg.lstsq(A, dst, rcond=None)[0]
    corners = np.array([[0, 0], [RES, 0], [0, RES], [RES, RES]], float)
    S = np.r_[src, corners]; D = np.r_[dst, np.c_[corners, np.ones(4)] @ aff]
    U = lambda r: np.where(r > 0, r * r * np.log(np.maximum(r, 1e-9)), 0.0)
    n = len(S); K = U(np.linalg.norm(S[:, None] - S[None], axis=2)) + np.eye(n) * 1e-3 * RES
    Pm = np.c_[np.ones(n), S]; L = np.zeros((n + 3, n + 3)); L[:n, :n] = K; L[:n, n:] = Pm; L[n:, :n] = Pm.T
    sol = np.linalg.solve(L, np.r_[D, np.zeros((3, 2))]); w, a = sol[:n], sol[n:]
    yy, xx = np.mgrid[0:RES, 0:RES].astype(float); G = np.c_[xx.ravel(), yy.ravel()]
    F = np.empty_like(G)
    for i in range(0, len(G), 1 << 18):   # 分块算，2048² 一次算要好几 GB 内存
        g = G[i:i + (1 << 18)]; F[i:i + len(g)] = np.c_[np.ones(len(g)), g] @ a + U(np.linalg.norm(g[:, None] - S[None], axis=2)) @ w
    h, wd = photo.shape[:2]; fx, fy = F[:, 0], F[:, 1]
    inside = (fx >= 0) & (fx < wd - 1) & (fy >= 0) & (fy < h - 1)
    x0 = np.clip(fx.astype(int), 0, wd - 2); y0 = np.clip(fy.astype(int), 0, h - 2); tx = (fx - x0)[:, None]; ty = (fy - y0)[:, None]
    c = (photo[y0, x0] * (1 - tx) * (1 - ty) + photo[y0, x0 + 1] * tx * (1 - ty) + photo[y0 + 1, x0] * (1 - tx) * ty + photo[y0 + 1, x0 + 1] * tx * ty)
    out = np.zeros((RES * RES, 4), np.float32); out[:, :3] = c[:, :3]; out[:, 3] = inside * (c[:, 3] if c.shape[1] > 3 else 1.0)   # 照片自带的透明度（发际线以上置 0）一起带过来
    return out.reshape(RES, RES, 4)

def load_rgba(path):
    img = bpy.data.images.load(path); w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)[::-1].copy(); bpy.data.images.remove(img); return a   # Blender 像素自下而上：翻成自上而下

def save_rgba(arr, path, name):
    h, w = arr.shape[:2]; img = bpy.data.images.new(name, w, h, alpha=True); img.pixels.foreach_set(arr[::-1].ravel())
    img.filepath_raw = path; img.file_format = 'PNG'; img.save(); return img

def skin_gain(warped, src, gt):
    """照片脸颊的平均肤色（线性）÷ 模型原皮肤平均色（漫反射贴图 × 调色），按通道，限制在 0.6~1.6"""
    eR, eL, nose = np.array(src[0]), np.array(src[1]), np.array(src[2])
    pts = []
    for e in (eR, eL):   # 脸颊：眼睛和鼻尖连线中点再往外下一点
        cpt = (e + nose) / 2 + (e - nose) * np.array([0.35, -0.6]); x, y = int(cpt[0]), int(cpt[1])
        pts.append(warped[max(0, y - 12):y + 12, max(0, x - 12):x + 12, :3].reshape(-1, 3))
    photo = (np.concatenate(pts) * 0.82) ** 2.2
    photo = photo.mean(0)
    diff = next(n for n in gt.nodes if n.type == 'TEX_IMAGE' and n.name == 'DiffuseTexture').image
    w, h = diff.size; px = np.empty(w * h * 4, np.float32); diff.pixels.foreach_get(px); px = px.reshape(-1, 4)[::53, :3]
    px = px[px.mean(1) > 0.15]
    tint = next((n.inputs[7].default_value[:3] for n in gt.nodes if n.type == 'MIX' and n.blend_type == 'MULTIPLY'), (1, 1, 1))
    model = (px ** 2.2).mean(0) * np.array(tint)
    # 只对齐亮度、不动色相：漫反射贴图里混着嘴唇指甲等，按通道算会把蓝色放大（实测增益 0.8/1.1/1.6，皮肤发冷发白）
    g = float(np.clip(photo.mean() / max(model.mean(), 1e-4), 0.7, 1.4))
    print('SKIN GAIN', round(g, 3), flush=True)
    return (g, g, g)

def _blur(a, w, r):
    """带权重的大半径模糊（三次盒式模糊 ≈ 高斯）：a 为 (H,W) 数值，w 为权重（脸外为 0，不把背景混进来）"""
    def box(x):
        for ax in (0, 1):
            c = np.cumsum(np.pad(x, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode='edge'), axis=ax)
            x = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
        return x
    num, den = a * w, w.astype(np.float64)
    for _ in range(3): num, den = box(num), box(den)
    return num / np.maximum(den, 1e-6)

def photo_tone(warped, pts, gt, iod_px):
    """照片去光照 + 肤色对齐（在线性空间做，返回 sRGB）：
    1) 照片自带影棚光（额头鼻梁亮、两侧暗）→ 除以大范围模糊后的亮度，压平明暗（保留五官细节和局部颜色）；
    2) 亮度对齐模型身体的皮肤（脸和脖子耳朵接得上），色相往身体肤色靠一半"""
    lin = np.where(warped[..., :3] <= 0.04045, warped[..., :3] / 12.92, ((warped[..., :3] + 0.055) / 1.055) ** 2.4)
    L = lin @ np.array([0.2126, 0.7152, 0.0722])
    eyeR, eyeL, nose, chin = (np.array(pts[k]) for k in ('eye_R_out', 'eye_L_out', 'nose', 'chin'))
    yy, xx = np.mgrid[0:RES, 0:RES]
    cx = (eyeR[0] + eyeL[0]) / 2; rx = abs(eyeL[0] - eyeR[0]) * 0.62; cy = (eyeR[1] + chin[1]) / 2; ry = abs(chin[1] - eyeR[1]) * 0.75
    face = ((((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) < 1) & (warped[..., 3] > 0.5)
    # 模糊半径要比眉毛、眼睛大得多（只去掉整体的明暗走向），否则深色的眉眼会被当成阴影提亮
    Lb = _blur(L, face, max(4, int(iod_px * 0.9)))
    ref = float(np.median(L[face]))
    flat = lin * np.clip((ref / np.maximum(Lb, 1e-4)) ** 0.6, 0.7, 1.5)[..., None]
    # 模型皮肤平均色：漫反射贴图里像皮肤的像素（R>G>B、够亮）× 调色
    diff = next(n for n in gt.nodes if n.type == 'TEX_IMAGE' and n.name == 'DiffuseTexture').image
    w, h = diff.size; px = np.empty(w * h * 4, np.float32); diff.pixels.foreach_get(px); px = px.reshape(-1, 4)[::37, :3]
    px = px[(px[:, 0] > px[:, 1]) & (px[:, 1] > px[:, 2]) & (px.mean(1) > 0.25)]
    tint = next((n.inputs[7].default_value[:3] for n in gt.nodes if n.type == 'MIX' and n.blend_type == 'MULTIPLY'), (1, 1, 1))
    model = (px ** 2.2).mean(0) * np.array(tint)            # 贴图是 sRGB：换算成线性
    cheek = flat[face & (np.abs(yy - (nose[1] + eyeR[1]) / 2) < iod_px * 0.15)].reshape(-1, 3).mean(0)
    g_l = float(np.clip(model.mean() / max(cheek.mean(), 1e-4), 0.5, 1.6))
    g_c = np.clip(model / np.maximum(cheek, 1e-4), 0.5, 1.8)
    gain = g_l * (g_c / g_l) ** 0.85   # 色相基本跟身体走：脸和脖子、耳朵不留色差（长相靠五官，不靠照片的肤色）
    print('PHOTO TONE ref %.3f gain %s' % (ref, np.round(gain, 3)), flush=True)
    out = np.clip(flat * gain, 0, 1)
    # 眉毛单独处理（用户：眉形要修）：去光照会把深色的眉毛当阴影提亮，眉毛发灰、眉尾淡没了。
    # 在两眼上方的眉毛带里，按「比周围皮肤暗多少」找出眉毛像素，这些像素用照片原色（只做整体亮度对齐、不压平、略加深）
    pts_ = {k: np.array(v, float) for k, v in pts.items()}
    region = np.zeros(L.shape, bool)
    for s_ in ('R', 'L'):
        o, i_, tp = pts_['eye_%s_out' % s_], pts_['eye_%s_in' % s_], pts_['eye_%s_top' % s_]
        x0, x1 = sorted((i_[0] + (i_[0] - o[0]) * 0.25, o[0] + (o[0] - i_[0]) * 0.65))
        region |= (xx > x0) & (xx < x1) & (yy < tp[1] - iod_px * 0.10) & (yy > tp[1] - iod_px * 0.95)
    skin = face & (L > Lb * 0.85)
    Ls = _blur(L, skin | (~face & (warped[..., 3] > 0.5)), max(3, int(iod_px * 0.25)))   # 周围皮肤亮度（不含眉毛本身）
    region = _blur(region.astype(float), np.ones(L.shape), max(2, int(iod_px * 0.12)))   # 眉毛带边缘羽化（方框边会把眉头眉尾截成直角）
    dark = np.clip((0.93 - L / np.maximum(Ls, 1e-4)) / 0.22, 0, 1) * region   # 阈值放宽：眉尾颜色淡，原来识别不出来被压平
    dark = _blur(dark, np.ones_like(dark), 1)
    brow = np.clip(lin * g_l * 0.55 * np.array([1.0, 0.92, 0.85]), 0, 1)   # 略加深、偏中性深棕（灰蓝来自皮肤反光，已在材质里按颜色深浅压掉）
    out = out * (1 - dark[..., None]) + brow * dark[..., None]
    print('BROW px', int((dark > 0.5).sum()), flush=True)
    srgb = np.where(out <= 0.0031308, out * 12.92, 1.055 * out ** (1 / 2.4) - 0.055)
    res = warped.copy(); res[..., :3] = srgb; return res

def face_region(pts, iod_px):
    """照片贴图的有效范围（渲染画面像素）：两侧沿脸部外轮廓点、往上经过眼尾外侧到额头，内缩一点再羽化——
    轮廓外的背景、太阳穴处的头发不贴到模型上"""
    P = lambda k: np.array(pts[k], float)
    up = np.array([0, -1.0]) * iod_px
    eRo, eLo, eRi, eLi = P('eye_R_out'), P('eye_L_out'), P('eye_R_in'), P('eye_L_in')
    tR = eRo + (eRo - eRi) * 0.55 + up * 0.48; tL = eLo + (eLo - eLi) * 0.55 + up * 0.48   # 眉尾在眼尾外上方：框小了会把眉尾切掉
    top = (eRo + eLo) / 2 + up * 1.25
    poly = [tR] + [P('contour_R_%d' % i) for i in range(5)] + [P('chin')] + [P('contour_L_%d' % i) for i in range(4, -1, -1)] + [tL, top]
    poly = np.array(poly); cen = poly.mean(0); poly = cen + (poly - cen) * 0.97
    yy, xx = np.mgrid[0:RES, 0:RES].astype(float); inside = np.zeros((RES, RES), bool)
    for (x1, y1), (x2, y2) in zip(poly, np.roll(poly, -1, 0)):   # 射线法判断点在多边形内
        cond = (y1 > yy) != (y2 > yy)
        xin = x1 + (yy - y1) * (x2 - x1) / np.where(y2 - y1 == 0, 1e-9, y2 - y1)
        inside ^= cond & (xx < xin)
    return np.clip(_blur(inside.astype(float), np.ones((RES, RES)), max(3, int(iod_px * 0.06))), 0, 1)

def project(cid):
    rig = bpy.data.objects[cid + '_rig']; body = bpy.data.objects[cid + '_body']
    fit = fit_info(cid)
    if fit is not None:   # 脸型拟合过：用完整关键点 + 照片的实际视角
        lm3, c, iod = landmarks_fit(rig, body, fit); yaw, pitch = fit['yaw_deg'], fit['pitch_deg']
        dstd = photo_landmarks(cid); keys = [k for k in lm3 if k in dstd]
    else:
        lm3, c, iod = landmarks3d(rig, body); yaw = pitch = 0.0
        dstd = json.load(open(os.path.join(IDDIR, cid + '_landmarks.json'), encoding='utf-8')); keys = list(KEYS)
    cam = make_camera(c, iod, yaw, pitch); vdir, _ = view_dir(yaw, pitch)
    src = [to_px(cam, lm3[k]) for k in keys]; dst = [dstd[k] for k in keys]
    srcd_all = dict(zip(keys, src))   # 剔除前的全部点（唇色取样等要用）
    if fit is not None:   # 去掉对应关系明显不一致的点（模型上取错顶点时，薄板样条会把照片局部拧成一团，嘴上方出现色块）
        S_, D_ = np.array(src, float), np.array(dst, float)
        aff_ = np.linalg.lstsq(np.c_[S_, np.ones(len(S_))], D_, rcond=None)[0]
        res_ = np.linalg.norm(np.c_[S_, np.ones(len(S_))] @ aff_ - D_, axis=1)
        sc_ = np.linalg.norm(np.array(dstd['eye_L_out'], float) - np.array(dstd['eye_R_out'], float))
        # 相邻点之间顺序颠倒也会折叠：同一竖线上的 鼻尖-鼻底-上唇-下唇-下巴 必须保持上下顺序
        order_ = [k for k in ('nose', 'subnasal', 'lip_top', 'lip_bot', 'chin') if k in keys]
        bad = {k for k, r in zip(keys, res_) if r > 0.10 * sc_ and k not in ('ala_R', 'ala_L', 'nose', 'eye_R_in', 'eye_L_in', 'eye_R_out', 'eye_L_out')}   # 鼻翼、眼角不剔除：去掉鼻翼后照片的鼻孔会落到上唇（周明远）
        for a_, b_ in zip(order_, order_[1:]):
            ia, ib = keys.index(a_), keys.index(b_)
            if not (src[ia][1] < src[ib][1]): bad.add(b_)
        if bad:
            print('TPS drop', sorted(bad), flush=True)
            keep_ = [i for i, k in enumerate(keys) if k not in bad]
            keys = [keys[i] for i in keep_]; src = [src[i] for i in keep_]; dst = [dst[i] for i in keep_]
    if fit is not None:   # 眉毛控制点（用户：眉型不还原，眉尾被拉弯往下垂）：照片上自动找出眉毛中线，跟着同侧眼睛做刚性移动加进薄板样条
        src, dst = list(src), list(dst); keys = list(keys)
        ph0 = os.path.join(IDDIR, cid + '_noglasses.png'); ph0 = ph0 if os.path.exists(ph0) else os.path.join(IDDIR, cid + '.png')
        g0 = load_rgba(ph0)[..., :3].mean(2)
        lmj0 = json.load(open(os.path.join(IDDIR, cid + '_landmarks_full.json'), encoding='utf-8'))
        top_ = sorted(lmj0.get('skin_top', lmj0.get('hairline', [])))
        for s_ in ('R', 'L'):
            ko, ki = 'eye_%s_out' % s_, 'eye_%s_in' % s_
            if ko not in keys or ki not in keys: continue
            po, pi = np.array(dstd[ko], float), np.array(dstd[ki], float); ro, ri = np.array(src[keys.index(ko)], float), np.array(src[keys.index(ki)], float)
            w = np.linalg.norm(po - pi); ytop = np.array(dstd['eye_%s_top' % s_], float)[1]
            xa, xb = sorted((pi[0] - (po[0] - pi[0]) * 0.12, po[0] + (po[0] - pi[0]) * 0.30))
            y0, y1 = int(ytop - 1.0 * w), int(ytop - 0.12 * w)
            reg = g0[y0:y1, int(xa):int(xb)]
            if reg.size == 0: continue
            base_ = np.percentile(reg, 80)
            cols = []
            for j in range(reg.shape[1]):
                d = base_ - reg[:, j]; d = np.convolve(d, np.ones(5) / 5, 'same')
                if d.max() > 0.10: cols.append((xa + j, y0 + int(np.argmax(d))))
            if len(cols) < reg.shape[1] * 0.5: print('BROW skip', s_, flush=True); continue
            cols = np.array(cols, float)
            pts_b = []
            for f in (0.08, 0.35, 0.65, 0.92):
                x_ = xa + (xb - xa) * f; near = cols[np.abs(cols[:, 0] - x_) < (xb - xa) * 0.08]
                if len(near) < 3: continue
                y_ = float(np.median(near[:, 1]))
                if top_ and y_ < np.interp(x_, [p[0] for p in top_], [p[1] for p in top_]) + 10: continue   # 被刘海盖住
                pts_b.append(np.array([x_, y_]))
            # 照片 → 画面：用同侧两个眼角定的相似变换（平移 + 旋转 + 缩放）
            dp, dr = pi - po, ri - ro; sc = np.linalg.norm(dr) / max(np.linalg.norm(dp), 1e-6)
            ang = math.atan2(dr[1], dr[0]) - math.atan2(dp[1], dp[0]); Rm2 = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
            for k_, p in enumerate(pts_b):
                src.append(tuple(ro + sc * Rm2 @ (p - po))); dst.append(list(p)); keys.append('brow_%s_%d' % (s_, k_))
            print('BROW pts', s_, len(pts_b), flush=True)
    tmp = os.path.join(config.ROOT, 'build', 'identity'); os.makedirs(tmp, exist_ok=True)
    def photo_masked(path):
        """照片发际线以上（头发、刘海盖住的额头）透明：不把照片里的头发贴到模型额头上（刘海位置和模型不完全一致时会露出一片画上去的头发）"""
        a = load_rgba(path)
        lmj = json.load(open(os.path.join(IDDIR, cid + '_landmarks_full.json'), encoding='utf-8'))
        if 'hairline' in lmj and fit is not None:
            hl_ = sorted(lmj.get('skin_top', lmj['hairline']))   # skin_top：刘海下沿（刘海盖住额头的角色）
            xs_ =np.array([p[0] for p in hl_], float); ys_ = np.array([p[1] for p in hl_], float)
            h_, w_ = a.shape[:2]; yy_ = np.arange(h_)[:, None]; xx_ = np.arange(w_)[None, :]
            yh = np.interp(xx_, xs_, ys_, left=ys_[0], right=ys_[-1])
            a[..., 3] *= np.clip((yy_ - yh) / (70.0 if cid == 'classB' else 130.0), 0, 1)                   # 发际线往下 70 像素渐变（窄了会看到照片肤色和模型肤色的分界线）
            # 发际线两端以外（太阳穴、鬓角的头发是竖着往下的）：端点往下 80 像素以内不贴，往里 90 像素平滑过渡（硬切会留一道竖缝）
            wout = np.clip(np.maximum(xs_[0] + 60 - xx_, xx_ - (xs_[-1] - 60)) / 90.0, 0, 1)
            yend = np.where(xx_ < (xs_[0] + xs_[-1]) / 2, ys_[0], ys_[-1])
            a[..., 3] *= 1 - wout * (1 - np.clip((yy_ - yend - 80) / 40.0, 0, 1))
            # 额头、太阳穴上散落的细发丝（林晓、王老师照片里刘海垂下来的几缕）会烘成皮肤上的黑线：投影前从照片里抹掉。
            # 只处理眉毛以上 + 两侧太阳穴；用黑帽运算找比周围暗的细线，再修补
        if 'hairline' in lmj and fit is not None and cid != 'classB':   # 同学乙已定稿，不动
            eR_, eL_ = np.array(lmj['eye_R'], float), np.array(lmj['eye_L'], float); iod_ = np.linalg.norm(eL_ - eR_); cx_ = (eR_[0] + eL_[0]) / 2
            ey_ = min(eR_[1], eL_[1])
            g_ = a[..., :3].mean(2)
            # 处理范围（平滑权重，硬边界会在眉毛旁留下方形缺口）：眉毛以上 0.40→0.50 眼距渐入；两侧太阳穴 1.0→1.15 眼距以外渐入
            def _sm(e0, e1, x): t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)
            up_ = (ey_ - yy_) / iod_; ax_ = np.abs(xx_ - cx_) / iod_
            wreg = np.maximum(_sm(0.40, 0.50, up_), _sm(1.0, 1.15, ax_) * _sm(0.05, 0.12, up_)) * (yy_ > yh - 40)
            wreg = np.broadcast_to(wreg, g_.shape).astype(np.float32)
            reg_ = wreg > 0.5
            def _flt(x, r, fn):   # 方形最大/最小值滤波（可分离）
                for ax in (0, 1):
                    p = np.pad(x, [(r, r) if k == ax else (0, 0) for k in (0, 1)], mode='edge')
                    x = fn(np.stack([np.take(p, range(i, i + x.shape[ax]), axis=ax) for i in range(2 * r + 1)]), axis=0)
                return x
            def _box(x, r):       # 盒式模糊（积分图，可分离）
                for ax in (0, 1):
                    c = np.cumsum(np.pad(x, [(r + 1, r) if k == ax else (0, 0) for k in range(x.ndim)], mode='edge'), axis=ax)
                    n = x.shape[ax]; x = (np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, range(0, n), axis=ax)) / (2 * r + 1)
                return x
            bh_ = _flt(_flt(g_, 8, np.max), 8, np.min) - g_                # 黑帽：闭运算 − 原图 = 比周围暗的细线
            ck_ = g_[int(ey_ + 0.30 * iod_):int(ey_ + 0.50 * iod_), int(eR_[0] - 0.15 * iod_):int(eR_[0] + 0.15 * iod_)]
            sk_ = float(np.median(ck_)) if ck_.size else float(np.median(g_))
            dk_ = (g_ < 0.70 * sk_) & (wreg > 0.01)                                  # 成片的深色头发（太阳穴垂下来的发束）：柔和透明，露出模型自己的皮肤
            dkw = np.clip(_box(_box(dk_.astype(np.float32), 10), 10) * 2.0, 0, 1)
            dkw *= wreg                                                     # 不渗进眉毛
            m_ = (bh_ > 0.06) & reg_ & (dkw < 0.3)                          # 散落的细发丝（四周是皮肤）：用周围肤色补
            m_ = _box(m_.astype(np.float32), 3) > 0.02
            m_ |= dkw > 0.01                                               # 发束底下也换成肤色：半透明边缘处不然会混出一道暗带
            print('STRANDS dark px', int(dk_.sum()), 'skin', round(sk_, 3), flush=True)
            if m_.any():
                known = (~m_ & (g_ > 0.78 * sk_)).astype(np.float32)
                rgb = a[..., :3]; num = rgb * known[..., None]; den = known.copy()
                for r_ in (14, 14, 14): num = np.stack([_box(num[..., k], r_) for k in range(3)], -1); den = _box(den, r_)
                fill = np.where(den[..., None] > 1e-3, num / np.maximum(den, 1e-3)[..., None], rgb)
                w_ = np.clip(_box(m_.astype(np.float32), 3) * 1.6, 0, 1)
                w_ = np.maximum(w_ * wreg, np.clip(dkw * 3, 0, 1))
                a[..., :3] = rgb * (1 - w_[..., None]) + fill * w_[..., None]
            a[..., 3] *= 1 - dkw
            print('STRANDS removed px', int(m_.sum()), flush=True)
            save_rgba(a.copy(), os.path.join(tmp, cid + '_strands_removed.png'), cid + '_strands_dbg')
        return a
    ph_ = os.path.join(IDDIR, cid + '_noglasses.png')   # 照片戴眼镜的角色：用去掉眼镜框的版本（3D 眼镜另外建模）
    warped = tps_warp(photo_masked(ph_ if os.path.exists(ph_) else os.path.join(IDDIR, cid + '.png')), src, dst)
    m0_ = body.material_slots[0].material; gt_ = next(n for n in m0_.node_tree.nodes if n.type == 'GROUP').node_tree
    srcd = dict(zip(keys, src))
    if fit is not None:
        warped = photo_tone(warped, srcd, gt_, RES / 4.4)
        warped[..., 3] *= face_region(srcd, RES / 4.4)
        if os.environ.get('V11_DBG_GRID'): warped[::32, :, :3] = 0; warped[:, ::32, :3] = 0   # 排查清晰度：画网格
    wimg = save_rgba(warped, os.path.join(tmp, cid + '_warped.png'), cid + '_warped'); wimg.colorspace_settings.name = 'sRGB'
    json.dump({k: [round(v, 1) for v in s] for k, s in zip(keys, src)}, open(os.path.join(tmp, cid + '_render_landmarks.json'), 'w'))
    if 'chin' not in lm3: lm3['chin'] = lm3.get('chin')
    if fit is not None:   # 旧流程里的眼睛中心（遮罩用）：拟合流程用眼角中点
        lm3['eye_R'] = (lm3['eye_R_out'] + lm3['eye_R_in']) / 2; lm3['eye_L'] = (lm3['eye_L_out'] + lm3['eye_L_in']) / 2
    # ---- 投影 + 遮罩 + 烘焙 ----
    me = body.data
    # 烘焙时关掉渲染细分：细分后再做投影 UV，烘焙结果会糊成一片（实测网格线全糊掉）；烘焙完恢复
    subd = body.modifiers.get('subdiv'); subd_lv = subd.render_levels if subd else 0
    if subd: subd.render_levels = 0
    if 'v11_proj' not in me.uv_layers: me.uv_layers.new(name='v11_proj')
    me.uv_layers['UVMap'].active = True; me.uv_layers['UVMap'].active_render = True
    uvm = body.modifiers.new('v11_uvproj', 'UV_PROJECT'); uvm.uv_layer = 'v11_proj'; uvm.projector_count = 1; uvm.projectors[0].object = cam
    m0 = body.material_slots[0].material
    gnode = next(n for n in m0.node_tree.nodes if n.type == 'GROUP'); gt = gnode.node_tree
    bsdf = next(n for n in gt.nodes if n.type == 'BSDF_PRINCIPLED'); chain = bsdf.inputs['Base Color'].links[0].from_socket
    stockmix = gt.nodes.get('v11_stockmix')   # 丝袜层：烘焙时绕开（不烘进皮肤贴图），烘完把皮肤贴图接回它前面
    if stockmix is not None and stockmix.inputs[6].links: chain = stockmix.inputs[6].links[0].from_socket
    gout = next(n for n in gt.nodes if n.type == 'GROUP_OUTPUT'); out_sock = gout.inputs[0]; orig_shader = out_sock.links[0].from_socket
    N = gt.nodes.new; Lk = gt.links.new; tmp_nodes = []
    def node(t, **kv):
        n = N(t); tmp_nodes.append(n)
        for k, v in kv.items(): setattr(n, k, v)
        return n
    uvn = node('ShaderNodeUVMap', uv_map='v11_proj')
    tex = node('ShaderNodeTexImage', image=wimg, extension='CLIP'); Lk(uvn.outputs['UV'], tex.inputs['Vector'])
    geo = node('ShaderNodeNewGeometry')
    dot = node('ShaderNodeVectorMath', operation='DOT_PRODUCT'); dot.inputs[1].default_value = tuple(-vdir); Lk(geo.outputs['Normal'], dot.inputs[0])
    def ramp(sock, a, b):   # a→0、b→1 的平滑过渡
        r = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP'); r.inputs['From Min'].default_value = a; r.inputs['From Max'].default_value = b
        Lk(sock, r.inputs['Value']); return r.outputs['Result']
    def mul(a, b):
        m = node('ShaderNodeMath', operation='MULTIPLY'); Lk(a, m.inputs[0]); Lk(b, m.inputs[1]); return m.outputs[0]
    facing = ramp(dot.outputs['Value'], 0.35, 0.80) if fit is None else ramp(dot.outputs['Value'], 0.12, 0.50)   # 越正对镜头越用照片；侧面渐变回原皮肤（拟合流程放宽：眉尾在太阳穴的斜面上，原来被渐变掉了）
    sep = node('ShaderNodeSeparateXYZ'); Lk(geo.outputs['Position'], sep.inputs['Vector'])
    z_bot = ramp(sep.outputs['Z'], lm3['chin'].z - iod * 0.6, lm3['chin'].z - iod * 0.15)   # 往下过渡到脖子
    # 额头上部：旧流程不投照片的发际线（脸部 = 1，往上过渡到 0）；拟合流程（有照着照片做的发型）一直投到发际线以上——
    # 照片里发际线自带的细碎绒毛贴在发型边缘下面，边缘自然变虚
    z_top =ramp(sep.outputs['Z'], c.z + iod * 1.05, c.z + iod * 0.75) if fit is None else ramp(sep.outputs['Z'], c.z + iod * 1.05, c.z + iod * 0.75)   # 试过投到发际线以上：照片的发丝被去光照提亮，像额头上的污痕，先不用
    mask = mul(mul(mul(facing, tex.outputs['Alpha']), z_bot), z_top)
    if fit is not None:   # 嘴唇（含上下唇贴合处朝上/朝下的内侧面）一律用照片颜色，否则唇缝露出原贴图的浅色唇内侧，像一道白线
        gi = body.vertex_groups['lips'].index
        if 'v11_lips' in me.attributes: me.attributes.remove(me.attributes['v11_lips'])
        at = me.attributes.new('v11_lips', 'FLOAT', 'POINT')
        at.data.foreach_set('value', [1.0 if any(g.group == gi and g.weight > 0.5 for g in v.groups) else 0.0 for v in me.vertices])
        an = node('ShaderNodeAttribute', attribute_name='v11_lips')
        lipf = ramp(dot.outputs['Value'], -0.2, 0.15)   # 嘴角朝侧面的部分不强制（照片在那里被拉长成一道）
        mx = node('ShaderNodeMath', operation='MAXIMUM'); Lk(mask, mx.inputs[0]); Lk(mul(mul(an.outputs['Fac'], tex.outputs['Alpha']), lipf), mx.inputs[1]); mask = mx.outputs[0]
    if fit is None:   # 旧流程（6 个点对不准眼皮）：眼球附近保留模型皮肤；拟合流程睑缘已对齐，照片眼皮直接贴
        for e in (lm3['eye_R'], lm3['eye_L']):
            d = node('ShaderNodeVectorMath', operation='DISTANCE'); d.inputs[1].default_value = e; Lk(geo.outputs['Position'], d.inputs[0])
            mask = mul(mask, ramp(d.outputs['Value'], iod * 0.12, iod * 0.20))
    # 旧流程：全身肤色往照片靠（增益乘在原皮肤上）；拟合流程反过来，照片已在 photo_tone 里对齐身体肤色
    gain = skin_gain(warped, src, gt) if fit is None else (1.0, 1.0, 1.0)
    gmix = node('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY'); gmix.inputs['Factor'].default_value = 1.0
    Lk(chain, gmix.inputs[6]); gmix.inputs[7].default_value = (*gain, 1)
    dim = node('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY'); dim.inputs['Factor'].default_value = 1.0   # 照片自带光照：压暗一点，免得叠上渲染光照后发白
    Lk(tex.outputs['Color'], dim.inputs[6]); dim.inputs[7].default_value = (0.82, 0.82, 0.82, 1) if fit is None else (1, 1, 1, 1)
    photo_col = dim.outputs[2]
    if fit is not None:
        # 唇缝内侧（上下唇贴合处朝上/朝下的面）正面几乎看不到，投影上去的照片被拉成长条，3/4 角度像嘴角拖出一道深线：
        # 这些面改用照片下唇的平均唇色（越朝侧面越用它）
        lt, lb = np.array(srcd_all['lip_top']), np.array(srcd_all['lip_bot']); sp = (lt + lb) / 2 + (lb - lt) * 0.28
        x_, y_ = int(sp[0]), int(sp[1]); patch = warped[y_ - 6:y_ + 7, x_ - 10:x_ + 11, :3].reshape(-1, 3)
        lip_lin = np.where(patch <= 0.04045, patch / 12.92, ((patch + 0.055) / 1.055) ** 2.4).mean(0)
        wl = mul(an.outputs['Fac'], ramp(dot.outputs['Value'], 0.45, 0.10))
        lm_ = node('ShaderNodeMix', data_type='RGBA'); Lk(wl, lm_.inputs['Factor']); Lk(photo_col, lm_.inputs[6])
        lm_.inputs[7].default_value = (*(lip_lin * 0.85), 1); photo_col = lm_.outputs[2]
        print('LIP COLOR', np.round(lip_lin, 3), flush=True)
    if fit is not None:   # 唇缝内侧（朝上/朝下的面）压暗：否则渲染时这一圈湿润高光像一道白线
        f2 = ramp(dot.outputs['Value'], -0.2, 0.6)
        k1 = node('ShaderNodeMapRange'); k1.inputs['To Min'].default_value = 0.3; Lk(f2, k1.inputs['Value'])      # 0.3 ~ 1
        kk = node('ShaderNodeMix', data_type='FLOAT'); Lk(an.outputs['Fac'], kk.inputs['Factor']); kk.inputs[2].default_value = 1.0; Lk(k1.outputs['Result'], kk.inputs[3])
        dm = node('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY'); dm.inputs['Factor'].default_value = 1.0
        Lk(photo_col, dm.inputs[6]); cc = node('ShaderNodeCombineColor'); Lk(kk.outputs[0], cc.inputs[0]); Lk(kk.outputs[0], cc.inputs[1]); Lk(kk.outputs[0], cc.inputs[2])
        Lk(cc.outputs[0], dm.inputs[7]); photo_col = dm.outputs[2]
    mix = node('ShaderNodeMix', data_type='RGBA'); Lk(mask, mix.inputs['Factor']); Lk(gmix.outputs[2], mix.inputs[6]); Lk(photo_col, mix.inputs[7])
    emi = node('ShaderNodeEmission'); Lk(mix.outputs[2], emi.inputs['Color']); Lk(emi.outputs[0], out_sock)
    diff = next(n for n in gt.nodes if n.type == 'TEX_IMAGE' and n.name == 'DiffuseTexture')
    W, H = diff.image.size if diff.image else (4096, 4096)
    if fit is not None: W = H = max(W, 4096)   # MakeHuman 贴图布局里脸只占很小一块：2048 时脸约 300 像素宽，比照片还糊
    baked = bpy.data.images.new(cid + '_skin_identity', W, H, alpha=False)
    targets = []
    for s in body.material_slots:   # 烘焙目标：每个材质都要有一个选中的目标图片节点
        if not s.material: continue
        t = s.material.node_tree.nodes.new('ShaderNodeTexImage'); t.image = baked; s.material.node_tree.nodes.active = t; targets.append((s.material, t))
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 1
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
        for d_ in prefs.devices: d_.use = (d_.type == 'OPTIX')
        sc.cycles.device = 'GPU'
    except Exception: pass
    for o in bpy.context.view_layer.objects: o.select_set(False)
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.bake(type='EMIT', margin=8, use_clear=True)
    # ---- 还原：皮肤底色直接用烘焙出来的贴图（照片的颜色已经是最终颜色，不再叠调色）----
    Lk(orig_shader, out_sock)
    for n in tmp_nodes: gt.nodes.remove(n)
    bt = gt.nodes.new('ShaderNodeTexImage'); bt.image = baked; bt.location = diff.location.copy(); bt.location.y -= 300
    uvb = gt.nodes.new('ShaderNodeUVMap'); uvb.uv_map = 'UVMap'; gt.links.new(uvb.outputs['UV'], bt.inputs['Vector'])
    if stockmix is not None: gt.links.new(bt.outputs['Color'], stockmix.inputs[6])   # 丝袜仍叠在皮肤上（原来直接接到 BSDF，黑丝没了）
    else: gt.links.new(bt.outputs['Color'], bsdf.inputs['Base Color'])
    if fit is not None:   # 深色处（眉毛、睫毛根、发际线）几乎不反光：皮肤的镜面反光叠在眉毛上会把它冲成灰蓝、发糊
        bw = gt.nodes.new('ShaderNodeRGBToBW'); gt.links.new(bt.outputs['Color'], bw.inputs['Color'])
        mr = gt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value = 0.04; mr.inputs['From Max'].default_value = 0.30; mr.inputs['To Min'].default_value = 0.08
        gt.links.new(bw.outputs['Val'], mr.inputs['Value'])
        for nm in ('Specular IOR Level', 'Coat Weight', 'Sheen Weight'):
            sk = bsdf.inputs.get(nm)
            if sk is None: continue
            mm_ = gt.nodes.new('ShaderNodeMath'); mm_.operation = 'MULTIPLY'; gt.links.new(mr.outputs['Result'], mm_.inputs[1])
            if sk.links: gt.links.new(sk.links[0].from_socket, mm_.inputs[0])
            else: mm_.inputs[0].default_value = sk.default_value
            gt.links.new(mm_.outputs[0], sk)
    sw = bsdf.inputs.get('Subsurface Weight')   # 皮肤透光调弱：照片颜色本来就是最终肤色，强透光会把它冲白
    if sw is not None and sw.links:
        k_ = gt.nodes.new('ShaderNodeMath'); k_.operation = 'MULTIPLY'; k_.inputs[1].default_value = 0.35
        gt.links.new(sw.links[0].from_socket, k_.inputs[0]); gt.links.new(k_.outputs[0], sw)
    elif sw is not None: sw.default_value *= 0.35
    for mat, t in targets: mat.node_tree.nodes.remove(t)
    body.modifiers.remove(uvm); me.uv_layers.remove(me.uv_layers['v11_proj'])
    if subd: subd.render_levels = subd_lv
    if 'v11_lips' in me.attributes: me.attributes.remove(me.attributes['v11_lips'])
    bpy.data.objects.remove(cam, do_unlink=True)
    keep3d = json.load(open(os.path.join(IDDIR, cid + '_landmarks_full.json'), encoding='utf-8')).get('keep_brow3d', False) if fit is not None else False
    for o in [o for o in bpy.data.objects if o.name.startswith(cid + '_eyebrow') and not keep3d]: bpy.data.objects.remove(o, do_unlink=True)   # 照片里眉毛被刘海盖住的角色（keep_brow3d）保留 3D 眉毛   # 照片里有眉毛
    baked.pack(); wimg.user_clear(); bpy.data.images.remove(wimg)
    body['v11_identity'] = True
    bpy.ops.wm.save_mainfile()
    print('IDENTITY OK', cid, 'texture', W, H, 'landmarks', src, flush=True)

if __name__ == '__main__':
    project(sys.argv[sys.argv.index('--') + 1])
