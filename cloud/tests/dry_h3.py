# -*- coding: utf-8 -*-
"""本地演练 video_h3.py（不开机、不花钱）：伪造一份 ComfyUI /object_info（节点名和控件顺序照官方模板 cloud/wf_templates），
把 comfy_run._get 换成假的，用 --dry 跑一遍构图，检查脚本本身有没有错、节点连线是否齐全。
用法：python cloud/tests/dry_h3.py [video_h3.py 的参数...]   例：python cloud/tests/dry_h3.py --only s06_01_0626 --mode fl --pika"""
import os, sys, json, types, runpy, tempfile, shutil, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'cloud'))
C = lambda *files: [list(files)]
FILES = dict(
    unet=['minimax_h3_fl2va_pruned_int8_convrot.safetensors', 'minimax_h3_fl2va_pruned_bf16.safetensors', 'minimax_h3_ref2va_pruned_int8_convrot.safetensors'],
    clip=['qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'], vae=['minimax_h3_video_vae_int8_convrot.safetensors', 'minimax_h3_audio_vae_fp32.safetensors'],
    patch=['minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors', 'minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot.safetensors'],
    lora=['minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors', 'minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors',
          'H3/pika_h3_flex_fl2va_comfy_bf16.safetensors', 'H3/pika_h3_flex_ref2va_comfy_bf16.safetensors', 'H3/pika_h3_flex_turbo_4step_fl2va.safetensors'])
def I(**req): return {'input': {'required': req}}
INFO = {
    'UNETLoader': I(unet_name=[FILES['unet']], weight_dtype=[['default']]),
    'CLIPLoader': I(clip_name=[FILES['clip']], type=[['minimax', 'wan']], device=[['default']]),
    'VAELoader': I(vae_name=[FILES['vae']]),
    'ModelPatchLoader': I(name=[FILES['patch']]),
    'LoraLoaderModelOnly': I(model=['MODEL'], lora_name=[FILES['lora']], strength_model=['FLOAT']),
    'LoadVideo': I(file=['COMBO'], format=['COMBO']), 'GetVideoComponents': I(video=['VIDEO']),
    'LoadImage': I(image=['COMBO'], upload=['COMBO']), 'LoadAudio': I(audio=['COMBO']),
    'MiniMaxH3FunControlNetApply': I(model=['MODEL'], model_patch=['MODEL_PATCH'], vae=['VAE'], control_video=['IMAGE'], strength=['FLOAT'], start_percent=['FLOAT'], end_percent=['FLOAT']),
    'MiniMaxH3ImageToVideo': I(clip=['CLIP'], vae=['VAE'], first_frame=['IMAGE'], prompt=['STRING'], width=['INT'], height=['INT'], length=['INT']),
    'MiniMaxH3ReferenceToVideo': I(clip=['CLIP'], vae=['VAE'], audio_vae=['VAE'], prompt=['STRING'], width=['INT'], height=['INT'], length=['INT'], mode=[['match']]),
    'BasicGuider': I(model=['MODEL'], conditioning=['CONDITIONING']), 'KSamplerSelect': I(sampler_name=[['res_multistep', 'lcm']]), 'ManualSigmas': I(sigmas=['STRING']),
    'BasicScheduler': I(model=['MODEL'], scheduler=[['simple']], steps=['INT'], denoise=['FLOAT']),
    'RandomNoise': {'input': {'required': {'noise_seed': ['INT', {'control_after_generate': True}]}}},
    'SamplerCustomAdvanced': I(noise=['NOISE'], guider=['GUIDER'], sampler=['SAMPLER'], sigmas=['SIGMAS'], latent_image=['LATENT']),
    'VAEDecode': I(samples=['LATENT'], vae=['VAE']), 'SaveImage': I(images=['IMAGE'], filename_prefix=['STRING']),
    'VAEDecodeAudio': I(samples=['LATENT'], vae=['VAE']), 'SaveAudio': I(audio=['AUDIO'], filename_prefix=['STRING']),
}
import comfy_run
comfy_run._get = lambda path: INFO if path == '/object_info' else {}
tmp = tempfile.mkdtemp(prefix='dryh3_')
pack = os.path.join(tmp, 'cloud_pack'); kf = os.path.join(tmp, 'kf'); inp = os.path.join(tmp, 'input'); os.makedirs(kf); os.makedirs(inp)
ids = [a for a in sys.argv[1:]]; only = ids[ids.index('--only') + 1].split(',') if '--only' in ids else ['s06_01_0626']
with zipfile.ZipFile(os.path.join(ROOT, 'dist', 'slim_trial_h3.zip')) as z: z.extractall(tmp)
for t in only:
    shutil.copy(os.path.join(ROOT, 'dist', 'cloud_pack', t, 'first.png'), os.path.join(kf, t + '.png'))
src = open(os.path.join(ROOT, 'cloud', 'video_h3.py'), encoding='utf-8').read()
src = src.replace("INP = '/root/ComfyUI/input'; KF = '/root/v11_out/kf'; TMP = '/root/v11_out/htmp'", "INP = %r; KF = %r; TMP = %r" % (inp, kf, os.path.join(tmp, 'htmp')))
src = src.replace("'/root/v11_out/h3_progress.log'", repr(os.path.join(tmp, 'progress.log'))).replace("default='/root/v11_out/h3'", "default=%r" % os.path.join(tmp, 'out'))
sys.argv = ['video_h3.py', pack] + (sys.argv[1:] if '--only' in sys.argv else ['--only', ','.join(only)] + sys.argv[1:]) + ['--dry']
ns = {'__name__': '__main__', '__file__': os.path.join(ROOT, 'cloud', 'video_h3.py')}
exec(compile(src, 'video_h3.py', 'exec'), ns)
print('DRY OK', tmp)

