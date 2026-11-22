# -*- coding: utf-8 -*-
"""片头 Claude 娘动起来（云端，Wan2.2 图生视频，节点映射同 video_map.json）：首帧 = 本地合成的「主楼广场 + Claude 娘立绘」。
输出 /root/v11_out/intro_v<k>.*。用法：python3 intro_video.py <首帧文件名（已在 ComfyUI/input）> [种子 ...]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_map.json'), encoding='utf-8'))
PROMPT = ('An anime-style girl with long flowing orange hair, a sunflower hair ornament and a white floral long dress stands in the center against a plain solid green screen background. She smiles warmly and gently at the camera and nods politely, then gracefully flicks open the folding fan in her hands '
          'and holds it up beside her shoulder, showing the fan to the camera. Her long hair and the hem of her dress sway softly in the morning breeze. '
          'She keeps her clean 2D anime illustration style throughout, the background stays a flat uniform chroma-key green with no objects. Static camera, gentle elegant movements.')
NEG = ('background objects, scenery, shadows on background, realistic human face, 3d render, deformed hands, extra fingers, extra people, blurry, flicker, text, watermark, subtitles, style change')
# 讲解版（用户 11-22：片头要用讲解时的动作）：面向镜头边说边做手势，再侧身用手掌示意画面左侧（后期在那里浮现 GitHub 卡片）
PROMPT_TALK = ('An anime-style girl with long flowing orange hair, a sunflower hair ornament and a white floral long dress stands in the center against a plain solid green screen background, '
          'holding a closed folding fan in her left hand. She talks to the camera like a friendly presenter introducing a video: her mouth moves as she speaks, '
          'she smiles gently and makes graceful open-palm explaining gestures with her right hand, then turns slightly and extends her right hand palm-up toward the left side of the frame, '
          'as if presenting something appearing there, and nods. Her long hair and dress sway softly. She keeps her clean 2D anime illustration style throughout, '
          'the background stays a flat uniform chroma-key green with no objects. Static camera, gentle elegant movements.')
if os.environ.get('INTRO_STYLE') == 'talk': PROMPT = PROMPT_TALK
TAG = os.environ.get('INTRO_TAG', 'intro_v')
img = sys.argv[1]; seeds = [int(x) for x in sys.argv[2:]] or [11, 29]
for k, sd in enumerate(seeds, 1):
    sets = {M['image']: img, M['prompt']: PROMPT, M['negative']: NEG, M['frames']: 81, M['width']: 832, M['height']: 480, M['seed']: sd}
    sets.update(M.get('extra', {}))
    comfy_run.run(M['workflow'], '%s%d' % (TAG, k), sets, timeout=1800)
print('INTRO VIDEO DONE', flush=True)
