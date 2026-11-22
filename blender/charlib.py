# -*- coding: utf-8 -*-
"""人物库（characters/<cid>/）读取：每个角色的全部参数集中在 characters/<cid>/character.py 的 CHAR 字典里，
建模时由这里把它们装进 build_cast / hair_cards / jk_sailor / accessories 里的各个参数表（同名条目以人物库为准）。
同事新增或优化人物只需要改 characters/，不用碰建模代码。说明见 characters/README.md。"""
import os, glob, runpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'characters')

# CHAR 的键 → (模块, 参数表名, 类型)。类型：dict = 参数表[cid] = 值；set = 值为 True 时 cid 加入集合
FIELDS = {
    'cast':         ('build_cast', 'CAST', 'dict'),          # (中文名, 性别0女1男, 年龄, 体重, 肌肉, 身高宏, 比例, 系统服装, 系统发型, 上衣色, 下装色)
    'height':       ('build_cast', 'HEIGHT', 'dict'),        # 目标身高（米）
    'face':         ('build_cast', 'FACE', 'dict'),          # 五官形态目标（照片拟合后只保留影响侧面的项）
    'face_scale':   ('build_cast', 'FACE_SCALE_OF', 'dict'),
    'eyebrow':      ('build_cast', 'EYEBROW', 'dict'),
    'skin':         ('build_cast', 'SKINS', 'dict'),         # MakeHuman 皮肤
    'skin_tint':    ('build_cast', 'SKIN_TINT', 'dict'),
    'iris':         ('build_cast', 'IRIS', 'dict'),
    'lip_tint':     ('build_cast', 'LIP_TINT', 'dict'),
    'stockings':    ('build_cast', 'STOCKINGS', 'dict'),
    'body':         ('build_cast', 'BODY', 'dict'),          # 身体形态目标（不动宏「体重」）
    'cup':          ('build_cast', 'CUP', 'dict'),
    'firm':         ('build_cast', 'FIRM', 'dict'),
    'outfit':       ('build_cast', 'OUTFIT', 'dict'),        # [(服装 mhclo, 颜色 或 'KIND' 改贴图), ...]
    'shoes':        ('build_cast', 'SHOES', 'dict'),
    'shoe_tint':    ('build_cast', 'SHOE_TINT', 'dict'),
    'top_fit':      ('build_cast', 'TOP_FIT', 'dict'),
    'fit_adjust':   ('build_cast', 'FIT_ADJUST', 'dict'),    # 照片拟合后的手动微调（深度方向）
    'fit_smooth':   ('build_cast', 'FIT_SMOOTH', 'dict'),
    'fit_crown':    ('build_cast', 'FIT_CROWN', 'dict'),
    'fit_shoulder': ('build_cast', 'FIT_SHOULDER', 'dict'),
    'lip_seal':     ('build_cast', 'LIP_SEAL', 'set'),
    'drape':        ('build_cast', 'DRAPE', 'set'),
    'hair_shape':   ('build_cast', 'HAIR_SHAPE', 'dict'),
    'hair_color':   ('build_cast', 'HAIR_COLOR', 'dict'),
    'keep_shell':   ('build_cast', 'KEEP_SHELL', 'set'),
    'hair':         ('hair_cards', 'CARDS', 'dict'),         # 照片发型参数（见 blender/lib/hair_cards.py 顶部）
    'sailor':       ('jk_sailor', 'SAILOR', 'dict'),
    'vtop':         ('jk_sailor', 'VTOP', 'dict'),
    'earring':      ('accessories', 'EARRING', 'dict'),
}
# 不进建模、给其他环节用的键：look / look_en（写实化外貌描述，cloud/looks.py）、voice（音色参考音文件名）、note（说明）

def chars():
    """人物库里所有角色：{cid: CHAR 字典}（_ 开头的目录是模板，跳过）"""
    out = {}
    for p in sorted(glob.glob(os.path.join(LIB, '*', 'character.py'))):
        cid = os.path.basename(os.path.dirname(p))
        if cid.startswith('_'): continue
        out[cid] = runpy.run_path(p).get('CHAR', {})
    return out

def apply(modules):
    """modules：{'build_cast': 模块全局字典, 'hair_cards': 模块, ...}；把人物库装进各参数表"""
    n = 0
    for cid, C in chars().items():
        for key, val in C.items():
            if key not in FIELDS: continue
            mod, name, kind = FIELDS[key]
            g = modules.get(mod)
            if g is None: continue
            g = g if isinstance(g, dict) else vars(g)
            if kind == 'set':
                s = g.setdefault(name, set())
                (s.add if val else s.discard)(cid)
            else:
                g.setdefault(name, {})[cid] = val
            n += 1
    return n

def identity(cid, suffix='.png'):
    """标准长相照片 / 关键点 / 拟合结果的路径：人物库优先，旧位置 assets/identity 兜底"""
    for d in (os.path.join(LIB, cid), os.path.join(ROOT, 'assets', 'identity')):
        p = os.path.join(d, cid + suffix)
        if os.path.exists(p): return p
    return os.path.join(LIB, cid, cid + suffix)
