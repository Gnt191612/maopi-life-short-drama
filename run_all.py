# -*- coding: utf-8 -*-
"""白模全片无人值守总控（不依赖 Claude、可断网；幂等：已完成的片段自动跳过，可反复运行）。
  1) Rhubarb：全部台词 -> 口型序列（CPU）
  2) 逐个地点片段：Blender 搭建 + 动画 + 渲染白模/深度图（Cycles 960x540，显存占用约 2GB）
  3) 每个片段合成带配音、字幕的预演视频；最后拼成全片预演 build/previs/v11_previs_full.mp4
运行：python run_all.py   （先运行 setup/ 下的安装脚本；强制重做某段：删除 build/renders/<seg>/ 与 build/shots/<seg>.blend）
日志：build/logs/run_all.log
"""
import os, sys, json, glob, time, subprocess, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import numpy as np
import segments as S

BL, RB, FF = config.BLENDER, config.RHUBARB, config.FFMPEG
for _n, _x in (('Blender', BL), ('Rhubarb', RB), ('ffmpeg', FF)):
    if not _x: sys.exit('找不到 %s：请先运行 setup/ 下的安装脚本' % _n)
LOG = os.path.join(config.LOGS, 'run_all.log'); PRE = config.PREVIS

def log(*a):
    s = time.strftime('%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a)
    print(s, flush=True); open(LOG, 'a', encoding='utf-8').write(s + '\n')

def visemes():
    for lid in S.META:
        out = os.path.join(config.VISEMES, lid + '.json')
        if os.path.exists(out): continue
        r = subprocess.run([RB, '-r', 'phonetic', '-f', 'json', '-q', '-o', out, os.path.join(S.AUD, lid + '.wav')], capture_output=True)
        log('rhubarb', lid, 'OK' if r.returncode == 0 else 'FAIL')

def segment(seg_id, n_frames):
    out = os.path.join(config.RENDERS, seg_id)
    done = len(glob.glob(os.path.join(out, 'beauty_*.png')))
    if done >= n_frames and os.path.exists(os.path.join(config.SHOTS, seg_id + '.blend')): return True
    for f in glob.glob(os.path.join(out, '*.png')): os.remove(f)
    t0 = time.time()
    with open(os.path.join(config.LOGS, 'blender_%s.log' % seg_id), 'w', encoding='utf-8') as lf:
        r = subprocess.run([BL, '-b', '--factory-startup', '-P', os.path.join(config.BLENDER_SCRIPTS, 'shoot_segment.py'), '--', seg_id],
                           stdout=lf, stderr=lf, env=config.blender_env())
    n = len(glob.glob(os.path.join(out, 'beauty_*.png')))
    log('segment', seg_id, 'rc=%d' % r.returncode, 'frames %d/%d' % (n, n_frames), '%.0fs' % (time.time() - t0))
    return r.returncode == 0 and n >= n_frames

def load_wav(p, sr=48000):
    r = subprocess.run([FF, '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32)

def ts(t): return '%d:%02d:%05.2f' % (t // 3600, t % 3600 // 60, t % 60)

def ff_path(p):
    """给 ffmpeg 滤镜参数用的路径（正斜杠、转义冒号）"""
    return p.replace('\\', '/').replace(':', '\\:')

def previs(seg_ids, out_mp4):
    """把若干片段的白模帧接起来，配上台词与字幕（开源字体 Noto Sans SC）"""
    tmp = os.path.join(PRE, 'tmp'); os.makedirs(tmp, exist_ok=True)
    lst, events, t = [], [], 0.0
    for sid in seg_ids:
        tl = json.load(open(os.path.join(config.SHOTS, sid + '_timeline.json'), encoding='utf-8'))
        frames = sorted(glob.glob(os.path.join(config.RENDERS, sid, 'beauty_*.png')))
        lst += frames
        for b in tl:
            for fr, lid in b['audio']: events.append((t + (fr - 1) / 24.0, lid))
        t += len(frames) / 24.0
    lp = os.path.join(tmp, 'frames.txt')
    open(lp, 'w', encoding='utf-8').write(''.join("file '%s'\nduration %.6f\n" % (f.replace('\\', '/'), 1 / 24) for f in lst))
    sr = 48000; mix = np.zeros(int((t + 1) * sr), np.float32)
    ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 960', 'PlayResY: 540', '', '[V4+ Styles]',
           'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV',
           'Style: D,%s,30,&H00FFFFFF,&H00000000,&H80000000,0,1,2,1,2,28' % config.FONT_NAME, '', '[Events]', 'Format: Layer, Start, End, Style, Text']
    for st, lid in events:
        w = load_wav(os.path.join(S.AUD, lid + '.wav')); i = int(st * sr); mix[i:i + len(w)] += w[:max(0, len(mix) - i)]
        if not lid.startswith('X'):
            ass.append('Dialogue: 0,%s,%s,D,%s：%s' % (ts(st), ts(st + S.META[lid]['dur']), S.TEXT[lid][0], S.TEXT[lid][1]))
    wp = os.path.join(tmp, 'mix.wav')
    with wave.open(wp, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    ap = os.path.join(tmp, 'sub.ass'); open(ap, 'w', encoding='utf-8-sig').write('\n'.join(ass) + '\n')
    vf = "fps=24,subtitles='%s':fontsdir='%s'" % (ff_path(ap), ff_path(config.FONTS_DIR))
    subprocess.run([FF, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lp, '-i', wp, '-vf', vf,
                    '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', out_mp4], check=True)
    log('previs OK', out_mp4, '%.1fs' % t)

def main():
    log('==== run_all start')
    visemes()
    segs = S.segments(); ok = []
    for sid, scene, set_name, beats in segs:
        n = sum(S.beat_frames(b) for b in beats)
        for attempt in range(2):
            if segment(sid, n): ok.append(sid); break
    by_scene = {}
    for sid in ok: by_scene.setdefault(sid[:3], []).append(sid)
    for scn, ids in by_scene.items():
        try: previs(ids, os.path.join(PRE, 'v11_previs_%s.mp4' % scn))
        except Exception as e: log('previs FAIL', scn, e)
    try: previs(ok, os.path.join(PRE, 'v11_previs_full.mp4'))
    except Exception as e: log('previs full FAIL', e)
    log('==== run_all end', '%d/%d segments' % (len(ok), len(segs)))

if __name__ == '__main__':
    main()
