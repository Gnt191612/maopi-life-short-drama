# -*- coding: utf-8 -*-
"""云端第一步（写实化实例，ComfyUI 已启动）：摸清镜像里有什么，几秒钟跑完，结果很小，下载回本地后据此填 video_map.json。
输出 /root/v11_out/probe.json 与 probe.txt：
  - GPU、显存、磁盘
  - 每个工作流：节点类型统计、图片/视频输入节点（节点号.输入名）、提示词节点（节点号 + 前 80 字）、种子/帧数/分辨率节点、引用的模型文件
  - 模型目录里有哪些文件（checkpoints / diffusion_models / unet / loras / vae / text_encoders / clip_vision）
用法：python3 probe_comfy.py"""
import os, json, subprocess, glob
WFDIR = '/root/ComfyUI/user/default/workflows/'
MDIR = '/root/ComfyUI/models'
OUT = '/root/v11_out'; os.makedirs(OUT, exist_ok=True)
IMG_T = ('LoadImage', 'LoadImageMask', 'Image Load')
VID_T = ('VHS_LoadVideo', 'VHS_LoadVideoPath', 'LoadVideo', 'Load Video')
TXT_KEYS = ('text', 'prompt', 'positive', 'negative', 'string')
NUM_KEYS = ('seed', 'noise_seed', 'length', 'num_frames', 'frames', 'frame_count', 'width', 'height', 'fps', 'frame_rate', 'steps', 'cfg', 'batch_size')

def sh(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e: return str(e)

def wf_summary(path):
    w = json.load(open(path, encoding='utf-8'))
    nodes = w.get('nodes', [])
    types = {}
    for n in nodes: types[n['type']] = types.get(n['type'], 0) + 1
    imgs, vids, txts, nums, models = [], [], [], [], set()
    for n in nodes:
        t = n['type']; vals = n.get('widgets_values'); title = n.get('title', '')
        if any(k in t for k in IMG_T): imgs.append('%s %s %s' % (n['id'], t, title))
        if any(k in t for k in VID_T) or 'Video' in t and 'Load' in t: vids.append('%s %s %s' % (n['id'], t, title))
        if isinstance(vals, list):
            for v in vals:
                if isinstance(v, str) and len(v) > 12 and ('Text' in t or 'Prompt' in t or 'CLIP' in t or 'Encode' in t or 'String' in t):
                    txts.append('%s %s %s | %s' % (n['id'], t, title, v[:80].replace('\n', ' ')))
                if isinstance(v, str) and v.lower().endswith(('.safetensors', '.ckpt', '.gguf', '.pth', '.bin')): models.add(v)
        if isinstance(vals, dict):
            for k, v in vals.items():
                if isinstance(v, str) and v.lower().endswith(('.safetensors', '.ckpt', '.gguf', '.pth')): models.add(v)
        for i in n.get('inputs', []):
            if i.get('widget') and any(k in i['name'] for k in NUM_KEYS): nums.append('%s %s.%s' % (n['id'], t, i['name']))
    return dict(nodes=len(nodes), types=types, image_inputs=imgs, video_inputs=vids, prompts=txts, numeric=nums[:40], models=sorted(models),
                mode_off=[n['id'] for n in nodes if n.get('mode') in (2, 4)])

def main():
    res = dict(gpu=sh('nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader'), disk=sh('df -h /root | tail -1'),
               comfy_up=sh('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8188/system_stats'), workflows={}, models={})
    for p in sorted(glob.glob(WFDIR + '*.json')):
        try: res['workflows'][os.path.basename(p)] = wf_summary(p)
        except Exception as e: res['workflows'][os.path.basename(p)] = {'error': str(e)}
    for d in ('checkpoints', 'diffusion_models', 'unet', 'loras', 'vae', 'text_encoders', 'clip', 'clip_vision', 'controlnet', 'upscale_models'):
        fs = glob.glob(os.path.join(MDIR, d, '**', '*.*'), recursive=True)
        res['models'][d] = ['%s (%.1f GB)' % (os.path.relpath(f, os.path.join(MDIR, d)), os.path.getsize(f) / 1e9) for f in fs if os.path.isfile(f)]
    json.dump(res, open(os.path.join(OUT, 'probe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'probe.txt'), 'w', encoding='utf-8') as f:
        f.write('GPU %s\nDISK %s\nCOMFY %s\n\n' % (res['gpu'], res['disk'], res['comfy_up']))
        for name, s in res['workflows'].items():
            f.write('== %s  (%s 节点)\n' % (name, s.get('nodes')))
            for k in ('image_inputs', 'video_inputs', 'prompts', 'numeric', 'models'):
                for x in s.get(k, []): f.write('   %-13s %s\n' % (k, x))
        f.write('\n== 模型\n')
        for d, fs in res['models'].items():
            for x in fs: f.write('   %-16s %s\n' % (d, x))
    print('PROBE DONE', len(res['workflows']), 'workflows', flush=True)

if __name__ == '__main__':
    main()
