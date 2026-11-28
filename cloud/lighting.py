# -*- coding: utf-8 -*-
"""每个场景的时间和光线（11-27，踩坑记录 70）：首帧（中文，Krea2 二转三）和视频（英文，H3）用同一套说法。
白模的灯光是统一的明亮日光，二转三照着画，傍晚、夜里的戏首帧也成了白天，视频里就出现「台灯亮着、窗外大白天」的时间错乱。
视频提示词只写光线和时间，不写背景里有什么物体（首帧模式下写首帧没有的东西会让模型换背景，踩坑 65）。"""
# 场景（segments.py 的 set_name）→ (中文：首帧, 英文：视频)
LIGHT = {
    'dorm_am':     ('清晨的宿舍，柔和的自然晨光从窗户照进来，室内明亮清爽，台灯关着。',
                    'Soft natural morning daylight fills the room from the window; the desk lamps are off.'),
    'dorm_pm':     ('下午的宿舍，温暖的午后阳光斜照进房间，室内明亮，台灯关着。',
                    'Warm afternoon sunlight slants into the room; the room is bright and the desk lamps are off.'),
    'dorm_dusk':   ('傍晚的宿舍，窗外天色已经暗下来，房间里主要靠一盏暖黄色台灯照明，墙面和角落偏暗，整体是暖色的昏黄光线，不是白天。',
                    'It is early evening: the daylight outside has faded, the room is lit mainly by one warm yellow desk lamp, walls and corners fall into soft warm shadow.'),
    'dorm_nt':     ('夜晚的宿舍，窗外漆黑，房间里只有暖黄色台灯和手机屏幕的光，周围偏暗，不是白天。',
                    'It is night: the room is lit only by warm desk lamps and phone screens, with deep shadows around them.'),
    'ext_dorm_am': ('清晨的宿舍楼外，柔和的晨光。', 'Soft early-morning daylight.'),
    'ext_dorm_pm': ('下午的宿舍楼外，温暖的阳光。', 'Warm afternoon sunlight.'),
    'ext_dorm_nt': ('夜晚的宿舍楼外，天是黑的，窗户亮着暖黄的灯，路灯照明。', 'It is night: the sky is dark, lit windows glow warm yellow and street lamps light the walkway.'),
    'ext_library': ('白天的图书馆外，明亮的日光。', 'Bright daylight.'),
    'lib':         ('白天的图书馆阅览室，明亮的日光加上室内灯光，光线均匀。', 'Bright daytime light from the windows mixed with even indoor lighting.'),
    'libdoor':     ('白天的图书馆门厅，明亮的日光从门外照进来。', 'Bright daylight comes in through the glass doors.'),
    'ext_canteen': ('中午的食堂外，明亮的日光。', 'Bright midday daylight.'),
    'canteen':     ('中午的食堂里，明亮的日光和顶灯。', 'Bright midday light from windows and ceiling lamps.'),
    'ext_dusk':    ('傍晚的校园路上，天空是橙紫色的晚霞，路灯刚刚亮起。', 'It is dusk: an orange and purple sky, street lamps just turning on.'),
    'ext_corridor': ('白天的教学楼走廊，窗户透进日光。', 'Daylight comes in through the corridor windows.'),
    'class':       ('白天的教室，明亮的日光和日光灯。', 'Bright daytime light from the windows and fluorescent ceiling lights.'),
    'track':       ('刚入夜的操场，天边还剩一点余晖，场边的照明灯和路灯已经亮起，照亮跑道。', 'It is just after nightfall: the last glow fades at the horizon while floodlights and street lamps beside the field light the running track.'),   # 剧本「夜幕刚降临」，首帧天边有余晖（11-27 首帧审查统一）
    'lawn':        ('晴天的校园草坪，明亮的阳光，蓝天白云。', 'Bright sunny daylight.'),
    'home':        ('白天的家里客厅，日光从窗户照进来。', 'Daylight comes in through the living-room window.'),
    'home_nt':     ('夜晚的家里客厅，窗外是黑的，暖色落地灯照明，周围偏暗。', 'It is night: a warm floor lamp lights the living room, the rest falls into soft shadow.'),
}

# 同一个地点的固定装修样式（只规定颜色和材质，不加物体；11-27 用户：「每段连在一起看能不能看出来是同一场景同一时间」——
# 早晨宿舍 16 个镜头墙色、床架、桌椅各画各的：粉白墙/灰蓝墙、木床架/金属床架、白桌橙椅；下午宿舍的床只是个白方块）
# 早中晚夜四场宿舍是同一间屋，以已经连贯的傍晚、夜里两场为准
DORM_STYLE = ('这是同一间中国大学四人宿舍，装修固定：浅灰白色墙面，浅木色书桌、书架和衣柜，深灰色金属的上床下桌床架和梯子，浅灰色地砖；'
              '床上铺着床垫、浅蓝色格子床单和白色枕头。画面里出现的墙、家具和床都按这个样式。')
STYLE = {s: DORM_STYLE for s in ('dorm_am', 'dorm_pm', 'dorm_dusk', 'dorm_nt')}
def style_zh(set_name): return STYLE.get(set_name, '')

def zh(set_name): return LIGHT.get(set_name, ('', ''))[0]
def en(set_name): return LIGHT.get(set_name, ('', ''))[1]

# 回忆镜头：调色在后期统一做（postfix_text.json 的 grade；11-27 起），这里只给光线，不让模型画色调（首帧不是冷色时两边会打架）
FLASH = {
    'cold': ('这是夜里的回忆画面：昏暗的宿舍，人脸主要被手机屏幕的光照亮，周围很暗。',
             'It is night in a dim dorm: his face is lit mainly by the glow of the phone screen, the surroundings dark.'),
    'warm': ('这是回忆画面：清晨柔和温暖的光，画面明亮温馨。', 'Soft warm early-morning light, bright and cozy.'),
}
def for_task(task):
    """(中文, 英文)：回忆镜头（task 的 flashback 字段）按回忆光线，其他按场景"""
    fb = task.get('flashback')
    if fb in FLASH: return FLASH[fb]
    return LIGHT.get(task.get('set', ''), ('', ''))