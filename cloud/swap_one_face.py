# -*- coding: utf-8 -*-
"""多人镜头里只给一个人换脸（自动流程多人不换脸，怕换错人；11-27 s08_01_0001 陈瑶被画成长发女生）。
用文字指明是哪一个人（位置 + 衣着），换完必须人工放大核对没有换错人。原图留 kf_bad/。
用法（云端）：python swap_one_face.py <镜头id> <角色> "<这个人的位置和衣着>" """
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_run, keyframes as K
tid, cid, who = sys.argv[1:4]
src = os.path.join(K.OUTK, tid + '.png'); os.makedirs('/root/v11_out/kf_bad', exist_ok=True)
shutil.copy(src, '/root/v11_out/kf_bad/%s.before_%s.png' % (tid, cid)); shutil.copy(src, os.path.join(K.INP, 'kfone_%s.png' % tid))
ref = 'canonface_%s.jpg' % cid if os.path.exists(os.path.join(K.INP, 'canonface_%s.jpg' % cid)) else 'canon_%s.jpg' % cid
res = comfy_run.run(K.WF_SWAP, 'kfone_%s_%s' % (tid, cid), {'3.image': ref, '10.image': 'kfone_%s.png' % tid, '39.text': K.SWAP.format(who='这个人：' + who)})
if res: shutil.copy(res, src); print('换脸完成', tid, cid, res)
else: print('换脸失败', tid)
