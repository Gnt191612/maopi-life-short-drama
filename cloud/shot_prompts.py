# -*- coding: utf-8 -*-
"""按镜头覆盖提示词（pack_for_cloud.py 打包时用）：节拍描述是按剧情写的，但同一节拍里不同机位看到的人数、左右位置不一样。
提示词和白模画面不符时，二转三会照着文字补人、给人加眼镜、左右画反（2026-11-26 图书馆 s02_01_0450/0852/1021）。
EN：任务 id → 这个镜头的画面描述（替换节拍描述）；CHARS：任务 id → 画面里真正看得到脸的角色（决定关键帧的人物前缀和换脸）"""
EN = {
    's02_01_0450': 'medium shot by a window seat, sunlight on the wooden table, green trees outside, the chubby young man in the dark grey hoodie, no glasses, '
                   'stands alone beside the table looking around with bright eyes, his face visible; he is the only standing person in the frame; '
                   'far in the background two other students sit at a distant table reading',
    's02_01_0852': 'close-up of one person only: the chubby young man in the dark grey hoodie, round face, no glasses, leans down at the library table and whispers '
                   'toward someone just outside the left edge of the frame; the left foreground is the empty wooden table edge; exactly one face in the frame',   # 白模左下角陈瑶的白肩膀已从锚点图抹掉（会被画成白球）
    's02_01_1021': 'medium shot at a library table, exactly two people: on the LEFT, slightly behind, the chubby young man in the dark grey hoodie with no glasses '
                   'leans over and whispers; on the RIGHT, the slim young man with glasses in a white shirt sits at the table with his head tilted toward him; '
                   'both glance toward the corner',
    's06_01_0178': 'high-angle shot inside a dorm room, exactly two people: the chubby young man in the dark grey hoodie sits slumped over the far desk under the loft bed; '
                   'the slim young man with glasses in a white shirt, in the foreground, walks over to that desk and stands beside him with his back to the camera, '
                   'quietly placing a glass of water; the white shirt stays white, warm desk lamp light',
    's08_01_0226': 'medium shot of three students seated on chairs in a circle in a plain meeting room, looking at each other in silence, from left to right: '
                   'the thin young man with fluffy slightly curly black hair in an olive green sweater, the slim young man with glasses in a white shirt, the chubby young man in the dark grey hoodie looking down; '
                   'a person in a light blue shirt is partly visible at the left edge; nobody sits behind them, the back of the room is empty',
    # 11-26 夜角色对照图查出的旧版跑偏镜头（早期纯图生视频）：人数、谁站谁坐、衣着写死
    's05_01_0727': 'wide shot of a large canteen hall, rows of tables with red stools, the chubby young man in the dark grey hoodie walks quickly away from the camera '
                   'toward the far exit with his head down, getting smaller in the frame; a few students far in the background; the camera stays wide, no close-up',
    's06_01_0063': 'medium shot, the slim young man with glasses in a white shirt opens the dorm door and steps in with a backpack, stops and looks toward a desk, worried; '
                   'he wears his round glasses the whole time; dim room, one warm desk lamp',
    's06_01_0790': 'medium shot inside a dorm, exactly two people: the slim young man with glasses in a white shirt sits on a stool beside the desk and then stands up; '
                   'the chubby young man in the dark grey hoodie sits at the desk under the loft bed covering his face with both hands; the white shirt stays white throughout',
    's08_01_0735': 'medium wide shot of exactly three students seated on chairs in a plain meeting room, all laughing, the atmosphere relaxing, from left to right: '
                   'the thin young man with fluffy slightly curly black hair in an olive green sweater, the slim young man with glasses in a white shirt, '
                   'the chubby young man in the dark grey hoodie; everyone stays seated, no other people in the room',
    's08_01_2657': 'medium wide shot in a plain meeting room, exactly three people: on the left the thin young man with fluffy slightly curly black hair in an olive green sweater sits on a chair; '
                   'in the middle the slim young man with glasses in a white shirt stands and starts clapping gently; on the right the chubby young man in the dark grey hoodie stands; '
                   'the camera stays wide, no other people',
    's10_00_0502': 'medium shot on a sunny lawn, exactly three young men squeeze together for a selfie: on the left the slim young man with glasses in a white shirt, '
                   'in the middle the chubby young man in the dark grey hoodie holding up the phone, on the right the thin young man with fluffy slightly curly black hair '
                   'in an olive green knit sweater; their clothes stay the same throughout',
    # 11-26 夜全片跑偏拼图第二批
    's07_00_0171': 'on the running track at dusk: the thin young man with fluffy slightly curly black hair in an olive green knit sweater walks beside the chubby young man '
                   'in the dark grey hoodie, then the camera moves in to a close-up of the chubby young man walking with his head down, kicking a small pebble, '
                   'then turning his face to ask, face visible, street lamp light; two clearly different people',
    's10_00_0102': 'medium shot on the sunny lawn, exactly three young men, from left to right: the slim young man with glasses in a white shirt laughs and reaches out '
                   'to push down the phone held by the chubby young man in the dark grey hoodie in the middle; on the right the thin young man with fluffy slightly curly '
                   'black hair in an olive green knit sweater',
    's05_01_0674': 'medium close-up, the thin young man with fluffy slightly curly black hair in an olive green knit sweater stands further back in the canteen queue '
                   'holding a tray, watching quietly with a serious expression',
    's08_01_1461': 'medium shot in a small plain meeting room with only a few students on chairs in a circle: the slim young man with glasses in a white shirt '
                   'stands up from his chair, the two students seated beside him look up at him; no crowd, no other people, the room stays the same',
    's06_01_0446': 'close-up of one person only: the chubby young man in the dark grey hoodie has his head down on the desk, at first only the top of his black hair is visible; '
                   'he slowly lifts his head and looks toward the right, eyes slightly puffy from crying, natural skin and natural eyes, no glowing, no red light; '
                   'exactly one person in the frame, warm lamp light',   # 原提示词 eyes red and swollen → 眼睛发红光；face clearly visible → 开头只有头顶时补出第二张脸
}
EXTRA = {   # 写进 task.json 的额外字段：noswap = 关键帧不做 Qwen 换脸（两人挨得近时会换错人）
    's03_02_0001': dict(noswap=True),   # 林母：Qwen 按标准照换脸会把白模的短卷发换成长直发，和 s09 的短卷发对不上
    's02_01_1021': dict(noswap=True),
    's02_01_0852': dict(noswap=True),
    's02_01_0450': dict(bg_face='classA'),   # 本地换脸：多出来的站立路人换成同学甲的脸
}
CHARS = {
    's02_01_0852': ['lin'],
    's07_00_0171': ['lin', 'zhou'],          # 白模开头周明远和林晓并排走，原来只写了林晓 → 画成两个林晓
    's10_00_0102': ['chen', 'lin', 'zhou'],  # 白模右边有周明远
}
