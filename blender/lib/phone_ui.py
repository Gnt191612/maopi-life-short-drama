# -*- coding: utf-8 -*-
"""手机与屏幕界面：真实地在三维手机屏幕上排出聊天/评论、来电、朋友圈动态（文字用开源字体 Noto Sans SC），
预览和正式渲染都能看到；正片阶段 Remotion 仍可按屏幕四角替换成精修界面。
手机结构：空物体 prop_phone_<id>（不缩放，屏幕朝局部 +Z、顶端朝 +Y）下挂机身、屏幕面、界面元素，避免父子缩放叠加。
"""
import bpy
import config
from mathutils import Vector
import sets

W, H, T = 0.071, 0.150, 0.008          # 机身宽、高、厚（米）
SW, SH = 0.065, 0.140                  # 屏幕可视区
Z0 = T / 2 + 0.0004                    # 屏幕表面（局部 z）
_FONT = None
EM = 2.85     # Blender 文字的 size 约等于 0.35 个汉字宽：换算成「一个汉字多宽（米）」

def font():
    """屏幕界面用静态粗体（可变字体在 Blender 里会按最细字重加载，小字几乎看不见）"""
    global _FONT
    if _FONT is None or _FONT.name not in bpy.data.fonts:
        import os
        p = os.path.join(config.FONTS_DIR, 'NotoSansSC-Static-Bold.ttf')
        _FONT = bpy.data.fonts.load(p if os.path.exists(p) else config.FONT, check_existing=True)
    return _FONT

def _emit(name, rgb, strength=1.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*rgb, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], o.inputs[0])
    return m

def _child(root, o, loc, scale=None):
    o.parent = root; o.location = loc
    if scale: o.scale = scale
    if o.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(o)
    return o

def make_phone(cid):
    root = bpy.data.objects.new('prop_phone_' + cid, None); root.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(root)
    body = bpy.data.objects.new('prop_phonebody_' + cid, sets._unit_cube()); _child(root, body, (0, 0, 0), (W, H, T))
    body.material_slots[0].link = 'OBJECT'; body.material_slots[0].material = sets.mat('prop_black', (0.02, 0.02, 0.025))
    scr = bpy.data.objects.new('prop_screen_' + cid, sets._unit_cube()); _child(root, scr, (0, 0, T / 2), (SW, SH, 0.0006))
    scr.material_slots[0].link = 'OBJECT'; scr.material_slots[0].material = _emit('ui_screen_off', (0.02, 0.025, 0.035), 0.3)
    return root

def phone_parts(root):
    return [root] + [c for c in root.children if c.name.startswith(('prop_phonebody_', 'prop_screen_'))]

def _rect(root, name, w, h, x, y, rgb, z=0.0, strength=1.0):
    o = bpy.data.objects.new(name, sets._unit_cube()); _child(root, o, (x, y, Z0 + 0.0002 + z), (w, h, 0.0002))
    o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = _emit('ui_' + '_'.join('%.2f' % c for c in rgb), rgb, strength)
    return o

def _wrap(body, max_w):
    """按字宽手动换行（汉字记 1、英文数字记 0.55）：Blender 文字框只在空格处换行，中文整段冲出屏幕（2026-11-22）"""
    if not max_w: return body
    out, cur, w = [], '', 0.0
    for ch in body:
        if ch == '\n': out.append(cur); cur, w = '', 0.0; continue
        cw = 0.55 if ord(ch) < 0x2E80 else 1.0
        if w + cw > max_w and cur: out.append(cur); cur, w = '', 0.0
        cur += ch; w += cw
    out.append(cur); return '\n'.join(out)

_PX = 64   # 文字贴图：每个汉字 64 像素

def _text_png(body, rgb, align):
    """用系统 Python + PIL 把文字画成透明 PNG（缓存到 build/screen_text/），失败返回 None"""
    import os, hashlib, subprocess
    d = os.path.join(config.ROOT, 'build', 'screen_text'); os.makedirs(d, exist_ok=True)
    key = hashlib.md5(('%s|%s|%s' % (body, rgb, align)).encode('utf-8')).hexdigest()[:16]
    out = os.path.join(d, key + '.png')
    if not os.path.exists(out):
        py = os.environ.get('V11_SYSPY') or 'python'
        try:
            subprocess.run([py, os.path.join(config.BLENDER_SCRIPTS, 'tools_text_png.py'), out, body, ','.join('%.3f' % c for c in rgb), align, str(_PX), '1'],
                           capture_output=True, timeout=60)
        except Exception as e: print('TEXT PNG FAIL', e, flush=True)
    return out if os.path.exists(out) else None

def _text(root, name, body, x, y, size, rgb, width=None, align='LEFT', z=0.0):
    """屏幕文字：PIL 画好的透明贴图贴在小平面上（size = 一个汉字多宽，米；width = 文字框宽，米）"""
    body = _wrap(body, (width / size) if width else None)
    png = _text_png(body, rgb, align)
    if png is None:   # 兜底：Blender 文字曲线（笔画会缺块，但至少有字）
        cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.font = font(); cu.size = size * EM
        cu.align_x = align; cu.align_y = 'TOP'
        o = bpy.data.objects.new(name, cu); _child(root, o, (x, y, Z0 + 0.0006 + z))
        o.data.materials.append(_emit('ui_txt_' + '_'.join('%.2f' % c for c in rgb), rgb, 1.0))
        return o
    img = bpy.data.images.load(png, check_existing=True)
    w_m, h_m = img.size[0] / _PX * size, img.size[1] / _PX * size
    cx = x + w_m / 2 if align == 'LEFT' else x
    o = bpy.data.objects.new(name, sets._unit_cube()); _child(root, o, (cx, y - h_m / 2, Z0 + 0.0006 + z), (w_m, h_m, 0.00005))
    m = bpy.data.materials.new('ui_txtimg_' + name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Cubic'; tex.extension = 'CLIP'
    tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Generated'], tex.inputs['Vector'])   # 按包围盒 0~1 铺满（立方体自带的 UV 每个面只占贴图一小块，字只显示一角，2026-11-22）
    em = nt.nodes.new('ShaderNodeEmission'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(tex.outputs['Alpha'], mx.inputs['Fac'])
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
    o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = m
    return o

def _show(objs, f_on, f_off):
    for o in objs:
        for fr, v in ((1, True), (f_on - 1, True), (f_on, False), (f_off, False), (f_off + 1, True)):
            if fr < 1: continue
            o.hide_render = v; o.hide_viewport = v
            o.keyframe_insert('hide_render', frame=fr); o.keyframe_insert('hide_viewport', frame=fr)

def build_ui(root, owner, items, f_end, tag):
    """items: [(出现帧, 发送人/标题, 文字)]；f_end：界面保留到哪一帧。按内容自动选样式：来电 / 朋友圈动态 / 评论列表"""
    L, R, TOP = -SW / 2 + 0.004, SW / 2 - 0.004, SH / 2
    first = items[0][0]; made = []
    if items[0][1] == '来电':                                           # 来电界面
        made += [_rect(root, 'ui_%s_bg' % tag, SW, SH, 0, 0, (0.08, 0.10, 0.14), strength=0.9),
                 _text(root, 'ui_%s_name' % tag, items[0][2], 0, TOP - 0.030, 0.011, (1, 1, 1), align='CENTER'),
                 _text(root, 'ui_%s_sub' % tag, '来电…', 0, TOP - 0.048, 0.005, (0.75, 0.78, 0.82), align='CENTER'),
                 _rect(root, 'ui_%s_no' % tag, 0.013, 0.013, -0.016, -SH / 2 + 0.020, (0.90, 0.25, 0.22)),
                 _rect(root, 'ui_%s_yes' % tag, 0.013, 0.013, 0.016, -SH / 2 + 0.020, (0.25, 0.80, 0.35))]
        _show(made, first, f_end); return made
    base = [_rect(root, 'ui_%s_bg' % tag, SW, SH, 0, 0, (0.95, 0.95, 0.95), strength=0.9),
            _rect(root, 'ui_%s_bar' % tag, SW, 0.011, 0, TOP - 0.0055, (0.93, 0.93, 0.93), z=0.0001),
            _text(root, 'ui_%s_title' % tag, '朋友圈', 0, TOP - 0.0025, 0.0045, (0.1, 0.1, 0.1), align='CENTER')]
    _show(base, first, f_end); made += base
    y = TOP - 0.016
    post = next((it for it in items if it[1].endswith('的朋友圈')), None)
    if post:                                                           # 动态正文（带头像、名字；林晓那条带一张原图）
        name = post[1][:-4]
        grp = [_rect(root, 'ui_%s_ava' % tag, 0.009, 0.009, L + 0.0045, y - 0.0045, (0.55, 0.65, 0.80), z=0.0001),
               _text(root, 'ui_%s_pname' % tag, name, L + 0.011, y, 0.0042, (0.25, 0.35, 0.60)),
               _text(root, 'ui_%s_ptext' % tag, post[2], L + 0.011, y - 0.0055, 0.0040, (0.08, 0.08, 0.08), width=R - L - 0.011)]
        lines = 1 + len(post[2]) // 13
        y -= 0.0065 + lines * 0.0052
        if '原图' in post[2]:
            grp.append(_rect(root, 'ui_%s_photo' % tag, 0.036, 0.027, L + 0.011 + 0.018, y - 0.0135, (0.55, 0.70, 0.45), z=0.0001)); y -= 0.029
        _show(grp, post[0], f_end); made += grp; y -= 0.004
    else:                                                              # 只有评论：上方是被评论的那条动态（缩略）
        grp = [_rect(root, 'ui_%s_ava' % tag, 0.009, 0.009, L + 0.0045, y - 0.0045, (0.55, 0.65, 0.80), z=0.0001),
               _text(root, 'ui_%s_pname' % tag, owner, L + 0.011, y, 0.0042, (0.25, 0.35, 0.60)),
               _rect(root, 'ui_%s_photo' % tag, 0.030, 0.030, L + 0.011 + 0.015, y - 0.0215, (0.62, 0.58, 0.52), z=0.0001)]
        _show(grp, first, f_end); made += grp; y -= 0.040
    for k, (fr, who, txt) in enumerate(it for it in items if not it[1].endswith('的朋友圈')):   # 评论一条条出现
        lines = 1 + (len(who) + 1 + len(txt)) // 14
        h = 0.0016 + lines * 0.0050
        grp = [_rect(root, 'ui_%s_cbg%d' % (tag, k), R - L, h, 0, y - h / 2, (0.90, 0.90, 0.90), z=0.0001),
               _text(root, 'ui_%s_c%d' % (tag, k), '%s：%s' % (who.replace('网友·', ''), txt), L + 0.0012, y - 0.0008, 0.0038, (0.10, 0.10, 0.10), width=R - L - 0.0024)]
        _show(grp, fr, f_end); made += grp; y -= h + 0.0012
    return made

def insert_camera(root, name):
    """手机屏幕特写机位：挂在手机上（随手微动），正对屏幕"""
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); bpy.context.scene.collection.objects.link(cam)
    cam.parent = root; cam.location = (0, -0.004, 0.105); cam.rotation_euler = (0.04, 0, 0)   # 贴近屏幕，夹在手机和脸之间
    cam.data.lens = 21; cam.data.clip_start = 0.005; cam.data.clip_end = 50
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 0.105; cam.data.dof.aperture_fstop = 8
    return cam
