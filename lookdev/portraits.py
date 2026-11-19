# -*- coding: utf-8 -*-
"""照片级定妆照：白模底图 + 深度控制（锁定脸型/角度/身材）+ 文字描述（外观）+ IP-Adapter（正脸生成后作为其余角度的长相参考），
模型：RealVisXL V5.0（OpenRAIL++）、ControlNet Depth SDXL、IP-Adapter Plus Face SDXL（Apache-2.0）、SDXL VAE fp16 fix（MIT）。
输出 assets/lookdev/<cid>_<view>.png —— 云端视频写实化时作为每个角色的长相参考，保证全片同一个人始终是同一张脸。
运行：<装了 diffusers 的 python> lookdev/portraits.py [角色id ...]   （环境变量 V11_SDXL_DIR 指向模型目录）
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import torch
from PIL import Image

M = os.environ.get('V11_SDXL_DIR') or os.path.join(config.TOOLS, 'sdxl')
SRC = os.path.join(config.ROOT, 'build', 'lookdev'); OUT = os.path.join(config.ROOT, 'assets', 'lookdev'); os.makedirs(OUT, exist_ok=True)
STYLE = ('RAW photo, realistic photograph, natural skin texture with pores, soft natural light, 85mm lens, shallow depth of field, '
         'plain light grey studio background, high detail, film grain')
NEG = ('cartoon, anime, 3d render, cgi, doll, plastic skin, smooth skin, airbrushed, painting, illustration, deformed, extra fingers, '
       'blurry, lowres, watermark, text, makeup, heavy retouch')
LOOK = {   # 外观描述（与剧本人物设定、白模服装颜色一致）
 'lin':    '20 year old chubby Chinese male university student, round full face, small eyes, slightly double chin, short black messy hair with bangs, '
           'wearing a dark grey sweatshirt and navy jeans, shy and good-natured expression',
 'chen':   '21 year old slim tall Chinese male university student, oval face with defined cheekbones, thin round metal glasses, short neat black hair with side part, '
           'wearing a white button-up shirt and black trousers, calm and composed expression',
 'zhou':   '22 year old lean Chinese male graduate student, angular rectangular face, high cheekbones, slight eye bags, very short buzz-cut black hair, '
           'wearing an olive green casual jacket and black trousers, gentle and steady expression',
 'wang':   '38 year old Chinese male university counselor, square face, laugh lines, short black hair, '
           'wearing a light blue shirt and dark grey trousers, warm and sincere expression',
 'mom':    '50 year old Chinese mother, round kind face, laugh lines, short wavy bob haircut with dark brown hair, '
           'wearing a beige knitted sweater, warm loving smile',
 'classA': '20 year old athletic Chinese male university student, diamond-shaped face, prominent chin, slightly tanned skin, short black hair, '
           'wearing a dark navy sports jacket, cheeky grin',
 'classB': '20 year old slim Chinese female university student, oval face, bright eyes, black hair in a ponytail, '
           'wearing a cream-colored turtleneck sweater and light jeans, gentle shy expression',
}
VIEW_TXT = {'face_front': 'close-up portrait, facing the camera', 'face_34': 'close-up portrait, three-quarter view',
            'face_side': 'close-up portrait, side profile', 'half': 'half-body portrait, standing', 'full': 'full-body photo, standing, whole body visible'}
ORDER = ['face_front', 'face_34', 'face_side', 'half', 'full']

def main():
    from diffusers import StableDiffusionXLControlNetImg2ImgPipeline, ControlNetModel, AutoencoderKL
    from transformers import CLIPVisionModelWithProjection
    cn = ControlNetModel.from_pretrained(os.path.join(M, 'controlnet-depth-sdxl'), torch_dtype=torch.float16, variant='fp16')
    vae = AutoencoderKL.from_pretrained(os.path.join(M, 'sdxl-vae-fp16-fix'), torch_dtype=torch.float16)
    enc = CLIPVisionModelWithProjection.from_pretrained(os.path.join(M, 'IP-Adapter', 'models', 'image_encoder'), torch_dtype=torch.float16)
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(os.path.join(M, 'RealVisXL_V5.0'), controlnet=cn, vae=vae,
                                                                      image_encoder=enc, torch_dtype=torch.float16, variant='fp16')
    pipe.load_ip_adapter(os.path.join(M, 'IP-Adapter'), subfolder='sdxl_models', weight_name='ip-adapter-plus-face_sdxl_vit-h.safetensors')
    pipe.enable_model_cpu_offload()                   # 8 GB 显卡：按需把模块放上显存，其余留在内存
    pipe.enable_vae_tiling()
    ids = sys.argv[1:] or list(LOOK)
    for cid in ids:
        ref = None
        for view in ORDER:
            base = os.path.join(SRC, '%s_%s.png' % (cid, view)); dep = os.path.join(SRC, '%s_%s_depth.png' % (cid, view))
            if not (os.path.exists(base) and os.path.exists(dep)): continue
            init = Image.open(base).convert('RGB'); depth = Image.open(dep).convert('RGB').resize(init.size)
            g = torch.Generator('cpu').manual_seed(1000 + sum(map(ord, cid)))
            if ref is None: pipe.set_ip_adapter_scale(0.0)            # 正脸：只靠文字 + 白模，定下这个人的长相
            else: pipe.set_ip_adapter_scale(0.65)                    # 其余角度：参考正脸，保证是同一个人
            img = pipe(prompt='%s, %s, %s' % (LOOK[cid], VIEW_TXT[view], STYLE), negative_prompt=NEG, image=init, control_image=depth,
                       ip_adapter_image=ref if ref is not None else init, strength=0.62, controlnet_conditioning_scale=0.55,
                       num_inference_steps=32, guidance_scale=5.5, generator=g).images[0]
            p = os.path.join(OUT, '%s_%s.png' % (cid, view)); img.save(p)
            if view == 'face_front': ref = img
            print('PORTRAIT OK', cid, view, flush=True)

if __name__ == '__main__':
    main()
