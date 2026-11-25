# -*- coding: utf-8 -*-
"""精简补跑包（本地）：只带云端真正用到的文件 —— task.json、first.png（关键帧来源）、anchors.json + anchor_*.png（锚点模式）、
出场角色的长相参考图。白模 beauty/depth/pose 视频现在的图生视频工作流用不到，不传（2026-11-25：实例空闲快自动关机，要尽快开跑）。
用法：python cloud/slim_pack.py <任务id,任务id,...> <输出 zip>"""
import os, sys, json, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'dist', 'cloud_pack')
ids = [x for x in sys.argv[1].split(',') if x]; out = sys.argv[2]
chars = set()
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    z.writestr('cloud_pack/manifest.json', json.dumps(dict(fps=24, size=[832, 480], tasks=ids), indent=1))
    for t in ids:
        td = os.path.join(PACK, t)
        for f in os.listdir(td):
            if f in ('task.json', 'first.png', 'anchors.json') or f.startswith('anchor_'):
                z.write(os.path.join(td, f), 'cloud_pack/%s/%s' % (t, f))
        chars |= set(json.load(open(os.path.join(td, 'task.json'), encoding='utf-8')).get('characters', []))
    for f in os.listdir(os.path.join(PACK, 'refs')):
        if any(f.endswith('_%s.jpg' % c) for c in chars): z.write(os.path.join(PACK, 'refs', f), 'cloud_pack/refs/' + f)
print('SLIM', out, len(ids), '个镜头', '%.1f MB' % (os.path.getsize(out) / 1e6))
