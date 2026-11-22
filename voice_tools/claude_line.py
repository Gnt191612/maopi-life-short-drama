# -*- coding: utf-8 -*-
"""片头 Claude 娘台词（IndexTTS2）：每个音色候选各念一遍，温柔微笑的情绪；输出 assets/intro/voice/claude_line_<候选>.wav
运行：D:\\ai\\index-tts\\.venv\\Scripts\\python.exe voice_tools/claude_line.py [候选号 ...]"""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
INDEX_DIR = os.environ.get('V11_INDEXTTS_DIR') or r'D:\ai\index-tts'
sys.path.insert(0, INDEX_DIR)
TEXT = os.environ.get('CLAUDE_LINE', '本视频由 Claude Opus 五点五 领衔制作。')
EMO = [0.45, 0, 0, 0, 0, 0, 0, 0.55]   # 高兴, 愤怒, 悲伤, 恐惧, 反感, 低落, 惊讶, 自然：温柔地微笑着说
OUT = os.path.join(ROOT, 'assets', 'intro', 'voice'); os.makedirs(OUT, exist_ok=True)

def main():
    picks = sys.argv[1:] or [os.path.basename(p)[len('Claude娘_'):-4] for p in sorted(glob.glob(os.path.join(HERE, 'voices_v2', 'Claude娘_*.wav')))]
    os.chdir(INDEX_DIR)
    from indextts.infer_v2 import IndexTTS2
    tts = IndexTTS2(cfg_path='checkpoints/config.yaml', model_dir='checkpoints', use_fp16=True, use_cuda_kernel=False, use_qwen_emo=False)
    for k in picks:
        ref = os.path.join(HERE, 'voices_v2', 'Claude娘_%s.wav' % k)
        out = os.path.join(OUT, 'claude_line_%s.wav' % k)
        tts.infer(spk_audio_prompt=ref, text=TEXT, output_path=out, emo_vector=EMO, emo_alpha=0.6, verbose=False)
        print('LINE OK', k, out, flush=True)

if __name__ == '__main__':
    main()
