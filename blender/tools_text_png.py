# -*- coding: utf-8 -*-
"""（系统 Python 运行，需要 Pillow）把一段文字画成透明背景 PNG，给 Blender 里的手机屏幕当贴图用。
Blender 的文字曲线不能正确填充 Noto Sans SC 的重叠轮廓（笔画缺块、像乱码，2026-11-22 全片检查），PIL/FreeType 可以。
用法：python blender/tools_text_png.py <输出.png> <文字（可含 \\n）> <r,g,b 0~1> <对齐 LEFT|CENTER> <每字像素> <粗体 0/1>"""
import sys, os
from PIL import Image, ImageDraw, ImageFont
out, text, rgb, align, px, bold = sys.argv[1:7]
px = int(px); col = tuple(int(float(c) * 255) for c in rgb.split(',')) + (255,)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, '.tools', 'fonts')
font = None
for name in (('NotoSansSC-Static-Bold.ttf', 'NotoSansSC-Regular.ttf') if bold == '1' else ('NotoSansSC-Static-Regular.ttf', 'NotoSansSC-Regular.ttf')):
    p = os.path.join(FD, name)
    if os.path.exists(p): font = ImageFont.truetype(p, px); break
if font is None: font = ImageFont.load_default()
lines = text.split('\n'); lh = int(px * 1.3)
w = max(1, max(int(font.getlength(l)) for l in lines) + 4); h = lh * len(lines) + 4
im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
for i, l in enumerate(lines):
    x = 2 if align == 'LEFT' else (w - font.getlength(l)) / 2
    d.text((x, 2 + i * lh), l, font=font, fill=col)
im.save(out); print('TEXT PNG', out, w, h)
