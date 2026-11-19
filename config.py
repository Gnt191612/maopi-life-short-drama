# -*- coding: utf-8 -*-
"""全局路径配置：一切路径都相对仓库根目录推导，换任何电脑都能运行（不依赖 Blender，Blender 内外的脚本都 import 它）。
外部工具统一由 setup/ 下的安装脚本下载到 <仓库>/.tools/，也可以用环境变量指定已有安装：
  V11_BLENDER  Blender 可执行文件      V11_FFMPEG  ffmpeg 可执行文件      V11_RHUBARB  rhubarb 可执行文件
"""
import os, sys, shutil, platform

ROOT = os.path.dirname(os.path.abspath(__file__))
WIN = platform.system() == 'Windows'
EXE = '.exe' if WIN else ''

def P(*parts):
    return os.path.join(ROOT, *parts)

# ---- 工程目录 ----
STORY = P('story')                 # 剧本结构、台词、走位表
BLENDER_SCRIPTS = P('blender')     # Blender 端脚本
ASSETS = P('assets')               # 固定资产（入库，Git LFS）
CAST = P('assets', 'cast')         # 7 个角色 .blend
if os.environ.get('V11_CAST_DIR'): CAST = os.environ['V11_CAST_DIR']   # 迭代新版人物时先建到暂存目录（不影响正在跑的渲染）
SETS = P('assets', 'sets')         # 19 个场景 .blend
AUDIO = P('assets', 'audio')       # 78 句配音 wav + meta.json
VISEMES = P('build', 'visemes')    # 口型序列（可重新生成）
MOCAP = P('build', 'mocap')        # CMU 动作捕捉片段（安装脚本下载）
SHOTS = P('build', 'shots')        # 每个片段的完整动画 .blend（可重新生成）
RENDERS = P('build', 'renders')    # 白模画面 / 深度图（可重新生成）
PREVIS = P('build', 'previs')      # 预演视频（可重新生成）
# 快速剧情预览：V11_PREVIEW=1 时用 EEVEE 低分辨率渲染，输出与正式渲染分开存放
PREVIEW = os.environ.get('V11_PREVIEW') == '1'
if PREVIEW:
    RENDERS = P('build', 'renders_preview'); PREVIS = P('build', 'previs_preview')
LOGS = P('build', 'logs')

# ---- 外部工具（.tools/ 下，由 setup 脚本下载）----
TOOLS = P('.tools')
BLENDER_VERSION = '4.5.16'
BLENDER_USER = os.path.join(TOOLS, 'blender_user')   # Blender 用户目录放在仓库内：插件与 MakeHuman 素材都在这里，不污染系统

def _find(env, candidates, which=None):
    if os.environ.get(env): return os.environ[env]
    for c in candidates:
        if os.path.exists(c): return c
    return shutil.which(which) if which else None

BLENDER = _find('V11_BLENDER', [os.path.join(TOOLS, 'blender', 'blender' + EXE)], 'blender')
FFMPEG = _find('V11_FFMPEG', [os.path.join(TOOLS, 'ffmpeg', 'ffmpeg' + EXE)], 'ffmpeg')
FFPROBE = _find('V11_FFPROBE', [os.path.join(TOOLS, 'ffmpeg', 'ffprobe' + EXE)], 'ffprobe')
RHUBARB = _find('V11_RHUBARB', [os.path.join(TOOLS, 'rhubarb', 'rhubarb' + EXE)], 'rhubarb')
FONT = os.path.join(TOOLS, 'fonts', 'NotoSansSC-Regular.ttf')     # 开源字体（SIL OFL），字幕与字卡用
FONT_NAME = 'Noto Sans SC'
FONTS_DIR = os.path.join(TOOLS, 'fonts')
BLENDER_HAIR_LIB = None   # Blender 自带发丝节点库，运行时按 Blender 安装位置推导（见 blender_hair_lib()）

def blender_hair_lib():
    import bpy
    return os.path.join(os.path.dirname(bpy.app.binary_path), BLENDER_VERSION[:3], 'datafiles', 'assets', 'geometry_nodes',
                        'procedural_hair_node_assets.blend')

def mpfb_data():
    """MakeHuman 素材目录（MPFB 用户数据）。BLENDER_USER_RESOURCES 指向仓库内目录，所以它也在仓库内。"""
    return os.path.join(BLENDER_USER, 'extensions', '.user', 'user_default', 'mpfb', 'data')

def blender_env():
    """调用 Blender 时使用的环境变量：用户目录指向仓库内（插件、素材随仓库走）"""
    env = dict(os.environ)
    env['BLENDER_USER_RESOURCES'] = BLENDER_USER
    env['PYTHONIOENCODING'] = 'utf-8'
    return env

# ---- 配音模型（仅在需要改台词、重新配音时使用；由 setup/setup_tts_* 安装，或用环境变量指向已有安装）----
SPARK_DIR = os.environ.get('V11_SPARK_DIR') or os.path.join(TOOLS, 'Spark-TTS')           # 含 pretrained_models/Spark-TTS-0.5B
COSYVOICE_DIR = os.environ.get('V11_COSYVOICE_DIR') or os.path.join(TOOLS, 'CosyVoice')   # 含 pretrained_models/CosyVoice2-0.5B
VOICE_TOOLS = P('voice_tools')

for _d in (VISEMES, MOCAP, SHOTS, RENDERS, PREVIS, LOGS):
    os.makedirs(_d, exist_ok=True)
for _p in (ROOT, STORY, BLENDER_SCRIPTS, os.path.join(BLENDER_SCRIPTS, 'lib')):
    if _p not in sys.path: sys.path.insert(0, _p)
