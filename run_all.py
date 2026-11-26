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
REAL_DIR = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--real=')), None)   # 成片合成：--previs-only --real=<云端 out 目录>
if REAL_DIR: PRE = os.path.join(config.ROOT, 'build', 'final'); os.makedirs(PRE, exist_ok=True)   # 写实版输出到 build/final/，不覆盖预演

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
    def real_frames(n0):   # 拍子可能因真人动作所需时间而加长：以拍摄引擎写出的实际时间轴为准
        tlp = os.path.join(config.SHOTS, seg_id + '_timeline.json')
        return max(n0, max(b['f1'] for b in json.load(open(tlp, encoding='utf-8')))) if os.path.exists(tlp) else n0
    n_frames = real_frames(n_frames)
    done = len(glob.glob(os.path.join(out, 'beauty_*.png')))
    if done >= n_frames and os.path.exists(os.path.join(config.SHOTS, seg_id + '.blend')): return True
    partial = bool(os.environ.get('V11_RENDER_BEATS'))   # 局部补拍：只渲部分镜头，不能清空其它帧，也不能按总帧数判失败（11-25：原来每段都重跑了一遍）
    if not partial:
        for f in glob.glob(os.path.join(out, '*.png')): os.remove(f)
    t0 = time.time()
    with open(os.path.join(config.LOGS, 'blender_%s.log' % seg_id), 'w', encoding='utf-8') as lf:
        r = subprocess.run([BL, '-b', '--factory-startup', '-P', os.path.join(config.BLENDER_SCRIPTS, 'shoot_segment.py'), '--', seg_id],
                           stdout=lf, stderr=lf, env=config.blender_env())
    n = len(glob.glob(os.path.join(out, 'beauty_*.png'))); n_frames = real_frames(n_frames)
    log('segment', seg_id, 'rc=%d' % r.returncode, 'frames %d/%d' % (n, n_frames), '%.0fs' % (time.time() - t0))
    return r.returncode == 0 and (partial or n >= n_frames)

def load_wav(p, sr=48000):
    r = subprocess.run([FF, '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32)

def ts(t): return '%d:%02d:%05.2f' % (t // 3600, t % 3600 // 60, t % 60)

def ff_path(p):
    """给 ffmpeg 滤镜参数用的路径（正斜杠、转义冒号）"""
    return p.replace('\\', '/').replace(':', '\\:')

def music_bed(beat_t, dialog, sr):
    """按 story/music.py 的配乐表铺音乐：淡入淡出、不够长就循环；有台词时自动避让（再压低约 9 dB，0.15 秒压下、0.8 秒回升）"""
    from music import CUES
    out = np.zeros_like(dialog)
    # 台词包络：50 ms 窗口的音量，有声处 = 1
    win = int(0.05 * sr); env = np.abs(dialog)
    env = np.convolve(env, np.ones(win) / win, mode='same') > 0.01
    duck = np.ones(len(dialog), np.float32); g = 1.0; lo = 10 ** (-9 / 20)
    step = 256                                          # 逐块平滑（攻击快、释放慢）
    for i in range(0, len(dialog), step):
        target = lo if env[i:i + step].any() else 1.0
        rate = 1 - np.exp(-step / (sr * (0.15 if target < g else 0.8)))
        g += (target - g) * rate; duck[i:i + step] = g
    mdir = os.path.join(config.ROOT, 'assets', 'music')
    for b0, b1, track, db in CUES:
        if b0 not in beat_t or b1 not in beat_t: continue
        path = next((os.path.join(mdir, f) for f in os.listdir(mdir) if os.path.splitext(f)[0] == track), None) if os.path.isdir(mdir) else None
        if not path: log('配乐缺少曲目', track); continue
        a, z = beat_t[b0][0], beat_t[b1][1]; n = int((z - a) * sr); i0 = int(a * sr)
        m = load_wav(path, sr)
        if not len(m): continue
        reps = int(np.ceil(n / len(m)))
        seg = np.tile(m, reps)[:n] * (10 ** (db / 20)) / max(1e-6, float(np.abs(m).max()))
        fi, fo = min(n, int(1.5 * sr)), min(n, int(2.0 * sr))
        seg[:fi] *= np.linspace(0, 1, fi); seg[n - fo:] *= np.linspace(1, 0, fo)
        out[i0:i0 + n] += seg[:max(0, len(out) - i0)]
    return out * duck

def previs(seg_ids, out_mp4):
    """把若干片段的白模帧接起来，配上台词与字幕（开源字体 Noto Sans SC）"""
    tmp = os.path.join(PRE, 'tmp'); os.makedirs(tmp, exist_ok=True)
    lst, events, screens, t = [], [], [], 0.0
    beat_t = {}                                        # 拍 -> (开始秒, 结束秒)，配乐按拍定位
    for sid in seg_ids:
        tl = json.load(open(os.path.join(config.SHOTS, sid + '_timeline.json'), encoding='utf-8'))
        # 帧列表按时间轴（1..最后一拍的 f1）排，不按白模帧文件：局部补拍曾把部分片段的白模帧清掉，原来只认白模帧，
        # 成片少了近 4 分钟（应 600 秒只合出 381 秒），配音字幕也跟着错位（2026-11-25）。写实帧优先，其次白模帧，都没有就沿用上一帧
        n_end = max(b['f1'] for b in tl)
        grey = {int(f[-8:-4]): f for f in glob.glob(os.path.join(config.RENDERS, sid, 'beauty_*.png'))}
        real = {}
        if REAL_DIR:   # 云端写实化回来的画面（out/<镜头任务>/frame_####.png）优先，缺的帧用白模补
            for f in glob.glob(os.path.join(REAL_DIR, sid + '_*', 'frame_*.png')): real[int(f[-8:-4])] = f
        frames, last = [], None
        for k in range(1, n_end + 1):
            last = real.get(k) or grey.get(k) or last
            if last is None: last = next((grey[x] for x in sorted(grey)), None) or next((real[x] for x in sorted(real)), None)
            if last: frames.append(last)
        if len(frames) < n_end: log('片段帧不全', sid, len(frames), n_end)
        lst += frames
        for b in tl:
            beat_t[b['id']] = (t + (b['f0'] - 1) / 24.0, t + b['f1'] / 24.0)
            for fr, lid in b['audio']: events.append((t + (fr - 1) / 24.0, lid))
            for fr, scr, d in b.get('screen', []): screens.append((t + (fr - 1) / 24.0, scr, d))
        t += len(frames) / 24.0
    lp = os.path.join(tmp, 'frames.txt')
    open(lp, 'w', encoding='utf-8').write(''.join("file '%s'\nduration %.6f\n" % (f.replace('\\', '/'), 1 / 24) for f in lst))
    sr = 48000; mix = np.zeros(int((t + 1) * sr), np.float32)
    ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 960', 'PlayResY: 540', '', '[V4+ Styles]',
           'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV',
           'Style: D,%s,30,&H00FFFFFF,&H00000000,&H80000000,0,1,2,1,2,28' % config.FONT_NAME,
           'Style: P,%s,26,&H0000E5FF,&H00000000,&HA0000000,0,3,2,0,8,24' % config.FONT_NAME, '', '[Events]', 'Format: Layer, Start, End, Style, Text']
    for st, lid in events:
        w = load_wav(os.path.join(S.AUD, lid + '.wav')); i = int(st * sr); mix[i:i + len(w)] += w[:max(0, len(mix) - i)]
        if not lid.startswith('X'):
            ass.append('Dialogue: 0,%s,%s,D,%s：%s' % (ts(st), ts(st + S.META[lid]['dur']), S.TEXT[lid][0], S.TEXT[lid][1]))
    for st, sid, d in screens:   # 手机屏幕文字（正片由 Remotion 合成到手机上；预演以画面上方黄字示意）
        ass.append('Dialogue: 0,%s,%s,P,【手机】%s：%s' % (ts(st), ts(st + d), S.SCREEN[sid][0], S.SCREEN[sid][1]))
    mix += music_bed(beat_t, mix, sr)
    wp = os.path.join(tmp, 'mix.wav')
    with wave.open(wp, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    ap = os.path.join(tmp, 'sub.ass'); open(ap, 'w', encoding='utf-8-sig').write('\n'.join(ass) + '\n')
    vf = "fps=24,subtitles='%s':fontsdir='%s'" % (ff_path(ap), ff_path(config.FONTS_DIR))
    if REAL_DIR:   # 写实版成片：写实帧 832×480 与补位的白模帧尺寸不同，统一缩放到 1080p 再上字幕
        vf = "fps=24,scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1," + vf[len('fps=24,'):].replace('PlayRes', 'PlayRes')
    subprocess.run([FF, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lp, '-i', wp, '-vf', vf,
                    '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', out_mp4], check=True)
    log('previs OK', out_mp4, '%.1fs' % t)

def main():
    log('==== run_all start')
    segs = S.segments(); ok = []
    only = [x for x in os.environ.get('V11_ONLY', '').split(',') if x]   # 只渲指定片段（试片用），如 V11_ONLY=s05_00,s05_01
    if only: segs = [s for s in segs if s[0] in only]
    if '--previs-only' in sys.argv:   # 只重新合成预演（换了配乐/字幕时用，不重新渲染画面）
        ok = [s[0] for s in segs if os.path.exists(os.path.join(config.SHOTS, s[0] + '_timeline.json'))]
        segs = []
    else:
        visemes()
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
