# -*- coding: utf-8 -*-
"""把这部短剧每个镜头实际用的提示词导出来，供开机前逐个审查（本地运行，输出在 build/review/prompts/，不入库）：
  build/review/prompts/全片提示词.md   —— 每个镜头一节：剧情动作（中文 act）、节拍画面描述（英文）、首帧中文前缀 + kf_hint、H3 视频最终提示词
  build/review/prompts/prompts.json   —— 同样内容的机器可读版（下一部片可直接改了再用）
  build/review/prompts/角色与声音.md   —— 每个角色的中英文外貌描述、声音特征
  build/review/prompts/场景与运镜.md   —— 每个场景的背景描述、环境音；白模运镜 → H3 官方运镜词
  build/review/prompts/风格与通用句.md —— 风格、质感、真人动作、关键帧换脸指令等通用句
提示词的写法规则和踩过的坑见 docs/prompts/README.md。改了剧本、人物或 shot_prompts.py 后重新运行一遍即可。
用法：python cloud/export_prompts.py"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import segments as S, looks, backgrounds as B, h3_prompt as HP, shot_prompts as SP
from story_scenes import SCENES
OUT = os.path.join(ROOT, 'build', 'review', 'prompts'); os.makedirs(OUT, exist_ok=True)   # 本片专属，只在本地供审查；通用写法和模板在 docs/prompts/
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
BEAT = {b['id']: b for sc in SCENES for b in sc['beats']}

def kf_prefix(task):   # 与 keyframes.py make_kf 里的 tag() 相同逻辑（首帧「二转三」读的中文前缀）
    chars = task.get('characters', []); L = looks.LOOK
    def tag(c):
        parts = L[c].split('，'); s = parts[0]
        keep = [p for p in parts[1:] if '发' in p and len(p) < 24] + [p for p in parts[1:] if p.startswith('穿')]
        if len(chars) > 1: keep += [p for p in parts[1:] if '眼镜' in p]
        return s + ('（' + '，'.join(keep) + '）' if keep else '')
    pre = ('画面中的人物是' + '、'.join(tag(c) for c in chars if c in L) + '，不要改变人物的性别、人数和衣着。') if chars else ''
    return pre + task.get('kf_hint', '')

rows = []
for tj in sorted(glob.glob(os.path.join(PACK, '*', 'task.json'))):
    t = json.load(open(tj, encoding='utf-8'))
    vj = os.path.join(os.path.dirname(tj), 'voice.json'); lines = json.load(open(vj, encoding='utf-8')) if os.path.exists(vj) else None
    acts = []
    for b in t.get('beats', []):
        a = BEAT.get(b, {}).get('act', '')
        acts.append('；'.join(a) if isinstance(a, list) else a)
    rows.append(dict(id=t['id'], segment=t['segment'], set=t.get('set', ''), frames=t['frames'], seconds=round(t['n'] / 24, 2), move=t.get('move'),
                     characters=t.get('characters', []), act_zh=[a for a in acts if a], beat_en=t['prompt'].split('. Background:')[0],
                     overridden=t['id'] in SP.EN, kf_prefix_zh=kf_prefix(t), h3_prompt=HP.build(t, 'i2va', lines, False),
                     h3_prompt_speech=HP.build(t, 'i2va', lines, True) if lines else None,
                     lines=[dict(speaker=v['speaker'], text=v['text'], start=v['start']) for v in (lines or [])]))
json.dump(rows, open(os.path.join(OUT, 'prompts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

md = ['# 全片提示词（%d 个镜头）' % len(rows), '', '> 由 `cloud/export_prompts.py` 生成，不要手改；改源头（`story/story_scenes.py`、`cloud/shot_prompts.py`、`cloud/h3_prompt.py`、人物库）后重新导出。',
      '> 每个镜头：剧情动作（中文，白模动作来源）→ 画面描述（英文，标「按镜头改写」的来自 shot_prompts.py）→ 首帧中文前缀（Krea2 二转三只读这一句）→ H3 视频提示词（官方格式）。', '']
for r in rows:
    md += ['## %s  （%s，%.1f 秒，运镜 %s，人物 %s）' % (r['id'], r['set'], r['seconds'], r['move'], '、'.join(looks.NAME.get(c, c) for c in r['characters']) or '无'), '']
    if r['act_zh']: md += ['- **剧情动作**：' + ' / '.join(r['act_zh'])]
    md += ['- **画面描述**%s：%s' % ('（按镜头改写）' if r['overridden'] else '', r['beat_en'])]
    if r['kf_prefix_zh']: md += ['- **首帧前缀**：' + r['kf_prefix_zh']]
    for v in r['lines']: md += ['- **台词** %.1fs %s：%s' % (v['start'], v['speaker'], v['text'])]
    md += ['', '```text', r['h3_prompt'], '```', '']
open(os.path.join(OUT, '全片提示词.md'), 'w', encoding='utf-8').write('\n'.join(md))

md = ['# 角色与声音', '', '> 来源：人物库 `characters/<cid>/character.py`（look / look_en）、`cloud/h3_prompt.py`（VOICE）。改外貌改人物库，云端读重新生成的 looks_gen.json。', '']
for c, n in looks.NAME.items():
    md += ['## %s（%s）' % (n, c), '', '- 中文（首帧）：' + looks.LOOK.get(c, ''), '- 英文（视频）：' + looks.LOOK_EN.get(c, ''), '- 声音：' + HP.VOICE.get(c, ''), '']
open(os.path.join(OUT, '角色与声音.md'), 'w', encoding='utf-8').write('\n'.join(md))

md = ['# 场景与运镜', '', '## 场景背景描述（`cloud/backgrounds.py`）', '']
for k in B.BG: md += ['- **%s**：%s' % (k, B.bg(k))]
md += ['', '## 场景环境音（`cloud/h3_prompt.py` SOUND / SET_SOUND）', '']
for k, v in HP.SOUND.items(): md += ['- **%s**：%s' % (k, v)]
md += ['', '| 场景 | 用的环境音 |', '|---|---|'] + ['| %s | %s |' % (k, v) for k, v in HP.SET_SOUND.items()]
md += ['', '## 运镜：白模机位类型 → H3 官方运镜词（类型 + 幅度 + 速度）', '', '| 白模 | 旧写法（已弃用） | H3 写法 |', '|---|---|---|']
md += ['| %s | %s | %s |' % (k, B.MOVE_EN.get(k, ''), v) for k, v in HP.CAMERA.items()]
md += ['', '景别识别：' + '、'.join(k for k, _ in HP.SHOT_SIZE)]
open(os.path.join(OUT, '场景与运镜.md'), 'w', encoding='utf-8').write('\n'.join(md))

import keyframes as KF
md = ['# 风格与通用句', '',
      '## H3 视频（英文，正面描述，不写负面）', '', '- 首帧对齐句（官方固定）：`%s`' % HP.ALIGN['i2va'], '- 真人动作：' + HP.LIFE, '- 质感：' + HP.QUALITY,
      '- 不说话的镜头：Nobody speaks in this shot; lips stay relaxed and closed except for natural breathing.',
      '- 说话（原生语音）：`... (S1) says with realistic lip articulation and no exaggerated mouth opening: <d>[Chinese] 原话</d>`', '',
      '## 首帧（Krea2 二转三，中文前缀）', '', '- 模板：画面中的人物是{每人：性别年龄体型（发型，衣着[，眼镜]）}、…，不要改变人物的性别、人数和衣着。{kf_hint}',
      '- kf_hint 写法：从左到右依次写每个人的位置、体型、衣着，最后写「画面里只有这 N 个人」。', '',
      '## 关键帧换脸（Qwen 人物替换，只用于单人镜头）', '', '- ' + KF.SWAP, '',
      '## 旧的风格句（图生视频时代，视频阶段已不用；首帧阶段仍可参考）', '', '- STYLE_EN：' + looks.STYLE_EN, '- NEG_EN：' + looks.NEG_EN]
open(os.path.join(OUT, '风格与通用句.md'), 'w', encoding='utf-8').write('\n'.join(md))
print('导出 %d 个镜头 → %s' % (len(rows), OUT))
