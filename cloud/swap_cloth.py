# -*- coding: utf-8 -*-
"""首帧里某人的衣服颜色/款式不对、提示词多次改不过来时（白模衣服太暗），用 Qwen 人物替换只换衣服（11-27 s05_01_0001 周明远三次都是深灰卫衣）。
图1 = 角色定妆照（带定稿衣服），图2 = 当前首帧；指令只换指定那个人的上衣，其他全部不变。结果覆盖 kf/<id>.png（原图留 kf_bad/）。
用法（云端）：python swap_cloth.py <镜头id> <角色> "<这个人在画面里的位置描述>" "<衣服描述>"
"""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run
INP = '/root/ComfyUI/input'; OUTK = '/root/v11_out/kf'
WF_SWAP = os.environ.get('V11_WF_SWAP', '【推荐】Qwen2.1-人物替换.json')
tid, cid, where, cloth = sys.argv[1:5]
src = os.path.join(OUTK, tid + '.png'); os.makedirs('/root/v11_out/kf_bad', exist_ok=True)
shutil.copy(src, '/root/v11_out/kf_bad/%s.before_cloth.png' % tid); shutil.copy(src, os.path.join(INP, 'kfcloth_%s.png' % tid))
txt = ('把图2中%s的上衣换成图1中这个人穿的%s：颜色、材质、款式与图1一致。'
       '只换这一件上衣，图2中这个人的脸、发型、姿势和裤子不变，画面里其他人、背景、构图、景别和光影全部保持不变，不要增加或减少人物。') % (where, cloth)
res = comfy_run.run(WF_SWAP, 'kfcloth_%s' % tid, {'3.image': 'canon_%s.jpg' % cid, '10.image': 'kfcloth_%s.png' % tid, '39.text': txt})
if res: shutil.copy(res, src); print('换衣完成', tid, res)
else: print('换衣失败', tid)
