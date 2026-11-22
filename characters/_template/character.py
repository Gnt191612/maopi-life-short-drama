# -*- coding: utf-8 -*-
"""人物库模板：复制整个 _template 文件夹，改名为新角色代号（英文、无空格，如 xiaoli），再改下面的参数。
各键含义见 characters/README.md；不需要的键删掉即可（用默认值）。
改完运行：powershell -ExecutionPolicy Bypass -File blender\\tests\\identity_round.ps1 -Cid <代号> -Tag r1 -Body"""

CHAR = {
    # 中文名, 性别(0女1男), 年龄, 体重, 肌肉, 身高宏, 比例, 系统服装(占位), 系统发型(占位), 上衣色, 下装色   —— 都是 0~1 的 MakeHuman 宏参数
    'cast': ('新角色', 1.0, 0.45, 0.50, 0.50, 0.55, 0.50, 'male_casualsuit01', 'short02', (0.3, 0.3, 0.3), (0.15, 0.15, 0.18)),
    'height': 1.75,                          # 目标身高（米）
    'skin': 'young_asian_male',              # young_asian_male / young_asian_female / middleage_asian_male / middleage_asian_female
    'skin_tint': (1.0, 0.97, 0.95),
    'eyebrow': 'eyebrow005',                 # MakeHuman 眉形 eyebrow001~012
    'face': {},                              # 照片拟合前的大致五官（拟合后只保留影响侧面的项）
    'fit_adjust': {},                        # 照片拟合后的手动微调（胖瘦、双下巴、嘴突等深度方向）
    'lip_seal': True,                        # 唇缝封口（照片拟合的角色都要开）
    'body': {'upperlegs-height-incr': 0.25, 'lowerlegs-height-incr': 0.2},   # 身体形态目标
    'outfit': [('shirts01/clothes/elvs_crude_t-shirt_male/elvs_crude_t-shirt_male.mhclo', (0.2, 0.2, 0.25)),
               ('pants02/clothes/punkduck_male_classic_jeans/punkduck_male_classic_jeans.mhclo', None)],
    'shoes': 'shoes02',
    # 照片发型（短发示例；长发、马尾见 blender/lib/hair_cards.py 顶部各角色）
    'hair': dict(style='short', no_part=True, rgb=(0.006, 0.005, 0.0045), thick_top=0.02, thick_side=0.008, part_t=0.28, front_vol=0.004,
                 tie_up=-0.35, n_cards=0, baby=80, fly=150, cap_edge=False, base_hl=dict(ear=-0.05, behind=-0.065, nape=-0.072), curl=0.2),
    # 写实化提示词（与白模造型一致）
    'look': '一位20岁的中国男大学生，……，穿……',
    'look_en': 'a 20-year-old Chinese male college student, ..., wearing ...',
    'voice': '',                             # voice_tools/voices_v2 里选定的参考音色文件名
}
