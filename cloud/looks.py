# -*- coding: utf-8 -*-
"""角色外貌描述（写实化提示词用），与 2026-11-22 定稿的白模、标准长相照片（assets/identity/<cid>.png）一致。
云端脚本（keyframes.py / video_run.py）和本地打包（pack_for_cloud.py）共用。改了白模造型要同步改这里。"""

LOOK = {
 'lin':    '一位20岁微胖的中国男大学生，圆脸，小眼睛，略有双下巴，黑色碎发短发，穿深灰色开襟连帽卫衣、里面深灰色T恤、深蓝色牛仔裤，憨厚腼腆',
 'chen':   '一位21岁高瘦的中国男大学生，鹅蛋脸，戴浅金色圆形细框眼镜，黑色中分刘海短发，穿白衬衫、黑色长裤，沉稳安静',
 'zhou':   '一位22岁清瘦的中国男研究生，长方脸，高颧骨，轻微眼袋，黑色偏长蓬松微卷的短发、厚刘海，穿橄榄绿针织毛衣、工装裤，温和踏实',
 'wang':   '一位38岁的中国男辅导员，方脸微胖，有笑纹，黑色侧分短发，穿浅蓝色衬衫系深蓝色领带、灰色西裤，略有小肚子，真诚温暖',
 'classA': '一位20岁健壮的中国男大学生，菱形脸，下巴突出，黑色两侧推短的短发，穿深藏青色T恤、牛仔裤，爱开玩笑',
 'classB': '一位20岁苗条的中国女大学生，鹅蛋脸，平直眉，杏眼，乌黑长发中分梳成低马尾、戴黑色发箍，穿白色水手服（黑色水手领带白边、蓝色领巾）、黑色百褶短裙、黑色丝袜、黑色玛丽珍鞋，文静害羞',
 'mom':    '一位四十出头的中国母亲，气质干练、不显老，黑色微卷的波浪短发，淡妆红唇，穿黑色V领垂坠长袖上衣、暖棕色长裤，右耳戴金色扇形耳环',
}
# 英文版（视频模型多数对英文提示词更稳）
LOOK_EN = {
 'lin':    'a chubby 20-year-old Chinese male college student with a round face, small eyes, slight double chin, short messy black hair, dark grey open hoodie over a dark grey T-shirt, dark blue jeans',
 'chen':   'a tall slim 21-year-old Chinese male college student with an oval face, thin round light-gold wire glasses, short black hair with center-parted bangs, white shirt, black trousers',
 'zhou':   'a lean 22-year-old Chinese male graduate student with a long face, high cheekbones, slight eye bags, fluffy slightly curly black hair with thick bangs, olive green knit sweater, cargo pants',
 'wang':   'a 38-year-old Chinese male counselor with a square, slightly chubby face, smile lines, side-parted short black hair, light blue shirt with a navy tie, grey trousers',
 'classA': 'a sturdy 20-year-old Chinese male college student with a diamond-shaped face, prominent chin, short black hair with faded sides, navy T-shirt, jeans',
 'classB': 'a slim 20-year-old Chinese female college student with an oval face, straight brows, almond eyes, long black hair in a low ponytail with a black headband, white sailor-style top with black sailor collar and blue scarf, black pleated mini skirt, black stockings',
 'mom':    'an elegant Chinese mother in her early forties, short wavy black bob hair, light makeup with red lips, black V-neck draped long-sleeve top, warm brown trousers, a gold fan-shaped earring',
}
NAME = {'lin': '林晓', 'chen': '陈瑶', 'zhou': '周明远', 'wang': '王老师', 'classA': '同学甲', 'classB': '同学乙', 'mom': '林母'}
STYLE_EN = ('photorealistic live-action film still, shot on a cinema camera, natural lighting, realistic skin texture, '
            'contemporary China, 2020s')
NEG_EN = ('cartoon, anime, 3d render, cgi, video game, doll, plastic skin, blurry, deformed face, extra fingers, extra people, '
          'text, watermark, subtitles, flickering, low quality, oversaturated')
