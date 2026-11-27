# -*- coding: utf-8 -*-
"""全片逐帧统一长相（本地 GPU）：每帧检测人脸 → 认出是本镜头哪个角色 → InsightFace inswapper 换成人物库标准脸
→ GFPGAN 1.4 把换好的脸修复到 512 清晰度 → 羽化贴回原画面。
2026-11-25：云端只在关键帧换脸，视频生成过程中脸会慢慢走样，不同镜头里的林晓、陈瑶长得对不上（用户指出）。
云端关键帧换脸仍然保留：它定下整个人（发型、体型、衣着、性别）；这里只统一五官。
模型（不进仓库）：.tools/models/faceswap/inswapper_128.onnx、gfpgan_1.4.onnx（facefusion-assets 公开发布）
用法：python cloud/face_unify.py <合并后的结果目录（含 real/<任务id>/frame_####.png）> [任务id前缀 ...]
      处理完的帧原地覆盖，并重新编码 real/<任务id>.mp4；已处理的镜头记在 real/<任务id>/.unified，重跑会跳过"""
import os, sys, json, glob, subprocess, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import torch   # 先加载 torch 自带的 CUDA/cuDNN 动态库，onnxruntime-gpu 才找得到
import onnxruntime as ort
import insightface
from insightface.app import FaceAnalysis
import config
PACK = os.path.join(ROOT, 'dist', 'cloud_pack'); M = os.path.join(ROOT, '.tools', 'models', 'faceswap')
PROV = ['CUDAExecutionProvider', 'CPUExecutionProvider']
app = FaceAnalysis(name='buffalo_l', providers=PROV, allowed_modules=['detection', 'recognition', 'landmark_3d_68']); app.prepare(ctx_id=0, det_size=(640, 640))
swapper = insightface.model_zoo.get_model(os.path.join(M, 'inswapper_128.onnx'), providers=PROV)
so = ort.SessionOptions(); gfp = ort.InferenceSession(os.path.join(M, 'gfpgan_1.4.onnx'), so, providers=PROV)
GIN = gfp.get_inputs()[0].name
FFHQ = np.array([[0.37691676, 0.46864664], [0.62285697, 0.46912813], [0.50123859, 0.61331904], [0.39308822, 0.72541100], [0.61150205, 0.72490465]], np.float32) * 512
MASK = np.zeros((512, 512), np.float32); cv2.ellipse(MASK, (256, 270), (190, 225), 0, 0, 360, 1, -1); MASK = cv2.GaussianBlur(MASK, (0, 0), 18)

def ref_faces():
    out = {}
    for p in sorted(glob.glob(os.path.join(PACK, 'refs', 'canon_*.jpg'))):
        c = os.path.basename(p)[6:-4]; im = cv2.imread(p)
        for pad in (0, 0.35, 0.8):
            b = int(max(im.shape[:2]) * pad); im_ = cv2.copyMakeBorder(im, b, b, b, b, cv2.BORDER_CONSTANT, value=(128, 128, 128)) if b else im
            s = 900 / max(im_.shape[:2]); fs = app.get(cv2.resize(im_, None, fx=s, fy=s))
            if fs: out[c] = max(fs, key=lambda f: f.bbox[2] - f.bbox[0]); break
    return out
REF = ref_faces(); print('标准脸', sorted(REF), flush=True)

def enhance(img, face, blend=0.8):
    Mx = cv2.estimateAffinePartial2D(face.kps.astype(np.float32), FFHQ, method=cv2.LMEDS)[0]
    crop = cv2.warpAffine(img, Mx, (512, 512), borderMode=cv2.BORDER_REPLICATE)
    x = (crop[:, :, ::-1].astype(np.float32) / 255.0 - 0.5) / 0.5
    y = gfp.run(None, {GIN: x.transpose(2, 0, 1)[None]})[0][0]
    y = ((np.clip(y.transpose(1, 2, 0), -1, 1) + 1) / 2 * 255)[:, :, ::-1]
    y = crop * (1 - blend) + y * blend
    inv = cv2.invertAffineTransform(Mx); h, w = img.shape[:2]
    back = cv2.warpAffine(y.astype(np.float32), inv, (w, h)); m = cv2.warpAffine(MASK, inv, (w, h))[:, :, None]
    return (img * (1 - m) + back * m).clip(0, 255).astype(np.uint8)

def assign_by_pos(faces, heads, w, h):
    """按白模头部位置认人：检测到的脸和白模里同一帧各角色头部投影最近的配对（白模里谁在画面哪里是确定的）"""
    pairs = []
    for i, f in enumerate(faces):
        cx, cy = (f.bbox[0] + f.bbox[2]) / 2 / w, (f.bbox[1] + f.bbox[3]) / 2 / h
        for c, (x, y, _) in heads.items():
            if c in REF: pairs.append((((cx - x) ** 2 + (cy - y) ** 2) ** 0.5, i, c))
    pairs.sort(); used_f, used_c, out = set(), set(), {}
    for d, i, c in pairs:
        if i in used_f or c in used_c or d > 0.22: continue   # 视频跑偏太多（离白模位置超过画面 22%）的不按位置配
        out[i] = c; used_f.add(i); used_c.add(c)
    return out

def assign(faces, chars):
    """贪心：相似度最高的一对先配，一个角色只给一张脸；明显不是本镜头角色的脸（路人、同学）不换"""
    pairs = []
    for i, f in enumerate(faces):
        for c in chars:
            if c in REF: pairs.append((float(np.dot(f.normed_embedding, REF[c].normed_embedding)), i, c))
    pairs.sort(reverse=True); used_f, used_c, out = set(), set(), {}
    for s, i, c in pairs:
        if i in used_f or c in used_c or s < 0.10: continue
        out[i] = c; used_f.add(i); used_c.add(c)
    return out

def process(tdir, tid, heads=None):
    tj = os.path.join(PACK, tid, 'task.json')
    tk = json.load(open(tj, encoding='utf-8')) if os.path.exists(tj) else {}
    chars = tk.get('characters', []); bg = tk.get('bg_face')   # bg_face：没配上主角的脸换成这个背景人物（s02_01_0450 视频多画了一个和林晓很像的人，换成同学甲，避免看成两个林晓）
    if not chars or os.path.exists(os.path.join(tdir, '.unified')): return 0
    frames = sorted(glob.glob(os.path.join(tdir, 'frame_*.png'))); n = 0
    for p in frames:
        img = cv2.imread(p); faces = []
        for f in app.get(img):
            if f.det_score < 0.55 or f.bbox[2] - f.bbox[0] < 36: continue
            if getattr(f, 'pose', None) is not None and abs(float(f.pose[1])) > 70: continue   # 接近正侧面不换（换出来容易错位）
            faces.append(f)
        if not faces: continue
        hd = (heads or {}).get(str(int(os.path.basename(p)[6:10])))
        got = assign_by_pos(faces, hd, img.shape[1], img.shape[0]) if hd and len(chars) > 1 else {}
        if len(got) < len(faces):   # 位置配不上的脸，再按长相在剩下的角色里配
            rest = [k for k in range(len(faces)) if k not in got]; left = [c for c in chars if c not in got.values()]
            if len(chars) == 1 and not got and chars[0] in REF:   # 单人镜头：脸最大的是主角（多出来的路人往往站在后面），不按相似度，免得把主角让给长得像的路人
                got[max(range(len(faces)), key=lambda k: faces[k].bbox[2] - faces[k].bbox[0])] = chars[0]
            else:
                for k, c in assign([faces[k] for k in rest], left).items(): got[rest[k]] = c
        if bg in REF:
            for k in range(len(faces)):
                if k not in got: got[k] = bg
        for i, c in got.items():
            img = swapper.get(img, faces[i], REF[c], paste_back=True)
            img = enhance(img, faces[i]); n += 1
        cv2.imwrite(p, img)
    if frames:
        f0 = int(os.path.basename(frames[0])[6:10])
        subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-framerate', '24', '-start_number', str(f0), '-i', os.path.join(tdir, 'frame_%04d.png'),
                        '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', tdir + '.mp4'], check=True)
    open(os.path.join(tdir, '.unified'), 'w').write(str(n))
    return n

if __name__ == '__main__':
    real = os.path.join(sys.argv[1], 'real'); pre = sys.argv[2:]
    for tdir in sorted(d for d in glob.glob(os.path.join(real, '*')) if os.path.isdir(d)):
        tid = os.path.basename(tdir)
        if pre and not any(tid.startswith(x) for x in pre): continue
        hp = os.path.join(sys.argv[1], 'heads', tid + '.json')
        print(tid, '换脸', process(tdir, tid, json.load(open(hp)) if os.path.exists(hp) else None), flush=True)
    print('FACE UNIFY DONE', flush=True)
