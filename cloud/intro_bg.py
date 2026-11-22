# -*- coding: utf-8 -*-
"""片头背景（云端，Krea2 文生图）：大连理工大学校园场景候选 3 张，画面一侧留空给 Claude 娘。
输出 /root/v11_out/intro_bg_<k>.png。用法：python3 intro_bg.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
BG = {
 'main':  '写实照片，大连理工大学主楼前的广场：一座对称的米黄色苏式风格大楼，中央有高耸的塔楼，楼前是宽阔的广场、整齐的草坪和松树，清晨的阳光，蓝天白云，'
          '画面右侧三分之一是空旷的广场地面，没有任何人，电影感广角构图，16:9',
 'lib':   '写实照片，大连理工大学令希图书馆：一座现代风格的浅色大型图书馆建筑，前面有水面倒影和绿树，清晨的柔和阳光，蓝天，'
          '画面右侧三分之一是空旷的步道，没有任何人，电影感广角构图，16:9',
 'sakura':'写实照片，大连理工大学校园里的樱花林荫道：两侧开满粉白色的樱花树，远处是红砖和米色的教学楼，春天清晨的阳光透过花枝，地面落满花瓣，'
          '画面右侧留出空旷的道路，没有任何人，电影感构图，16:9',
}
for k, (name, p) in enumerate(BG.items(), 1):
    comfy_run.run('Krea2-文生图-4K.json', 'intro_bg_%s' % name, {'271.string': p, '264.width': 1344, '264.height': 768, '255.seed': 101 + k, '254.seed': 101 + k},
                  timeout=1200)
print('INTRO BG DONE', flush=True)
