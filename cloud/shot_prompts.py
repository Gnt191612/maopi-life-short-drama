# -*- coding: utf-8 -*-
"""按镜头覆盖提示词（pack_for_cloud.py 打包时用）：节拍描述是按剧情写的，但同一节拍里不同机位看到的人数、左右位置不一样。
提示词和白模画面不符时，二转三会照着文字补人、给人加眼镜、左右画反（2026-11-26 图书馆 s02_01_0450/0852/1021）。
EN：任务 id → 这个镜头的画面描述（替换节拍描述）；CHARS：任务 id → 画面里真正看得到脸的角色（决定关键帧的人物前缀和换脸）"""
EN = {
    's02_01_0450': 'medium shot by a window seat, sunlight on the wooden table, green trees outside, the chubby young man in the dark grey hoodie, no glasses, '
                   'stands alone beside the table looking around with bright eyes, his face visible; he is the only standing person in the frame; '
                   'far in the background two other students sit at a distant table reading',
    's02_01_0852': 'close-up: the chubby young man in the dark grey hoodie, round face, no glasses, leans toward the left edge of the frame and whispers to a seated classmate '
                   'who is cut off by the left frame edge: only that classmate\'s white shirt shoulder and upper arm are visible, a plain white cotton shirt with folds; '
                   'no ball, no lamp, no round object; exactly one face in the frame',
    's02_01_1021': 'medium shot at a library table, exactly two people: on the LEFT, slightly behind, the chubby young man in the dark grey hoodie with no glasses '
                   'leans over and whispers; on the RIGHT, the slim young man with glasses in a white shirt sits at the table with his head tilted toward him; '
                   'both glance toward the corner',
    's06_01_0178': 'high-angle shot inside a dorm room, exactly two people: the chubby young man in the dark grey hoodie sits slumped over the far desk under the loft bed; '
                   'the slim young man with glasses in a white shirt, in the foreground, walks over to that desk and stands beside him with his back to the camera, '
                   'quietly placing a glass of water; the white shirt stays white, warm desk lamp light',
    's08_01_0226': 'medium shot of three students seated on chairs in a circle in a plain meeting room, looking at each other in silence, from left to right: '
                   'the thin young man with a buzz cut in an olive green sweater, the slim young man with glasses in a white shirt, the chubby young man in the dark grey hoodie looking down; '
                   'a person in a light blue shirt is partly visible at the left edge; nobody sits behind them, the back of the room is empty',
}
EXTRA = {   # 写进 task.json 的额外字段：noswap = 关键帧不做 Qwen 换脸（两人挨得近时会换错人）
    's02_01_1021': dict(noswap=True),
    's02_01_0852': dict(noswap=True),
    's02_01_0450': dict(bg_face='classA'),   # 本地换脸：多出来的站立路人换成同学甲的脸
}
CHARS = {
    's02_01_0852': ['lin'],
}
