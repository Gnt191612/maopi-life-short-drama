# -*- coding: utf-8 -*-
"""把 GLB 包成人物审阅器用的 viewer/models/<id>.js（base64，双击 html 离线加载）。
云端只传 GLB（比 .js 小 1/4），到本地再包。格式与 blender/export_viewer.py 输出的一致。
python viewer/glb_to_js.py <glb 文件 ...>   （文件名即角色代号，如 classB.glb）"""
import os, sys, base64
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models'); os.makedirs(OUT, exist_ok=True)
for p in sys.argv[1:]:
    cid = os.path.splitext(os.path.basename(p))[0]
    data = base64.b64encode(open(p, 'rb').read()).decode('ascii')
    open(os.path.join(OUT, cid + '.js'), 'w', encoding='ascii').write("window.V11_MODELS=window.V11_MODELS||{};V11_MODELS['%s']='%s';\n" % (cid, data))
    print('JS OK', cid)
