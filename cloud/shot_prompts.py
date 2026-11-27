# -*- coding: utf-8 -*-
"""按镜头覆盖提示词（pack_for_cloud.py 打包时用）：节拍描述是按剧情写的，但同一节拍里不同机位看到的人数、左右位置不一样。
提示词和白模画面不符时，二转三会照着文字补人、给人加眼镜、左右画反（2026-11-26 图书馆 s02_01_0450/0852/1021）。
EN：任务 id → 这个镜头的画面描述（替换节拍描述）；CHARS：任务 id → 画面里真正看得到脸的角色（决定关键帧的人物前缀和换脸）"""
EN = {
    's02_01_0450': 'medium shot by a window seat, sunlight on the wooden table, green trees outside, the chubby young man in the dark grey hoodie, no glasses, '
                   'stands alone beside the table looking around with bright eyes, his face visible; he is the only standing person in the frame; '
                   'far in the background two other students sit at a distant table reading',
    's02_01_0852': 'close-up of one person only: the chubby young man in the dark grey hoodie, round face, no glasses, leans down at the library table and whispers '
                   'toward the left edge of the frame, where only the white shirt shoulder of a seated person is visible; exactly one face in the frame',
    's02_01_1021': 'medium shot at a library table, exactly two people: on the LEFT, slightly behind, the chubby young man in the dark grey hoodie with no glasses '
                   'leans over and whispers; on the RIGHT, the slim young man with glasses in a white shirt sits at the table with his head tilted toward him; '
                   'both glance toward the corner',
}
CHARS = {
    's02_01_0852': ['lin'],
}
