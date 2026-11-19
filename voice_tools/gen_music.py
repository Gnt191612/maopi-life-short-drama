# -*- coding: utf-8 -*-
"""原创配乐（AI 生成，纯音乐）：ACE-Step（Apache-2.0，生成的音乐可自由使用与再分发）。
每条按场景气质写风格提示；时长略长于所需，混音时淡入淡出、不够就循环。输出 assets/music/ai_<id>.wav。
运行：<ACE-Step 环境的 python> voice_tools/gen_music.py [id ...]   （环境变量 V11_ACESTEP_DIR 指向 ACE-Step 仓库）
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
ACE = os.environ.get('V11_ACESTEP_DIR') or os.path.join(config.TOOLS, 'ACE-Step')
sys.path.insert(0, ACE)
OUT = os.path.join(config.ROOT, 'assets', 'music'); os.makedirs(OUT, exist_ok=True)

TRACKS = {   # id: (风格提示, 时长秒, 种子)
 'morning_citypop':  ('city pop, lo-fi, funky bass, bright electric piano, light drums, sunny morning, upbeat, 104 bpm, instrumental', 95, 11),
 'library_lofi':     ('lo-fi hip hop, chill beats, jazzy piano chords, soft vinyl crackle, playful, 84 bpm, instrumental', 75, 23),
 'sneaky_pizz':      ('playful pizzicato strings, sneaky tiptoe, light woodblock percussion, comedic, mischievous, instrumental', 60, 37),
 'canteen_funk':     ('funk, slap bass, short brass stabs, groovy, comedic tension, rising awkwardness, 112 bpm, instrumental', 55, 41),
 'night_chillwave':  ('chillwave, ambient synth pads, soft drum machine, nostalgic, night city, dreamy, reverb guitar, 78 bpm, instrumental', 130, 53),
 'teaparty_guitar':  ('acoustic guitar fingerpicking, warm and gentle, indie folk, soft piano, hopeful, intimate, instrumental', 100, 67),
 'ending_indiepop':  ('indie pop, bright jangly guitars, uplifting, summer afternoon, cheerful drums, handclaps, 120 bpm, instrumental', 90, 79),
}

def main():
    only = set(sys.argv[1:])
    from acestep.pipeline_ace_step import ACEStepPipeline
    # 8 GB 显卡：分阶段放显存 + 分段解码，留出显存给渲染和日常使用
    pipe = ACEStepPipeline(checkpoint_dir=os.path.join(ACE, 'checkpoints'), dtype='bfloat16', torch_compile=False,
                           cpu_offload=True, overlapped_decode=True)
    meta_p = os.path.join(OUT, 'ai_music.json')
    meta = json.load(open(meta_p, encoding='utf-8')) if os.path.exists(meta_p) else {}
    for tid, (prompt, dur, seed) in TRACKS.items():
        if only and tid not in only: continue
        out = os.path.join(OUT, 'ai_%s.wav' % tid)
        if os.path.exists(out) and not only: continue
        pipe(format='wav', audio_duration=dur, prompt=prompt, lyrics='[instrumental]', infer_step=60, guidance_scale=15,
             scheduler_type='euler', cfg_type='apg', omega_scale=10, manual_seeds=[seed], guidance_interval=0.5,
             min_guidance_scale=3, save_path=out)
        meta[tid] = dict(prompt=prompt, duration=dur, seed=seed, model='ACE-Step-v1-3.5B', license='Apache-2.0 (model); output free to use')
        json.dump(meta, open(meta_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('MUSIC OK', tid, flush=True)

if __name__ == '__main__':
    main()
