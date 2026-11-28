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

def zh(set_name): return LIGHT.get(set_name, ('', ''))[0]
def en(set_name): return LIGHT.get(set_name, ('', ''))[1]

# 回忆镜头有自己的调色（剧本写明冷蓝/暖金），不能套场景平时的光线（s07_01/03 夜里宿舍回忆是冷蓝，不是暖黄台灯）
FLASH = {
    'cold blue': ('这是回忆画面，整体冷蓝色调，昏暗的夜里，人脸主要被手机屏幕的冷光照亮，周围很暗。',
                  'This is a flashback with a cold blue color grade: a dim night, his face lit mainly by the cool glow of the phone screen, the surroundings dark.'),
    'warm golden': ('这是回忆画面，整体暖金色调，温暖柔和的晨光，画面明亮温馨。',
                    'This is a flashback with a warm golden color grade: soft warm morning light, bright and cozy.'),
}
def for_task(task):
    """(中文, 英文)：回忆镜头按调色，其他按场景"""
    p = task.get('prompt', '').lower()
    for k, v in FLASH.items():
        if k + ' color grade' in p: return v
    return LIGHT.get(task.get('set', ''), ('', ''))
