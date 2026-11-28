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

    's01_01_1016': 'close-up of the same chubby young man by the window looking down at his phone, typing, his face and mouth clearly visible in soft window light; he wears the same dark grey open zip hoodie with the hood resting behind his neck over a dark grey T-shirt, not a black jacket, not a white T-shirt',   # 11-27 用户指出：同一场戏里林晓穿成黑外套+白T恤（白模卫衣帽子被机位挡住）
    's02_01_1116': 'medium close-up, the same chubby young man now sits at the window table with the open book, his phone face-up beside the book; he wears the same dark grey open zip hoodie with the hood resting behind his neck over a dark grey T-shirt, not a black jacket, not a white T-shirt',   # 11-27 用户指出：同一场戏里林晓穿成黑外套+白T恤（白模卫衣帽子被机位挡住）
    's01_01_0577': 'wide shot of the whole dorm room with bunk beds on both sides: in the back the chubby young man in the dark grey open hoodie has just climbed down the bunk ladder and grabs a toothbrush cup and towel from his desk; at the desk on the left sits the slim young man with glasses in a white shirt, glancing at him; real dorm room, real wood and metal, natural morning light',   # 11-27 用户/对齐审查：渲染失败（白模质感、人物错）
    's05_01_0440': 'medium shot in a real busy university canteen with long white dining tables and red plastic stools: the young man in the navy track jacket walks up from the left with a food tray and pats the shoulder of the chubby young man in the dark grey hoodie on the right, grinning; real canteen, real food trays, natural light',   # 11-27 用户/对齐审查：渲染失败（白模质感、人物错）
    's08_01_0288': 'medium close-up, the man in the light blue shirt and dark tie pulls a chair over and sits down in the circle, face visible; behind him on the left sits the slim young man with glasses in a white shirt',   # 11-27 用户/对齐审查：渲染失败（白模质感、人物错）
    's10_00_0787': 'medium shot on a sunny campus lawn with real green trees, exactly three young men: on the left the slim young man with glasses in a white shirt; in the middle the chubby young man in the dark grey open hoodie looks down at his phone and types, then smiles; behind him on the right the thin young man with fluffy slightly curly black hair in an olive green knit sweater',   # 11-27 用户/对齐审查：渲染失败（白模质感、人物错）
}
EXTRA = {   # 写进 task.json 的额外字段：noswap = 关键帧不做 Qwen 换脸（两人挨得近时会换错人）
    's03_02_0001': dict(noswap=True),   # 林母：Qwen 按标准照换脸会把白模的短卷发换成长直发，和 s09 的短卷发对不上
    's08_01_0226': dict(kf_hint='从左到右：左边是清瘦的周明远（蓬松卷发、橄榄绿毛衣），中间是陈瑶（白衬衫、圆框眼镜），右边是体型明显偏胖的林晓（深灰连帽卫衣）；画面里只有这三个学生，其他人都不胖。'),
    's08_01_0735': dict(kf_hint='从左到右：左边是清瘦的周明远（蓬松卷发、橄榄绿毛衣），中间是陈瑶（白衬衫、圆框眼镜），右边是体型明显偏胖的林晓（深灰连帽卫衣）；画面里只有这三个学生，其他人都不胖。'),
    's08_01_2657': dict(kf_hint='从左到右：左边坐着清瘦的周明远（蓬松卷发、橄榄绿毛衣），中间站着陈瑶（白衬衫、圆框眼镜），右边站着体型明显偏胖的林晓（深灰连帽卫衣）；画面里只有这三个学生，其他人都不胖。'),
    's01_01_1016': dict(kf_hint='林晓穿的是深灰色开襟连帽卫衣（帽子搭在脖子后面），里面是深灰色T恤，和前后镜头同一身衣服；不是黑色西装外套，里面也不是白T恤。'),
    's02_01_1116': dict(kf_hint='林晓穿的是深灰色开襟连帽卫衣（帽子搭在脖子后面），里面是深灰色T恤，和前后镜头同一身衣服；不是黑色西装外套，里面也不是白T恤。'),
    's01_01_0577': {'kf_hint': '这是真实的大学宿舍：后面站着的是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓，刚从上铺下来拿毛巾和漱口杯；左边书桌前坐着戴圆框眼镜、穿白衬衫的清瘦男生陈瑶。真实的木头和金属床架，自然晨光，不要3D渲染的质感。', 'kf_start': 2},
    's05_01_0440': {'kf_hint': '这是真实的大学食堂：红色方块是食堂的红色塑料凳，白色长条是餐桌，远处有打饭窗口。左边是穿藏青色运动外套端着餐盘的男生，右边是体型明显偏胖、穿深灰卫衣的林晓。不要3D渲染的方块质感。', 'kf_start': 2},
    's08_01_0288': {'kf_hint': '前面是穿浅蓝衬衫打深色领带的中年男老师；左后方坐着的是戴圆框眼镜、穿白衬衫的清瘦男生陈瑶（是年轻男生，不是女人）。'},
    's10_00_0787': {'kf_hint': '真实的校园草坪和真实的绿树（不是卡通树）。左边是戴圆框眼镜、穿白衬衫的陈瑶，中间是体型明显偏胖、穿深灰开襟卫衣、低头看手机的林晓，右后方是清瘦卷发、穿橄榄绿毛衣的周明远；画面里只有这三个人。', 'kf_start': 2},
    # 11-27 试片：白模里林晓趴在桌上低头、只露头顶，二转三画成了一个弯腰的人，换脸又硬加一张正脸 → 画面两个人；视频里那人变成学习的同学，宿舍像自习室（用户指出）
    's06_01_0446': {'kf_hint': '画面里只有林晓一个人：他趴在宿舍书桌上低着头，画面右下角只露出他黑色碎发的头顶和一点深灰色卫衣的肩膀，看不到脸。背景是宿舍的浅色墙面和金属床梯，没有别的人。'},
    's02_01_1021': dict(noswap=True),
    's02_01_0852': dict(noswap=True),
    's02_01_0450': dict(bg_face='classA'),   # 本地换脸：多出来的站立路人换成同学甲的脸
}
CHARS = {
    's08_01_0288': ['wang', 'chen'],   # 白模左后方坐着陈瑶，原来只登记王老师 → 画成中年女人
    's02_01_0852': ['lin'],
    's07_00_0171': ['lin', 'zhou'],          # 白模开头周明远和林晓并排走，原来只写了林晓 → 画成两个林晓
    's10_00_0102': ['chen', 'lin', 'zhou'],  # 白模右边有周明远
}

# ===== 11-27 全片提示词审查改写（用户要求「对全篇提示词做细致全面的检查，保证符合现实和剧情」）=====
# 每条按白模画面（逐镜抽帧核对过）+ 剧情动作重写；规则：只写白模里看得见的东西和动作（踩坑 65）、正面写法不用否定词（H3 没有负面分支）、
# 衣着和人物库一致、人数和白模一致（踩坑 68）、时间和场景一致（踩坑 70）。动作以白模为准（视频动作由白模控制，文字写别的动作会来回拉扯）。
EN.update({
    # —— 以前沿用了上一镜的描述，和本镜动作对不上（打包时节拍没有英文描述就沿用上一条）——
    's01_01_0411': 'medium shot from behind and above: the chubby young man in the dark grey hoodie throws off the quilt and climbs down the bunk ladder in a hurry, landing beside his desk',
    's01_01_0758': 'medium shot by the dorm door: the chubby young man in the dark grey hoodie puts down his toothbrush, rubs his face with a towel, forces a smile at the mirror, then turns and walks past the camera into the room',
    's01_01_1244': 'medium shot: the slim young man with round glasses in a white shirt, backpack on, walks to the dorm door with his back to the camera, stops with his hand by the door handle and turns his head back over his shoulder toward the room to speak, then shakes his head',
    's01_01_1399': 'medium shot at the dorm doorway: the slim young man with round glasses in a white shirt steps out through the open door and pulls it closed behind him',
    's02_01_0221': 'wide shot of the library reading room: the chubby young man in the dark grey hoodie walks quickly across the room toward the bright window seats on the far side, glancing at the light; the slim young man with round glasses in a white shirt stays seated at a table in the background',
    's03_01_0181': 'medium shot: the chubby young man in the dark grey hoodie lies on his bed looking at his phone; a notification appears, his smile freezes, and he slowly sits up on the edge of the bed staring at the screen, his face turning pale',
    's03_03_0167': 'medium shot from behind at his desk under the loft bed: the chubby young man in the dark grey hoodie ends the video call and lowers the phone, his shoulders slump, he leans forward and props his head in his hand',
    's04_00_0362': 'medium shot at the closed glass doors of the library: the chubby young man in the dark grey hoodie sighs, turns away, walks to the stone steps and sits down, taking out his phone',
    's07_00_0469': 'medium close-up on the night track: the thin young man with fluffy curly hair in an olive green knit sweater has stopped walking and turned to face the chubby young man in the dark grey hoodie, recalling the past calmly with a faint self-mocking smile as he speaks; the chubby one stands facing him and listens',
    's08_01_2274': 'medium shot in the meeting room: the chubby young man in the dark grey hoodie stands up from his chair gripping the hem of his hoodie and starts speaking nervously, his voice a little shaky; the slim young man with round glasses in a white shirt stands beside him on the left',
    # —— 白模是手机屏幕特写，以前写成了人脸镜头（模型会往手机特写里画脸）——
    's03_01_0023': 'extreme close-up of a smartphone screen held in his hand, a social media comment list scrolling up; the screen text stays exactly as in Picture 1',
    's05_01_0090': 'extreme close-up of a smartphone screen held in a slightly trembling hand, a list of comments scrolling; the screen text stays exactly as in Picture 1',
    's07_01_0023': 'flashback with a cold blue color grade: extreme close-up of a smartphone screen showing an incoming call, the phone keeps ringing in his hand; the screen text stays exactly as in Picture 1',
    's07_03_0023': 'flashback with a cold blue color grade: extreme close-up of a smartphone screen in the dark, a message being typed, his thumb hovering over the send button; the screen text stays exactly as in Picture 1',
    's09_01_0707': 'extreme close-up of a smartphone screen at night, new comments popping up one after another; the screen text stays exactly as in Picture 1',
    's10_00_0586': 'extreme close-up of a smartphone screen in daylight, an unedited photo being posted with a short caption; the screen text stays exactly as in Picture 1',
    # —— 白模整段是从肩后拍手机，看不到脸（以前写「脸和嘴清楚可见」）；衣着正面写 ——
    's01_01_1016': 'over-the-shoulder close-up from behind the chubby young man: his hand in the sleeve of his dark grey open zip hoodie holds the phone and his thumb types quickly; his face stays turned toward the screen, out of view; soft morning window light',
    # —— 多段动作只写了第一段 ——
    's01_01_0054': 'medium close-up from beside the top bunk bed: the chubby young man under the quilt, half awake, reaches out for the glowing phone by his pillow and brings it to his face, squints at the screen, then his eyes light up, he grins smugly, speaks softly and swipes up with his thumb',
    's01_01_0174': 'medium shot, the slim young man with round glasses in a white shirt sits at a wooden desk under the bunk beds reciting English vocabulary from a book, tapping the page with his pen; then, keeping his eyes on the book, he turns a page, speaks toward the top bunk and glances at his wristwatch; morning light on his face, the top bunk visible at the top edge of the frame',
    's02_01_1116': 'medium close-up, the chubby young man in the dark grey open zip hoodie over a dark grey T-shirt sits at the window table with the open book; his phone beside the book lights up, he grabs it, unlocks it and smiles, puts it down, and two seconds later picks it up again to refresh',
    's03_01_0244': 'medium shot, the chubby young man in the dark grey hoodie sits at his messy desk with takeout boxes, a computer screen shows a grade sheet with one row in red; he lets out a long sigh and his shoulders sag; then his phone rings with a video call, he quickly sits up straight, wipes his face, forces a smile and holds the phone up in front of him to answer; his face in three-quarter view toward the camera',
    's06_01_0063': 'medium shot, the slim young man with round glasses in a white shirt opens the dorm door and steps in with a backpack, stops and looks toward a desk, worried; he quietly puts the backpack down, picks up a thermos and pours a glass of warm water; dim room, one warm desk lamp',
    's08_01_0809': 'medium close-up, the sturdy young man in a navy T-shirt sits on a chair in the circle, scratching his head shyly as he speaks, his voice getting quieter, an embarrassed smile; then he hesitates, turns his head toward someone beside him and speaks sincerely, face visible',
    's08_01_1461': 'medium shot in a small plain meeting room with a few students on chairs in a circle: the slim young man with round glasses in a white shirt stands up from his chair, pushes up his glasses and speaks calmly; then he turns toward his seated roommate and speaks warmly; the students seated beside him look up at him; the room stays the same',
    's09_01_0001': 'close-up, the chubby young man sits at his desk late at night holding up his phone, looking at his tired face in the front camera, unwashed hair, heavy dark circles; his finger hesitates over the shutter, he closes his eyes for a moment, takes a deep breath, speaks softly and taps the shutter; warm desk lamp',
    's09_01_0121': 'close-up, the chubby young man looks down typing on his phone and reads his words softly, face and mouth clearly visible, tired but honest expression; then he taps send, quickly flips the phone face down on the desk and stares at it nervously',
    's09_01_0918': 'close-up, the chubby young man looks at his phone as comments pop up, eyes red but smiling; after a moment he opens his contacts, taps his mother\'s number, raises the phone to his ear and takes a deep breath',
    # —— 否定写法改正面（H3 没有负面分支，写 no/not 常被当成要画的东西）、时间/衣着/人数改正 ——
    's01_00_0001': 'wide establishing shot at dawn, exterior of a Chinese university dormitory building, sky just getting light, a few windows glowing warm yellow, trees in front swaying, the walkway quiet and empty',
    's02_01_0450': 'medium shot by a window seat, sunlight on the wooden table, the chubby young man in the dark grey hoodie with his round face stands alone beside the table looking around at the light and the bookshelves with bright eyes, whispering happily, then nods and puts his books on the table; far in the background two other students sit at a distant table reading',
    's02_01_0790': 'medium shot, in a quiet corner of the library the thin young man with fluffy slightly curly black hair in an olive green knit sweater studies alone behind a tall stack of exam prep books, only books, papers and a pen on the table, turning a page and writing intently',
    's02_01_0852': 'close-up of the chubby young man in the dark grey hoodie with his round face: he crouches down at the library table and whispers curiously toward someone just outside the left edge of the frame, tilting his chin toward the corner; the left foreground is the wooden table edge',
    's02_01_1021': 'medium shot at a library table, two people: on the LEFT, slightly behind, the chubby young man in the dark grey hoodie leans over and whispers; on the RIGHT, the slim young man with round glasses in a white shirt sits at the table with his head tilted toward him and answers quietly, his eyes still on his book',
    's04_00_0481': 'medium shot, the chubby young man in the dark grey hoodie sits on the stone steps in front of the library scrolling his phone album, his finger stops on an old photo, his eyes shift, and he mutters to himself, making up his mind; face visible',
    's05_01_0440': 'medium shot in a real busy university canteen with long white dining tables and red plastic stools: the sturdy young man in a navy T-shirt walks up from the left with a food tray and pats the shoulder of the chubby young man in the dark grey hoodie on the right, grinning and teasing him, his face toward the camera; real canteen, real food trays',
    's05_01_0727': 'wide shot of a large canteen hall, rows of tables with red stools: the chubby young man in the dark grey hoodie puts his tray down, grabs his phone and walks quickly away from the camera toward the far exit with his head down, getting smaller in the frame; a few students far in the background; the camera stays wide',
    's06_01_0446': 'close-up of the chubby young man in the dark grey hoodie alone: his head is down on the desk, at first only the top of his black hair is visible; he slowly lifts his head and looks toward the right, eyes puffy and wet from crying, natural skin and natural eyes, his voice hoarse as he speaks, then lowers his head again; warm lamp light',
    's07_00_0054': 'wide shot, two young men walk slowly side by side along the edge of the red running track at night under the field lights, in silence: on the left the chubby one in the dark grey hoodie, on the right the thin one with fluffy slightly curly black hair in an olive green knit sweater',
    's07_00_0171': 'on the running track at night: the thin young man with fluffy slightly curly black hair in an olive green knit sweater walks beside the chubby young man in the dark grey hoodie, then the camera moves in to a close-up of the chubby young man walking with his head down, kicking a small pebble, then turning his face to ask, face visible, lit by the field lights; two clearly different people',
    's07_05_0001': 'flashback with a warm golden color grade: at a dorm door in the morning, two smiling classmates hand steaming takeaway lunch boxes to the thin young man with fluffy slightly curly black hair who has just opened the door, and pat his arm; he is stunned, then smiles',
    's08_01_0226': 'medium shot of three students seated on chairs in a circle in a plain meeting room, looking at each other in silence, from left to right: the thin young man with fluffy slightly curly black hair in an olive green sweater, the slim young man with round glasses in a white shirt, the chubby young man in the dark grey hoodie looking down and rubbing his hands; a person in a light blue shirt is partly visible at the left edge; the back of the room is empty',
    's08_01_0735': 'medium wide shot of three students seated on chairs in a plain meeting room, all laughing, the atmosphere relaxing, someone patting the arm of the person beside him, from left to right: the thin young man with fluffy slightly curly black hair in an olive green sweater, the slim young man with round glasses in a white shirt, the chubby young man in the dark grey hoodie; everyone stays seated',
    's08_01_2657': 'medium wide shot in a plain meeting room, three people: on the left the thin young man with fluffy slightly curly black hair in an olive green sweater sits on a chair; in the middle the slim young man with round glasses in a white shirt stands and starts clapping gently; on the right the chubby young man in the dark grey hoodie stands; the others join in the applause; the camera stays wide',
    's10_00_0102': 'medium shot on the sunny lawn, three young men in front, from left to right: the slim young man with round glasses in a white shirt laughs and reaches out to push down the phone held by the chubby young man in the dark grey hoodie in the middle; on the right the thin young man with fluffy slightly curly black hair in an olive green knit sweater; a few other students far behind on the lawn',
    's10_00_0332': 'medium close-up, the thin young man with fluffy slightly curly black hair in an olive green knit sweater on the sunny lawn casually waves his phone and speaks lightly, barely hiding a pleased smile',
    's10_00_0502': 'medium shot on a sunny lawn, three young men squeeze together for a selfie and smile brightly at the camera: on the left the slim young man with round glasses in a white shirt, in the middle the chubby young man in the dark grey hoodie holding up the phone and pressing the shutter, on the right the thin young man with fluffy slightly curly black hair in an olive green knit sweater; a few other students far behind on the lawn',
    's10_00_0787': 'medium shot on a sunny campus lawn with green trees, three young men in front: in the middle the chubby young man in the dark grey open hoodie puts his phone away and throws his arms around the shoulders of the two beside him, excitedly calling out; on the left the slim young man with round glasses in a white shirt; on the right the thin young man with fluffy slightly curly black hair in an olive green knit sweater',
})
EXTRA.update({   # 首帧提示正面写（Krea2 同样不擅长否定）；衣着和人物库一致
    's01_01_1016': dict(face_hidden=['lin'], kf_hint='从肩膀后面拍林晓的手和手机，看不到脸。他穿深灰色开襟连帽卫衣（帽子搭在脖子后面），袖口是深灰色的卫衣袖子，和前后镜头同一身衣服。'),
    's02_01_1116': dict(kf_hint='林晓穿深灰色开襟连帽卫衣（帽子搭在脖子后面），里面是深灰色T恤，和前后镜头同一身衣服。'),
    's05_01_0440': {'kf_hint': '这是真实的大学食堂：红色方块是食堂的红色塑料凳，白色长条是餐桌，远处有打饭窗口。左边是穿藏青色T恤、端着餐盘的健壮男生，右边是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓。真实照片质感。', 'kf_start': 2},
})
EN.update({   # 11-27 审查：描述写了「窗边/靠窗」但白模首帧看不到窗户 → 只写光线，不引入画面里没有的东西（踩坑 65）
    's01_01_0896': 'medium close-up in the dorm, the chubby young man in the dark grey hoodie holds up his phone for a selfie, tries two angles, turns his face toward the soft light from the side, chin down, then a practiced smile, taps the shutter and looks down at the photo; the slim young man with round glasses in a white shirt sits at a desk in the background',
    's01_01_1484': 'medium shot in the dorm, the chubby young man in the dark grey hoodie stands still grinning at his phone, his thumb refreshing the screen again and again, paying no attention to the room around him',
    's02_01_0450': 'medium shot beside a library table, warm sunlight falling across the wooden table, the chubby young man in the dark grey hoodie with his round face stands alone beside the table looking around at the light and the bookshelves with bright eyes, whispering happily, then nods and puts his books on the table; far in the background two other students sit at a distant table reading',
    's02_01_0539': 'medium shot at the wooden library table: the chubby young man in the dark grey hoodie, standing beside it, sets an open book at an angle, then places a latte with latte art and a pair of black-framed glasses beside it',
    's02_01_1116': 'medium close-up, the chubby young man in the dark grey open zip hoodie over a dark grey T-shirt sits at the library table with the open book; his phone beside the book lights up, he grabs it, unlocks it and smiles, puts it down, and two seconds later picks it up again to refresh',
})
EN.update({
    's01_01_1484': 'medium shot in the dorm, the chubby young man in the dark grey hoodie stands still grinning at his phone, his thumb refreshing the screen again and again, absorbed only in the screen',
    's02_01_0158': 'medium close-up in the library: the chubby young man in the dark grey hoodie, at first with his back to the camera near the doorway, turns toward the camera, whispering and waving his hand dismissively, then points off to the side toward the window seats',   # 白模开头是背影，随后转身（11-27 核对）
})
# ===== 11-27 全片首帧审查（逐张对照白模）发现的问题，当场修 =====
EN.update({
    's01_01_0543': 'close-up at floor level: the chubby young man\'s feet in dark sneakers land on the dorm floor at the bottom of the bunk ladder, then he turns and hurries off',   # 白模穿的是鞋，原文「光脚趿拖鞋」和首帧矛盾
    's01_01_0676': 'medium shot by the wall near the dorm door: the chubby young man in the dark grey hoodie brushes his teeth fast, foam in his mouth, his other hand fixing his messy hair',   # 白模首帧没有洗手台和镜子，不写
})
EXTRA.update({
    's01_01_0174': dict(kf_hint='画面里只有陈瑶一个人坐在书桌前背单词；左边的书桌、椅子和床梯旁边都是空的，没有别人。'),   # 首帧左后方多出一个白衬衫背影
    's01_01_0577': {'kf_hint': '这是真实的大学宿舍：画面里一共只有两个人——左边书桌前坐着戴圆框眼镜、穿白衬衫的清瘦男生陈瑶；后面站着体型明显偏胖、穿深灰色开襟连帽卫衣的林晓，刚从上铺下来拿毛巾和漱口杯。中间的过道是空的。真实的木头和金属床架，自然晨光，真实照片质感。', 'kf_start': 2},   # 首帧中间多出一个站着的白衬衫男生
    's01_01_0896': dict(kf_hint='前面是林晓：深灰色开襟连帽卫衣，卫衣里面是深灰色圆领T恤；后面书桌前坐着穿白衬衫的陈瑶。'),   # 首帧林晓卫衣里变成了白衬衫（陈瑶的衣着串到他身上）
})
EXTRA.update({   # 首帧审查第 3 批（11-27）
    's02_01_0221': dict(kf_hint='从左到右：左边桌子旁坐着的是戴圆框眼镜、穿白衬衫的清瘦男生陈瑶；右边远处正在走动的是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓。画面里只有这两个人，坐着的那个是清瘦的白衬衫男生。'),   # 首帧把坐着的陈瑶画成了第二个穿深色卫衣的胖子
    's02_01_0450': dict(kf_hint='画面里只有林晓一个人站着：体型明显偏胖、穿深灰色开襟连帽卫衣，站在桌边。后面远处的桌边坐着两个低头看书的同学，一共只有这两个人坐着。'),   # 首帧多出一个站着的人、后面坐着的人也多了；原来的 bg_face=classA 是掩盖多出的人，去掉
})
EXTRA['s02_01_0450'].pop('bg_face', None)
EXTRA.update({   # 首帧审查第 4 批（11-27）
    's02_01_0450': dict(kf_start=4, kf_hint='画面里只有林晓一个人站着：体型明显偏胖、穿深灰色开襟连帽卫衣，站在桌边。后面远处的桌边坐着两个低头看书的同学，一共只有这两个人坐着。'),   # 两次重做都在林晓左边多出一个站着的人 → 少重绘（从第 4 步开始），更多保留白模构图
    's02_01_1021': dict(noswap=True, kf_hint='画面里两个人：左后方是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓，弯着腰凑到右边那人耳边小声说话，他的上半身和脸都在画面里；右边坐在桌前的是戴圆框眼镜、穿白衬衫的清瘦男生陈瑶。'),   # 首帧里林晓不见了，只剩一件外套
})
EN.update({
    's04_00_0001': 'wide shot, Saturday morning, the chubby young man in the dark grey hoodie with a backpack walks briskly across a wide sunny paved plaza toward the library entrance off-screen, a few autumn-colored trees and a bench on the right',   # 白模是空旷广场，看不到台阶和玻璃门，不写（踩坑 65/76）
})
EXTRA.update({
    's05_01_0001': dict(kf_hint='前面是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓在看手机；后面站着的是清瘦、蓬松微卷黑发、穿橄榄绿针织毛衣和卡其色工装裤的周明远。'),   # 首帧周明远上衣成了深灰色，和下一镜 0068 的橄榄绿毛衣接不上
})
EXTRA.update({
    's05_01_0001': dict(kf_start=2, kf_hint='前面是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓在看手机；后面站着的是清瘦、蓬松微卷黑发、穿橄榄绿针织毛衣和卡其色工装裤的周明远，他的毛衣是明显的橄榄绿色。'),   # 第二次仍是深色上衣：白模衣服偏暗，重绘力度加大一档
    's05_01_0440': {'kf_hint': '这是真实的大学食堂：红色方块是红色塑料凳，白色长条是餐桌。左下前景是穿橄榄绿针织毛衣的周明远的背影；画面中间只站着一个人——穿藏青色T恤、端着餐盘的健壮男生；右下角只露出体型偏胖的林晓的黑色头顶。画面里一共三个人。真实照片质感。', 'kf_start': 2},   # 旧提示「左边端餐盘、右边林晓」和白模站位不符，中间多画了一个人
})

EXTRA['s05_01_0001'] = dict(kf_hint='前面是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓在看手机；后面站着另一个排队的同学。')   # 见 visible_overrides.json 的说明
EXTRA['s05_01_0440'] = {'kf_hint': '这是真实的大学食堂：红色方块是红色塑料凳，白色长条是餐桌。左下前景是穿橄榄绿针织毛衣的周明远的背影；画面中间只站着一个人——穿藏青色T恤、端着餐盘的健壮男生；右下角只露出体型偏胖的林晓的黑色头顶。画面里一共三个人。真实照片质感。'}   # 重绘力度 2 时两次都多画一个人 → 恢复默认（第 3 步开始）
# —— 回忆镜头：调色改在后期统一做（cloud/postfix_text.json 的 grade），提示词只写光线和动作（11-27：首帧不是冷色、提示词却要冷蓝，两边打架）——
EN.update({
    's07_01_0001': 'medium shot in a dark dorm room at night: the thin young man with fluffy slightly curly black hair in an olive green knit sweater stands beside the bunk bed railing holding his ringing phone, staring at the screen, unable to answer',   # 白模全程站着（原文「坐在床上抱膝」和白模不符）
    's07_01_0023': 'extreme close-up of a smartphone screen showing an incoming call, the phone keeps ringing in his hand; the screen text stays exactly as in Picture 1',
    's07_01_0056': 'medium shot in a dark dorm room at night: the thin young man with fluffy slightly curly black hair in an olive green knit sweater stands beside the bunk bed railing, still holding the ringing phone, his head sinking lower as he lets it ring',
    's07_03_0023': 'extreme close-up of a smartphone screen in the dark, a message being typed, his thumb hovering over the send button; the screen text stays exactly as in Picture 1',
})
for _t in ('s07_01_0001', 's07_01_0023', 's07_01_0056', 's07_03_0001', 's07_03_0023', 's07_03_0152'): EXTRA.setdefault(_t, {})['flashback'] = 'cold'
for _t in ('s07_05_0001',): EXTRA.setdefault(_t, {})['flashback'] = 'warm'
EXTRA['s07_00_0469'] = dict(kf_hint='画面里只有这两个人：左边是清瘦、蓬松卷发、穿橄榄绿针织毛衣的周明远，右边是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓，两人面对面站在跑道边；周围没有别人。')   # 首帧周明远身后多出一个人影
EN.update({   # 回忆镜头去掉调色字样（后期统一调色）
    's07_03_0001': 'late at night in a dark dorm, the thin young man types on his phone, the screen light on his tired face',
    's07_03_0152': 'late at night in a dark dorm, the thin young man types on his phone, the screen light on his tired face',
    's07_05_0001': 'at a dorm door in the morning, two smiling classmates hand steaming takeaway lunch boxes to the thin young man with fluffy slightly curly black hair who has just opened the door, and pat his arm; he is stunned, then smiles',
})
# —— 首帧审查第 9 批（11-27）——
EN['s07_05_0001'] = 'at a dorm door in the morning, the thin young man with fluffy slightly curly black hair in an olive green knit sweater stands alone in the open doorway, taking steaming takeaway lunch boxes handed in by friends just outside the frame; he is stunned for a moment, then smiles'   # 白模门口只有周明远，送饭的同学在画外（原文写两人入画 → 首帧多画一个人）
EXTRA.setdefault('s07_05_0001', {}).update(kf_hint='画面里只有周明远一个人：清瘦、蓬松微卷黑发、穿橄榄绿针织毛衣，站在打开的宿舍门口；门外的人不在画面里。', flashback='warm')
EXTRA['s07_00_0469'] = dict(kf_start=4, kf_hint='画面里只有这两个人：左边是清瘦、蓬松卷发、穿橄榄绿针织毛衣的周明远，右边是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓，两人面对面站在跑道边；后面只有路灯杆和树，没有别人。')   # 两次都把身后的灯杆画成人 → 少重绘
EXTRA['s07_06_0495'] = dict(kf_start=4, kf_hint='画面里只有两个人：背对镜头站在前面的是体型明显偏胖、穿深灰色开襟连帽卫衣的林晓；他对面站着清瘦、蓬松卷发、穿橄榄绿针织毛衣的周明远，正伸手拍林晓的肩膀。没有第三个人。')   # 首帧多出一个正对镜头的林晓
EXTRA['s08_01_0001'] = dict(kf_hint='从左到右坐着四个学生：最左边是扎低马尾、穿白色针织上衣的女生同学乙；第二个是穿藏青色T恤的健壮男生同学甲；第三个是男生周明远——清瘦、蓬松微卷的黑色短发、穿橄榄绿针织毛衣；第四个是戴浅金色圆框眼镜、穿白衬衫的清瘦男生陈瑶。中间站着穿浅蓝衬衫、系深蓝领带的王老师。画面里只有同学乙一个女生，其他都是男生。')   # 首帧把周明远画成了扎马尾的女生、陈瑶没戴眼镜
EXTRA['s08_01_0226'] = dict(kf_start=4, kf_hint='从左到右：左边是清瘦的周明远（蓬松卷发、橄榄绿毛衣），中间是陈瑶（白衬衫、圆框眼镜），右边是体型明显偏胖的林晓（深灰连帽卫衣）；画面里只有这三个学生坐着，他们身后的桌子和椅子都是空的，没有人。')   # 首帧后排多出一个坐着的白衬衫的人
EXTRA.setdefault('s07_05_0001', {}).update(kf_start=4)   # 第二次门口仍是两个人 → 少重绘
EXTRA['s08_01_0001'] = dict(kf_start=4, kf_hint='画面里一共 5 个人，只有最左边那个扎马尾的是女生，其他 4 个都是男生。从左数第三个坐着的是男生周明远：短卷发、橄榄绿毛衣、工装长裤。第四个坐着的男生陈瑶戴圆框眼镜、穿白衬衫。')   # 长提示 + 重绘力度 3 时周明远两次都被画成女生、还多出一个女生 → 精简 + 少重绘
EXTRA['s08_01_0001'] = dict(kf_start=5, kf_hint='画面里一共 5 个人，只有最左边扎马尾的是女生，其他 4 个都是男生。从左数第三个坐着的是男生周明远：短卷发、橄榄绿毛衣、工装长裤。第四个坐着的男生陈瑶戴圆框眼镜、穿白衬衫。')   # 力度 3/4 都把周明远画成女生（第三版多出两个女生）→ 力度 5，基本照白模人物结构
EXTRA['s09_01_0121'] = dict(kf_hint='画面里是林晓一个人：体型明显偏胖的男大学生，圆脸、略有双下巴，男生的黑色碎发短发（和上一镜一样，不是女生的精致短发），穿深灰色开襟连帽卫衣，深夜在台灯下低头打字。')   # 换脸后发型仍偏女性化，和相邻 0001 不像同一个人
# —— 视频审查（11-27）：s01_01_0348 视频把首帧的光床板改成了盖被子、整个房间都换了（描述写了「躺在被子里」，首帧没有被子）→ 描述里「一直在场」的道具/状态必须是首帧里有的 ——
EN.update({
    's01_01_0001': 'close-up on the top bunk: a smartphone beside the sleeping chubby young man lights up again and again with notifications; he lies asleep in a dark grey T-shirt, frowns and stirs a little',
    's01_01_0054': 'medium close-up beside the top bunk bed: the chubby young man in the dark grey hoodie, half awake, reaches out for the glowing phone beside him and brings it to his face, squints at the screen, then his eyes light up, he grins smugly, speaks softly and swipes up with his thumb',
    's01_01_0348': 'medium shot from above the top bunk: the chubby young man in the dark grey hoodie lies on his back on the bed holding his phone; his eyes suddenly go wide in shock and he starts to sit up, shouting',
    's01_01_0411': 'medium shot from behind and above: the chubby young man in the dark grey hoodie scrambles off the top bunk and climbs down the bunk ladder in a hurry, landing beside his desk',
    's01_01_0758': 'medium shot by the dorm door: the chubby young man in the dark grey hoodie puts down his toothbrush, rubs his face with a towel, forces a smile, then turns and walks past the camera into the room',
    's03_01_0001': 'medium shot, the chubby young man in the dark grey hoodie lies on his back on his bed holding his phone up above his face, scrolling through comments and grinning smugly',
    's03_01_0152': 'medium shot, the chubby young man in the dark grey hoodie lies on his back on his bed holding his phone up above his face, swiping up again and again, his grin growing wider',
    's03_01_0244': 'medium shot, the chubby young man in the dark grey hoodie sits at his desk staring at the screen in front of him, where his grades show a failed course; he lets out a long sigh and his shoulders sag; then his phone rings with a video call, he quickly sits up straight, wipes his face, forces a smile and holds the phone up in front of him to answer; his face in three-quarter view toward the camera',
})
# —— 视频审查：跟拍镜头 s01_01_0411 镜头移动后编出了办公室、复制出第二个林晓（深度 0.3 约束不住首帧外的空间）→ 加强控制试拍 ——
EXTRA.setdefault('s01_01_0411', {}).update(depth_w=0.7, pose_w=0.9)
EXTRA['s01_01_0174'] = dict(kf_start=4, kf_hint='画面里只有陈瑶一个人坐在书桌前背单词；他身后和左边的书桌、椅子、床梯旁边都是空的，没有别人。')   # 统一样式重做后身后又多出一个白衬衫的人 → 少重绘
EXTRA['s01_01_1174'] = dict(kf_hint='书桌、书架和椅子都是浅木色的（不是橙色），和这间宿舍其他家具一样。')   # 统一样式后仍画成橙色桌椅
EXTRA['s10_00_0001'] = dict(kf_start=4, kf_hint='前面并排站着三个主角：穿白衬衫戴圆框眼镜的陈瑶、穿深灰卫衣的胖胖的林晓、穿橄榄绿毛衣的周明远；画面里只有陈瑶一个人穿白衬衫，远处路过的学生穿别的颜色的衣服，离他们很远。')   # 新草坪首帧里陈瑶旁边多出一个同样穿白衬衫的人，像双胞胎
EXTRA['s01_01_1174'] = dict(kf_start=2, kf_hint='书桌、书架和椅子都是浅木色的原木家具，和这间宿舍其他家具一样。')   # 白模这套桌椅本身是橙色材质，力度 3 时照着画成橙色；「不是橙色」是否定写法不起作用 → 正面写 + 多重绘
EXTRA['s01_01_1174'] = dict(kf_start=3, kf_hint='画面里只有陈瑶一个人坐在书桌前。书桌、书架和椅子都是浅木色的原木家具，和这间宿舍其他家具一样。')   # 力度 2 多出一个陈瑶；力度 3 + 正面写法
EXTRA['s10_00_0001'] = dict(kf_start=3, kf_hint='前面并排站着三个主角：穿白衬衫戴圆框眼镜的陈瑶、穿深灰卫衣的胖胖的林晓、穿橄榄绿毛衣的周明远；只有陈瑶穿白衬衫。远处小路上路过的两个学生穿深色和彩色的衣服、背着书包，离他们很远。真实的校园草坪和树木，真实照片质感。')   # 力度 4 树和草地变回 3D 白模样子；力度 3 + 写清路人穿着
# —— 视频审查（11-28）——
EN['s01_01_0543'] = 'close-up at floor level: the chubby young man\'s feet in dark sneakers land on the dorm floor at the bottom of the bunk ladder, then he turns and hurries off; he wears the same dark grey open zip hoodie over a dark grey T-shirt and dark blue jeans'   # 视频往上带到身体时成了浅灰 T 恤，写明衣着
EN['s01_01_0896'] = 'medium close-up in the dorm, the chubby young man in the dark grey hoodie holds up his phone for a selfie, tries two angles, turns his face toward the soft light from the side, chin down, then a practiced smile, taps the shutter and looks down at the photo; the slim young man with round glasses in a white shirt stays seated at his desk far in the background the whole time'   # 视频里陈瑶从后面的书桌走到了林晓身边
EXTRA.setdefault('s01_01_1016', {}).update(depth_w=0.7, pose_w=0.9)   # 视频后半段绕到正面露脸（应始终越肩、看不到脸）→ 加强控制
EN['s02_01_0790'] = 'medium shot, in a quiet corner of the library the thin young man with fluffy slightly curly black hair in an olive green knit sweater sits alone at the table, head down, writing intently and turning a page'   # 视频里桌上凭空冒出一摞书（首帧桌上是空的，原文写了 tall stack of books）
# —— 视频审查（11-28）：手机屏幕特写 s03_01_0023 后半段变成一个陌生人在另一间宿舍（纯手机特写没有人物骨架约束）→ 6 个手机特写一起锁住 ——
for _t in ('s03_01_0023', 's05_01_0090', 's07_01_0023', 's07_03_0023', 's09_01_0707', 's10_00_0586'):
    EN[_t] = EN[_t].replace('extreme close-up of a smartphone screen', 'extreme close-up that stays on a smartphone screen held in a hand for the whole shot, only the screen, the phone edge and the fingers in frame,', 1)
    EXTRA.setdefault(_t, {}).update(depth_w=0.9)
EN['s03_01_0244'] = 'medium shot, the chubby young man in the dark grey hoodie sits at his desk staring at the screen in front of him, where his grades show a failed course; he lets out a long sigh and his shoulders sag; then his phone rings with a video call, he quickly sits up straight, wipes his face, forces a smile and holds the phone up in front of his face at arm\'s length, looking at the screen as the video call connects; his face in three-quarter view toward the camera'   # 视频里把手机贴到耳边打电话，和下一场视频通话对不上
