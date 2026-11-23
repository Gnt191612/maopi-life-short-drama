# -*- coding: utf-8 -*-
"""每个场景的背景描述（写进云端写实化提示词）。白模里背景只有方块墙和家具轮廓，AI 按提示词补细节；
原来只写一句「Chinese university campus」，宿舍、图书馆、食堂画出来都差不多（2026-11-22 用户要求优化背景）。
写法：真实的中国高校/家庭环境、具体的陈设和光线；不写人物（人物由剧本描述和参考图决定）。新场景加一行即可。"""
BG = {
 'dorm_am':   'a real Chinese university four-person dorm room in the morning: loft beds above wooden desks, metal ladders, '
              'clothes hanging on the bed rails, books and a water bottle on the desks, soft morning sunlight through the window and curtains',
 'dorm_pm':   'a real Chinese university four-person dorm room in the afternoon: loft beds above wooden desks, bookshelves, a laptop and snacks on the desk, '
              'warm afternoon sunlight slanting through the window',
 'dorm_dusk': 'a Chinese university dorm room at dusk: loft beds above desks, the room lit by one warm desk lamp, orange evening sky outside the window',
 'dorm_nt':   'a Chinese university dorm room at night: loft beds above desks, warm desk lamps and the glow of phone screens, dark blue night outside the window, '
              'cosy and lived-in, clothes on the bed rails',
 'ext_dorm_am': 'the outside of a Chinese university dormitory building in the morning: rows of windows with balconies and drying clothes, '
                'tree-lined walkway, bicycles parked in front, clear morning light',
 'ext_dorm_pm': 'the outside of a Chinese university dormitory building in the afternoon, tree-lined walkway, bicycles, students passing, warm sunlight',
 'ext_dorm_nt': 'a Chinese university dormitory building at night, many windows lit warm yellow, street lamps along the walkway, quiet campus',
 'ext_library': 'the front of a large modern Chinese university library building, wide steps, glass facade, trees and lawn, students with backpacks, daylight',
 'lib':       'inside a bright modern Chinese university library reading room: long wooden tables with desk lamps, tall bookshelves full of books, '
              'large windows with daylight, quiet study atmosphere',
 'libdoor':   'the entrance hall of a Chinese university library: glass doors, a security gate, notice boards, daylight from outside',
 'ext_canteen': 'the outside of a busy Chinese university canteen building at lunchtime, students walking in groups, trees, bicycles, bright daylight',
 'canteen':   'inside a busy Chinese university canteen: rows of tables and stools, food counters with steaming dishes in the background, '
              'students eating, fluorescent and window light',
 'ext_dusk':  'a Chinese university campus road at dusk, street lamps just turning on, trees silhouetted against an orange and purple sky',
 'ext_corridor': 'a teaching building corridor in a Chinese university: tiled floor, classroom doors, notice boards, windows with daylight',
 'class':     'a small classroom in a Chinese university used for a sharing session: chairs arranged in a circle, a green chalkboard, '
              'windows with soft daylight, plain walls with a few posters',
 'track':     'a Chinese university outdoor running track: red rubber track with white lane lines, green football field, '
              'stands and trees in the background, open sky',
 'lawn':      'a sunny green lawn on a Chinese university campus, teaching buildings and trees in the background, blue sky with white clouds, students strolling',
 'home':      'a modest Chinese family apartment living room in the daytime: sofa, tea table, TV cabinet, family photos, potted plants, daylight from the balcony',
 'home_nt':   'a modest Chinese family apartment at night: sofa and tea table lit by a warm floor lamp, family photos on the wall, quiet',
}

MOVE_EN = {'push': 'slow cinematic push-in camera', 'arc': 'slow orbiting camera move around the characters', 'track': 'smooth tracking camera following the movement',
           'hand': 'subtle handheld close-up camera', 'static': 'locked-off static camera'}

def bg(set_name):
    return BG.get(set_name, 'a real Chinese university campus scene')
