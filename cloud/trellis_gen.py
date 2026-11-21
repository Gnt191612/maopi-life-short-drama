# -*- coding: utf-8 -*-
"""在仙宫云 TRELLIS.2 镜像实例上运行：一张照片 → 带贴图的 3D 模型（GLB）。
用法（先 source 环境，见 trellis_gen.sh）：python trellis_gen.py <输入图> <输出.glb> [种子] [分辨率 512|1024|1536]
流程与镜像自带 app.py 一致：去背景 → 居中裁切 → 采样（几何 + 贴图）→ 重网格化、减面、烘焙贴图 → GLB"""
import os, sys
sys.path.insert(0, '/root/TRELLIS.2'); os.chdir('/root/TRELLIS.2')
import numpy as np, torch
from PIL import Image
from trellis2.pipelines import Trellis2ImageTo3DPipeline
from trellis2.pipelines.rembg.RembgWrapper import RembgWrapper
import o_voxel

src, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
res = sys.argv[4] if len(sys.argv) > 4 else '1024'
pipe = Trellis2ImageTo3DPipeline.from_pretrained('microsoft/TRELLIS.2-4B')
pipe.rembg_model = RembgWrapper('u2net'); pipe.low_vram = os.environ.get('LOW_VRAM') == '1'; pipe.cuda(); pipe.rembg_model.cuda()
# 24G 卡实测：1024 不论开不开低显存都爆显存；512 + 低显存导出的是一团碎片（疑似低显存模式的问题），所以默认不开

def preprocess(im):
    if max(im.size) > 1024: s = 1024 / max(im.size); im = im.resize((int(im.width * s), int(im.height * s)), Image.Resampling.LANCZOS)
    o = pipe.rembg_model(im.convert('RGB')); a = np.array(o)[:, :, 3]
    ys, xs = np.argwhere(a > 0.8 * 255).T
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2; sz = max(xs.max() - xs.min(), ys.max() - ys.min())
    o = o.crop((cx - sz // 2, cy - sz // 2, cx + sz // 2, cy + sz // 2))
    arr = np.array(o).astype(np.float32) / 255; arr = arr[:, :, :3] * arr[:, :, 3:4]
    return Image.fromarray((arr * 255).astype(np.uint8))

img = preprocess(Image.open(src)); img.save(out.replace('.glb', '_input.png'))
outputs, latents = pipe.run(img, seed=seed, preprocess_image=False,
                            pipeline_type={'512': '512', '1024': '1024_cascade', '1536': '1536_cascade'}[res], return_latent=True)
mesh = outputs[0]; mesh.simplify(16777216)
glb = o_voxel.postprocess.to_glb(vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs, coords=mesh.coords,
                                 attr_layout=pipe.pbr_attr_layout, grid_size=latents[2], aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                                 decimation_target=300000, texture_size=2048, remesh=True, remesh_band=1, remesh_project=0, use_tqdm=False)
glb.export(out, extension_webp=True)
print('GLB OK', out, os.path.getsize(out), flush=True)
