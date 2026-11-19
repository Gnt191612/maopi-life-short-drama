# -*- coding: utf-8 -*-
"""把 side_heads.py 渲出的头部特写拼成一张总览图：python blender/tests/heads_sheet.py [角色id ...]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from PIL import Image
D = os.path.join(config.RENDERS, 'side_heads')
ids = sys.argv[1:] or ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']
views = ('front', 'side', 'backside'); S = 300
rows = [[os.path.join(D, '%s_%s.png' % (c, v)) for v in views] for c in ids if os.path.exists(os.path.join(D, '%s_front.png' % c))]
cols = 2 if len(rows) > 3 else 1
sheet = Image.new('RGB', (cols * S * 3, ((len(rows) + cols - 1) // cols) * S), (40, 40, 40))
for i, r in enumerate(rows):
    for j, f in enumerate(r): sheet.paste(Image.open(f).resize((S, S)), ((i % cols) * S * 3 + j * S, (i // cols) * S))
sheet.save(os.path.join(D, '_sheet.png')); print(os.path.join(D, '_sheet.png'))
