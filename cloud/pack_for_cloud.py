# -*- coding: utf-8 -*-
"""打包云端写实化任务（本地运行）：按镜头切换把全片切成若干「镜头任务」，每个任务一个文件夹：
  beauty.mp4（白模画面）、depth.mp4（深度控制）、pose.mp4（骨架控制）、task.json（帧范围、提示词、出场角色、长相参考图）
外加 refs/（每个角色的照片级定妆照）。输出 dist/cloud_pack/ 和 dist/cloud_pack.zip，上传到仙宫云实例即可。
用法：python cloud/pack_for_cloud.py [片段id ...]   （默认全片；先跑完预演渲染 V11_PREVIEW=1 python run_all.py 与骨架导出）
      --pose  先为缺骨架图的片段导出骨架（调用 Blender）
      --update 只重打命令行给出的片段，其余已打好的镜头任务保留
"""
import os, sys, json, glob, shutil, subprocess, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import segments as S

REN = os.environ.get('V11_PACK_RENDERS') or (os.path.join(config.ROOT, 'build', 'renders_preview')
                                            if os.path.isdir(os.path.join(config.ROOT, 'build', 'renders_preview')) else config.RENDERS)
OUT = os.path.join(config.ROOT, 'dist', 'cloud_pack')
sys.path.insert(0, os.path.join(config.ROOT, 'blender')); import charlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import backgrounds   # 每个场景的背景描述、运镜词
import shot_prompts   # 按镜头覆盖提示词和出场角色
REFS = os.path.join(config.ROOT, 'assets', 'identity')   # 旧位置；现在用 charlib.identity()（人物库优先）   # 2026-11-22 起：用户选定的标准长相照片 <cid>.png（原来是 assets/lookdev 的旧定妆照）
CID = S.CID
STYLE = ('photorealistic live-action film, shot on cinema camera, natural lighting, realistic skin texture, Chinese university campus, '
         'contemporary, 2020s, everyday clothing')

def encode(frames, out_mp4, fps=24):
    lst = out_mp4 + '.txt'
    open(lst, 'w', encoding='utf-8').write(''.join("file '%s'\nduration %.6f\n" % (f.replace('\\', '/'), 1 / fps) for f in frames))
    subprocess.run([config.FFMPEG, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-vf', 'fps=%d,scale=832:480:force_original_aspect_ratio=decrease,pad=832:480:(ow-iw)/2:(oh-ih)/2' % fps,
                    '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', out_mp4], check=True)
    os.remove(lst)

def face_crop(c, im):
    """标准长相照片只裁脸（不带头发、衣服）→ refs/canonface_<cid>.jpg：整人替换模型会把参考图的发型、衣服一起搬过来"""
    import cv2
    lp = charlib.identity(c, '_landmarks_full.json')
    if not os.path.exists(lp): return
    lm = json.load(open(lp, encoding='utf-8'))
    eR, eL = lm['eye_R'], lm['eye_L']; iod = ((eL[0] - eR[0]) ** 2 + (eL[1] - eR[1]) ** 2) ** 0.5
    xs = [x for k in ('contour_R', 'contour_L') for _, x in lm.get(k, [])] or [eR[0] - iod, eL[0] + iod]
    ey = (eR[1] + eL[1]) / 2
    x0, x1 = int(min(xs) - 0.12 * iod), int(max(xs) + 0.12 * iod); y0, y1 = int(ey - 0.8 * iod), int(lm['chin'][1] + 0.25 * iod)
    h, w = im.shape[:2]
    cv2.imwrite(os.path.join(OUT, 'refs', 'canonface_%s.jpg' % c), im[max(0, y0):min(h, y1), max(0, x0):min(w, x1)], [cv2.IMWRITE_JPEG_QUALITY, 95])

ONLY_BEATS = {b for b in os.environ.get('V11_RENDER_BEATS', '').split(',') if b}   # 和 shoot_segment.py 局部补拍用同一个变量

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    segs = [s for s in S.segments() if not args or s[0] in args]
    if '--update' in sys.argv and os.path.isdir(OUT):   # 只重打给定片段（其余镜头任务保留），补拍个别片段后不用全部重打
        for sid_ in ({s[0] for s in segs} if not ONLY_BEATS else ()):   # 局部补拍时只重打涉及这些拍的镜头（下面逐个删）
            for d_ in glob.glob(os.path.join(OUT, sid_ + '_*')): shutil.rmtree(d_, ignore_errors=True)
    elif os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'refs'), exist_ok=True)
    tasks = []; hd_jobs = {}
    for sid, scene, set_name, beats in segs:
        tl_p = os.path.join(config.SHOTS, sid + '_timeline.json'); cuts_p = os.path.join(config.SHOTS, sid + '_cuts.json')
        if not os.path.exists(tl_p): print('跳过（还没拍）', sid); continue
        if '--pose' in sys.argv and not glob.glob(os.path.join(config.RENDERS, sid, 'pose_*.png')):
            subprocess.run([config.BLENDER, '-b', '--factory-startup', '-P', os.path.join(config.BLENDER_SCRIPTS, 'export_pose.py'), '--', sid],
                           env=config.blender_env(), capture_output=True)
        tl = json.load(open(tl_p, encoding='utf-8'))
        n_end = max(b['f1'] for b in tl)
        cuts = json.load(open(cuts_p, encoding='utf-8')) if os.path.exists(cuts_p) else [[b['f0'], b['id']] for b in tl]
        bounds = [c[0] for c in cuts] + [n_end + 1]
        byid = {b['id']: b for b in beats}
        last_en = ''
        for k in range(len(cuts)):
            f0, f1 = bounds[k], bounds[k + 1] - 1
            if f1 < f0: continue
            bts = [b for b in tl if b['f0'] <= f1 and b['f1'] >= f0]
            descs = [byid[b['id']].get('en') for b in bts if byid.get(b['id'], {}).get('en')]
            en = descs[0] if descs else last_en; last_en = en or last_en
            chars = sorted({CID[c] for b in bts for c in byid.get(b['id'], {}).get('chars', []) if c in CID})
            if ONLY_BEATS and not any(b['id'] in ONLY_BEATS for b in bts): continue   # 局部补拍：其它镜头保留旧任务
            tid = '%s_%04d' % (sid, f0); td = os.path.join(OUT, tid); shutil.rmtree(td, ignore_errors=True); os.makedirs(td)
            en = shot_prompts.EN.get(tid, en); chars = shot_prompts.CHARS.get(tid, chars)   # 按白模画面覆盖：人数、左右位置（踩坑记录 49）
            for kind in ('beauty', 'depth', 'pose'):
                fr = [os.path.join(REN if kind != 'pose' else config.RENDERS, sid, '%s_%04d.png' % (kind, f)) for f in range(f0, f1 + 1)]
                fr = [p for p in fr if os.path.exists(p)]
                if len(fr) == f1 - f0 + 1: encode(fr, os.path.join(td, kind + '.mp4'))
            refs = ['canon_%s.jpg' % c for c in chars[:3] if os.path.exists(charlib.identity(c, '.png'))]
            for c in chars:   # 标准长相 → refs/canon_<cid>.jpg（云端人物替换的图1）；只带出场角色、存高质量 JPG（家里上行慢）
                rp = os.path.join(OUT, 'refs', 'canon_%s.jpg' % c)
                if not os.path.exists(rp) and os.path.exists(charlib.identity(c, '.png')):
                    import cv2; im_ = cv2.imread(charlib.identity(c, '.png')); cv2.imwrite(rp, im_, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    face_crop(c, im_)
            fb = os.path.join(REN, sid, 'beauty_%04d.png' % f0)   # 首帧（先放预览帧，下面再用高清单帧覆盖）
            if os.path.exists(fb): shutil.copy(fb, os.path.join(td, 'first.png'))
            hd_jobs.setdefault(sid, []).append((f0, td))
            task = dict(id=tid, segment=sid, set=set_name, frames=[f0, f1], n=f1 - f0 + 1, beats=[b['id'] for b in bts], characters=chars,
                        move=(cuts[k][2] if len(cuts[k]) > 2 else 'static'),
                        prompt='%s. Background: %s. %s. %s' % (en or 'a scene on a Chinese university campus', backgrounds.bg(set_name),
                                                              backgrounds.MOVE_EN.get(cuts[k][2] if len(cuts[k]) > 2 else 'static', ''), STYLE), refs=refs)
            task.update(shot_prompts.EXTRA.get(tid, {}))
            json.dump(task, open(os.path.join(td, 'task.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            tasks.append(task)
    for sid, jobs in hd_jobs.items():   # 高清首帧 1920×1080（预览帧放大后很糊，二转三会脑补出第二个人）
        shot = os.path.join(config.SHOTS, sid + '.blend'); tmp = os.path.join(OUT, '_first_' + sid)
        if not os.path.exists(shot): continue
        subprocess.run([config.BLENDER, '-b', shot, '--factory-startup', '-P', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'render_first.py'), '--', tmp]
                       + [str(f) for f, _ in jobs], env=config.blender_env(), capture_output=True)
        for f, td in jobs:
            src = os.path.join(tmp, 'first_%04d.png' % f)
            if os.path.exists(src):
                import cv2; cv2.imwrite(os.path.join(td, 'first.png'), cv2.imread(src))
        shutil.rmtree(tmp, ignore_errors=True)
        print('高清首帧', sid, len(jobs), flush=True)
    all_ids = sorted(os.path.basename(os.path.dirname(p_)) for p_ in glob.glob(os.path.join(OUT, '*', 'task.json')))   # --update 时包含保留下来的旧任务
    json.dump(dict(fps=24, size=[832, 480], tasks=all_ids), open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), indent=1)
    zp = OUT + '.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_STORED) as z:
        for root, _, files in os.walk(OUT):
            for f in files: z.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), os.path.dirname(OUT)))
    print('打包完成：%d 个镜头任务（本次重打 %d），%s（%.0f MB）' % (len(all_ids), len(tasks), zp, os.path.getsize(zp) / 1e6))

if __name__ == '__main__':
    main()
