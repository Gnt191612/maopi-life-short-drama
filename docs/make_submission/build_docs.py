# -*- coding: utf-8 -*-
"""生成课程提交材料：分镜脚本.docx、服道化设计.docx（数据全部取自拍摄工程，白模重拍后重新运行即可更新）。
运行：$env:V11_PREVIEW='1'; python docs/make_submission/build_docs.py [输出目录]
依赖：python-docx、opencv-python；需要先拍完白模（build/shots/*_cuts.json、build/renders_preview/）和
blender/tests/costume_render.py 渲染的角色全身图（build/submission/costume_*）。"""
import os, sys, json, re, runpy, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'story')); sys.path.insert(0, os.path.join(ROOT, 'cloud'))
import config, segments as S, lines, music, backgrounds
import cv2, numpy as np
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dist', 'submission')
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(config.ROOT, 'build', 'submission', 'thumbs'); os.makedirs(TMP, exist_ok=True)
FPS = S.FPS
TITLE = '毛坯人生，精装朋友圈'
TEAM = '队长：郭宁桐　　队员：梁钧咏　王启元　刘洋　蔡磊　仝启瀚　刘译阳'
CN = {'林晓': '林晓', '陈瑶': '陈瑶', '周明远': '周明远', '王老师': '王老师', '林母': '林母', '同学甲': '同学甲', '同学乙': '同学乙'}
CID2N = {v: k for k, v in S.CID.items()}
PLACE = {'ext_dorm_am': '宿舍楼外·清晨', 'dorm_am': '男生宿舍·清晨', 'ext_library': '图书馆外景', 'lib': '图书馆阅览室',
         'ext_dorm_pm': '宿舍楼外·午后', 'dorm_pm': '男生宿舍·午后', 'home': '林晓家客厅', 'libdoor': '图书馆门口',
         'ext_canteen': '食堂外景', 'canteen': '学生食堂', 'ext_dusk': '校园道路·黄昏', 'dorm_dusk': '男生宿舍·黄昏',
         'track': '夜晚操场', 'dorm_nt': '男生宿舍·夜', 'ext_corridor': '教学楼走廊', 'class': '活动室（茶话会）',
         'ext_dorm_nt': '宿舍楼外·夜', 'home_nt': '林晓家·夜', 'lawn': '校园草坪·初夏'}
SHOT_CN = {'ECU': '大特写', 'CU': '特写', 'MCU': '近景', 'MS': '中景', 'WS': '全景', 'EST': '空镜（远景）', 'PHONE': '手机屏幕特写'}
MOVE_CN = {'push': '缓推', 'arc': '弧形移动', 'track': '跟拍（摇）', 'hand': '轻推＋手持感', 'static': '固定'}
SFX_CN = {'ding': '消息提示音', 'whoosh': '急促音效', 'send': '发送音', 'thud': '手机扣桌声', 'ring': '来电铃声', 'door': '开门声',
          'laugh': '笑声', 'clap': '掌声', 'shutter': '快门声', 'notify': '提示音', 'vibrate': '手机震动'}
MUSIC_CN = {'ai_morning_citypop': '原创 City Pop（轻快）', 'ai_library_lofi': '原创 Lo-fi（俏皮）', 'ai_sneaky_pizz': '原创拨弦（鬼祟）',
            'ai_canteen_funk': '原创 Funk（渐紧张）', 'gnossienne1': '萨蒂《玄秘曲》第一首', 'ai_night_chillwave': '原创 Chillwave（怀旧）',
            'gymnopedie1': '萨蒂《裸体歌舞》第一首', 'ai_teaparty_guitar': '原创指弹吉他（温暖）', 'nocturne_op9_2': '肖邦《夜曲》Op.9 No.2',
            'clair_de_lune': '德彪西《月光》', 'ai_ending_indiepop': '原创 Indie Pop（明亮）', 'bach_prelude_c': '巴赫《C 大调前奏曲》'}

def shot_type(en):
    e = (en or '').lower()
    if 'extreme close' in e: return 'ECU'
    if 'medium close' in e: return 'MCU'
    if 'close-up' in e or 'close up' in e: return 'CU'
    if 'wide' in e or 'long shot' in e: return 'WS'
    return 'MS'

def acts(b):
    a = b.get('act') or ''
    return '；'.join(a) if isinstance(a, list) else a

# ---------------- 数据 ----------------
SCN = {s['id']: s for s in S.SCENES}
CUE_AT = {}
for a, b_, trk, _ in music.CUES: CUE_AT[a] = trk
shots, scenes_out = [], []
t_film = 0.0
for sid, scene, set_name, beats in S.segments():
    tl_p = os.path.join(config.SHOTS, sid + '_timeline.json'); cp = os.path.join(config.SHOTS, sid + '_cuts.json')
    if not os.path.exists(tl_p) or not os.path.exists(cp): print('跳过（未拍）', sid); continue
    tl = json.load(open(tl_p, encoding='utf-8')); cuts = json.load(open(cp, encoding='utf-8'))
    byid = {b['id']: b for b in beats}
    n_end = max(b['f1'] for b in tl); bounds = [c[0] for c in cuts] + [n_end + 1]
    seg_shots = []
    for k, c in enumerate(cuts):
        f0, f1 = bounds[k], bounds[k + 1] - 1
        if f1 < f0: continue
        cam = c[1]; move = c[2] if len(c) > 2 else 'static'
        bts = [b for b in tl if b['f0'] <= f1 and b['f1'] >= f0]
        bid = re.sub(r'^cam_', '', cam); bid = re.sub(r'_(phone|re)$', '', bid)
        src = byid.get(bid) or (byid.get(bts[0]['id']) if bts else None) or {}
        if cam.endswith('_phone'): kind = 'PHONE'
        elif src.get('cam') == 'est': kind = 'EST'
        else: kind = shot_type(src.get('en'))
        content = '；'.join(dict.fromkeys(acts(byid[b['id']]) for b in bts if byid.get(b['id']) and acts(byid[b['id']])))
        talk = []
        for b in bts:
            for fr, lid in b['audio']:
                if f0 <= fr <= f1 and lid in S.TEXT:
                    who, txt = S.TEXT[lid]; talk.append('%s：%s' % (who, txt) if lid not in byid.get(b['id'], {}).get('os', []) else '（画外）%s：%s' % (who, txt))
            for fr, scr, d in b.get('screen', []):
                if f0 <= fr <= f1 and scr in lines.SCREEN:
                    who, txt = lines.SCREEN[scr]; talk.append('【手机屏幕】%s：%s' % (who, txt))
            for s_ in b.get('sfx', []):
                nm = s_[1] if isinstance(s_, (list, tuple)) else s_
                talk.append('〔音效〕' + SFX_CN.get(nm, nm))
        talk = list(dict.fromkeys(talk))
        if kind == 'PHONE': content = '切到手机屏幕：界面内容逐条出现，观众看清文字后切回人物反应' + ('（' + content + '）' if content else '')
        mid = (f0 + f1) // 2
        img = os.path.join(config.RENDERS, sid, 'beauty_%04d.png' % mid)
        th = os.path.join(TMP, '%s_%04d.jpg' % (sid, f0))
        if os.path.exists(img):
            im = cv2.imread(img); cv2.imwrite(th, cv2.resize(im, (480, 270), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])
        else: th = None
        place = PLACE.get(set_name, set_name)
        if scene['id'] == 's07' and set_name != 'track': place += '（回忆）'
        seg_shots.append(dict(seg=sid, scene=scene['id'], place=place, f0=f0, f1=f1, dur=(f1 - f0 + 1) / FPS, kind=kind, move=move,
                              content=content or '（承接上一镜）', talk=talk, thumb=th, t0=t_film + (f0 - 1) / FPS))
    t_film += n_end / FPS
    shots += seg_shots
for i, s_ in enumerate(shots): s_['no'] = i + 1
TOTAL = t_film

def mmss(t): return '%d:%02d' % (int(t) // 60, int(t) % 60)

# ---------------- 文档工具 ----------------
def set_font(doc, name='宋体', size=10.5):
    st = doc.styles['Normal']; st.font.name = name; st.font.size = Pt(size)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), name)
    for lvl, sz in (('Heading 1', 16), ('Heading 2', 13), ('Heading 3', 11.5), ('Title', 24)):
        h = doc.styles[lvl]; h.font.name = '黑体'; h.font.size = Pt(sz); h.font.bold = True; h.font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
        h.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr(); s = OxmlElement('w:shd')
    s.set(qn('w:val'), 'clear'); s.set(qn('w:color'), 'auto'); s.set(qn('w:fill'), hexcolor); tcPr.append(s)

def cell_text(cell, text, bold=False, size=9, align=None, color=None):
    cell.text = ''
    parts = text.split('\n') if isinstance(text, str) else text
    for i, t in enumerate(parts):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(0)
        if align: p.alignment = align
        r = p.add_run(t); r.font.size = Pt(size); r.bold = bold
        if color: r.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def table(doc, headers, widths, header_fill='1F2A44'):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, (h, w) in enumerate(zip(headers, widths)):
        c = t.rows[0].cells[i]; c.width = Cm(w); cell_text(c, h, bold=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color='FFFFFF'); shade(c, header_fill)
    tr = t.rows[0]._tr; trPr = tr.get_or_add_trPr(); th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'true'); trPr.append(th)   # 跨页重复表头
    return t

def add_row(t, vals, widths, sizes=None):
    r = t.add_row()
    for i, (v, w) in enumerate(zip(vals, widths)):
        c = r.cells[i]; c.width = Cm(w)
        if isinstance(v, tuple) and v[0] == 'img':
            c.text = ''; p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if v[1] and os.path.exists(v[1]): p.add_run().add_picture(v[1], width=Cm(w - 0.25))
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        else:
            cell_text(c, v, size=(sizes[i] if sizes else 9), align=WD_ALIGN_PARAGRAPH.CENTER if (sizes and sizes[i] == 'c') else None)
    trPr = r._tr.get_or_add_trPr(); cs = OxmlElement('w:cantSplit'); cs.set(qn('w:val'), 'true'); trPr.append(cs)   # 一行不跨页
    return r

def para(doc, text, size=10.5, bold=False, align=None, indent=True, space=4):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(space)
    if indent: p.paragraph_format.first_line_indent = Pt(size * 2)
    if align: p.alignment = align
    r = p.add_run(text); r.font.size = Pt(size); r.bold = bold
    return p

def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text); r.font.size = Pt(size); return p

def cover(doc, subtitle, extra):
    for _ in range(5): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('思政短剧'); r.font.size = Pt(16); r.font.color.rgb = RGBColor(0x55, 0x5F, 0x75)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('《%s》' % TITLE); r.font.size = Pt(28); r.bold = True; r.font.name = '黑体'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(subtitle); r.font.size = Pt(22); r.bold = True; r.font.name = '黑体'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    for _ in range(4): doc.add_paragraph()
    for line in [TEAM] + extra:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run(line).font.size = Pt(12)
    doc.add_page_break()

def new_doc(landscape):
    doc = Document(); set_font(doc)
    sec = doc.sections[0]
    if landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE; sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    else:
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for m in ('left_margin', 'right_margin'): setattr(sec, m, Cm(2.0))
    sec.top_margin = Cm(1.8); sec.bottom_margin = Cm(1.8)
    fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run('《%s》' % TITLE); r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    return doc

# ---------------- 分镜脚本 ----------------
def storyboard():
    doc = new_doc(True)
    cover(doc, '分镜脚本', ['全片时长约 %s（正片，不含片头片尾）　共 %d 个镜头　%d 场戏' % (mmss(TOTAL), len(shots), len(SCN)), '大连理工大学　2026 年 11 月'])
    doc.add_heading('一、说明', 1)
    para(doc, '本分镜脚本与正片一一对应：每个镜头的画面截图取自已完成的三维白模预演（Blender 白模动画，人物、走位、机位、运镜与正片一致），'
              '正片在白模基础上由 AI 写实化渲染得到真人质感画面，构图与动作不变。表中时长按 24 帧/秒计算，台词时间与配音实际长度一致。')
    para(doc, '导演原则：全片没有旁白和画外叙述；网友评论、来电、动态等以手机屏幕文字呈现；回忆段落用无声画面加环境声；情绪依靠表演与运镜表达。')
    doc.add_heading('景别与运镜说明', 2)
    w = [3.2, 22.5]; t = table(doc, ['术语', '含义'], w)
    for a, b_ in [('大特写 / 特写', '只拍物件（手机、手、桌面）或人物面部，用于强调细节与情绪'),
                  ('近景', '人物胸部以上，用于对话和表情'), ('中景', '人物膝盖或腰部以上，交代人物动作与关系'),
                  ('全景 / 空镜', '交代环境、人物位置与场次转换'), ('手机屏幕特写', '插入镜头，让观众看清朋友圈评论、消息等文字'),
                  ('缓推', '镜头缓慢推近，情绪段落推得更多'), ('弧形移动', '镜头绕人物缓慢移动，用于多人场面，增强空间感'),
                  ('跟拍（摇）', '人物走动、起身时镜头跟随'), ('轻推＋手持感', '近景/特写的轻微推近，带有真人摄影师的呼吸感'), ('固定', '机位不动')]:
        add_row(t, [a, b_], w)
    doc.add_heading('二、分场概览', 1)
    w = [1.6, 5.6, 4.4, 1.8, 1.8, 10.5]; t = table(doc, ['场次', '幕 / 场景', '配乐', '镜头', '时长', '内容提要'], w)
    for sc_ in S.SCENES:
        ss = [s_ for s_ in shots if s_['scene'] == sc_['id']]
        if not ss: continue
        actname = next((c[0].replace('\n', '　') for c in sc_.get('cards', []) if c[2] == 'act'), '')
        places = '、'.join(dict.fromkeys(s_['place'] for s_ in ss))
        trk = [MUSIC_CN.get(tr, tr) for a, b2, tr, _ in music.CUES if a.startswith(sc_['id'])]
        first_acts = [acts(b) for b in sc_['beats'] if acts(b)][:3]
        add_row(t, [sc_['id'].upper(), (actname + '\n' if actname else '') + places, '\n'.join(dict.fromkeys(trk)) or '—', str(len(ss)),
                    mmss(sum(s_['dur'] for s_ in ss)), '；'.join(first_acts)[:150] + '……'], w)
    doc.add_heading('三、分镜表', 1)
    W = [1.2, 5.2, 2.3, 1.6, 8.2, 7.2]
    for sc_ in S.SCENES:
        ss = [s_ for s_ in shots if s_['scene'] == sc_['id']]
        if not ss: continue
        actname = next((c[0].replace('\n', '　') for c in sc_.get('cards', []) if c[2] == 'act'), '')
        doc.add_heading('%s　%s' % (sc_['id'].upper(), actname or '、'.join(dict.fromkeys(s_['place'] for s_ in ss))), 2)
        trk = '、'.join(dict.fromkeys(MUSIC_CN.get(tr, tr) for a, b2, tr, _ in music.CUES if a.startswith(sc_['id'])))
        para(doc, '场景：%s　　镜头 %d 个　　时长 %s　　配乐：%s' % ('、'.join(dict.fromkeys(s_['place'] for s_ in ss)), len(ss), mmss(sum(s_['dur'] for s_ in ss)), trk or '无（静默）'), size=9.5, indent=False)
        t = table(doc, ['镜号', '画面', '景别 / 运镜', '时长', '画面内容', '台词 / 屏幕文字 / 音效'], W)
        for s_ in ss:
            add_row(t, [str(s_['no']), ('img', s_['thumb']), '%s\n%s' % (SHOT_CN[s_['kind']], MOVE_CN.get(s_['move'], s_['move'])),
                        '%.1f 秒\n%s' % (s_['dur'], mmss(s_['t0'])), s_['content'], '\n'.join(s_['talk']) or '—'], W)
    doc.add_heading('四、片头与片尾', 1)
    para(doc, '片头：Claude 娘在大连理工大学雪中雕像前讲解式介绍「本视频由 Claude Opus 5.5 领衔制作」，画面一侧为大连理工大学校徽，另一侧场记板列出片名与团队成员，'
              '并注明代码已在 GitHub（Gnt191612）开源。片尾：演职员字幕，配乐巴赫《C 大调前奏曲》。')
    p = os.path.join(OUT, '分镜脚本_《%s》.docx' % TITLE); doc.save(p); return p

# ---------------- 服道化设计 ----------------
CHAR_NOTE = {
 'lin': dict(role='主角，大学生，热衷在朋友圈经营「精装」形象', color='深灰、深蓝等低饱和色，宽松卫衣——「毛坯」的真实生活状态与内向性格；与他在朋友圈里精心摆拍的明亮画面形成反差',
             hair='黑色碎发短发，清晨刚起床时凌乱；面部素颜，熬夜后略有黑眼圈', makeup='第五幕深夜坦白、茶话会被理解时眼眶与鼻尖微红（情绪妆），其余场次自然素颜'),
 'chen': dict(role='林晓的室友，自律的学霸，外冷内热', color='白衬衫＋黑长裤，黑白极简——沉稳、理性、有条理；浅金色细框圆眼镜强化书卷气',
              hair='黑色中分刘海短发，干净整齐', makeup='自然素颜，肤色干净'),
 'zhou': dict(role='学长（研究生），考研失利后走出低谷的过来人', color='橄榄绿针织毛衣＋工装裤，大地色——温和、踏实、可信赖；针织面料带来温度感',
              hair='黑色偏长蓬松微卷短发、厚刘海', makeup='轻微眼袋，保留经历过压力的痕迹'),
 'wang': dict(role='辅导员，茶话会的组织者', color='浅蓝衬衫＋深蓝领带＋灰色西裤——职业而不刻板，蓝色传递信任与可靠',
              hair='黑色侧分短发', makeup='自然肤色，眼角笑纹，略有小肚子，亲切温暖'),
 'mom': dict(role='林晓的母亲（电话/视频出场）', color='黑色 V 领垂坠长袖上衣＋暖棕色长裤，金色扇形耳环——干练、不显老；暖棕色呼应「家」的温度',
             hair='黑色微卷波浪短发', makeup='淡妆、红唇，金色耳环戴在露出的右耳'),
 'classA': dict(role='同学，食堂起哄者之一，茶话会上说出自己的焦虑', color='深藏青 T 恤＋牛仔裤，休闲运动——爱开玩笑、外向',
                hair='两侧推短的短发', makeup='自然肤色'),
 'classB': dict(role='同学，茶话会上分享自己的心事', color='白色水手领上衣（黑领白边、蓝色领巾）＋黑色百褶短裙＋黑色丝袜＋玛丽珍鞋——文静、略带拘谨的学生气',
                hair='乌黑长发中分，低马尾，黑色发箍', makeup='淡妆，自然唇色'),
}
PROPS = [
 ('手机（每个角色一部）', '全片', '核心道具：朋友圈动态、点赞、评论、来电、自拍。屏幕界面与剧情文字同步出现；林晓的手机贯穿始终，是「精装朋友圈」与「毛坯人生」的连接点'),
 ('枕边手机', 'S01', '清晨在上铺枕边连续亮起，开场第一个大特写'),
 ('牙杯、牙刷、毛巾', 'S01', '林晓赶早八手忙脚乱洗漱'),
 ('英语单词书、笔', 'S01', '陈瑶在书桌前背单词，体现自律'),
 ('外卖盒 ×3', 'S01、S06', '林晓桌上堆着的外卖盒——「毛坯」生活的真实一面'),
 ('电脑显示器、台灯', 'S06、S09', '宿舍书桌陈设；台灯是傍晚与深夜场景的主光源，营造暖色孤独感'),
 ('书本、拿铁咖啡（带拉花）、黑框眼镜', 'S02', '图书馆窗边摆拍道具，林晓为朋友圈精心布置的「精装」画面'),
 ('「闭馆」告示', 'S04', '图书馆门口的告示，揭穿林晓发旧照的谎言'),
 ('餐盘', 'S05', '食堂排队打饭，被同学当众嘲笑的场景'),
 ('水杯（热水）', 'S06', '陈瑶把一杯热水轻轻放到趴在桌上的林晓手边'),
 ('双肩书包', 'S06', '陈瑶从外面回到宿舍'),
 ('活动标题板书、围成一圈的椅子', 'S08', '茶话会活动室布置，围坐象征平等与倾听'),
 ('沙发、茶几、落地灯、绿植', 'S03、S09', '林晓家客厅（林母通话场景），落地灯营造夜晚的温暖'),
]

def autocrop(path, out, pad=24):
    im = cv2.imread(path); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    bg = np.median(np.concatenate([g[:8].ravel(), g[-8:].ravel()]))
    ys, xs = np.where(np.abs(g.astype(int) - int(bg)) > 18)
    if len(xs): im = im[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    cv2.imwrite(out, im, [cv2.IMWRITE_JPEG_QUALITY, 88]); return out

def costume():
    doc = new_doc(False)
    cover(doc, '服装·道具·化妆设计', ['（服道化设计说明书）', '大连理工大学　2026 年 11 月'])
    doc.add_heading('一、总体设计思路', 1)
    para(doc, '本剧讲述大学生林晓在朋友圈里经营「精装」人设、现实生活却一地鸡毛的故事，最终在室友、学长、辅导员和同学的理解下学会坦然面对真实的自己。'
              '服道化设计围绕「精装」与「毛坯」的反差展开：现实中的服装、陈设一律朴素写实，取材当代中国高校日常；朋友圈里的画面（摆拍的拿铁、图书馆、精修照片）则明亮精致。')
    for t_ in ['写实：服装、发型、道具均为当代大学校园里真实可见的样子，不做舞台化夸张。',
               '色彩即性格：每个角色有固定主色，观众凭颜色就能认出人物（林晓深灰、陈瑶黑白、周明远橄榄绿、王老师浅蓝、林母黑与暖棕）。',
               '全片统一：同一角色在所有场次服装、发型不变，便于观众辨认，也保证 AI 写实化渲染时人物前后一致。',
               '光线与情绪：清晨明亮、午后暖、黄昏到深夜逐渐转为台灯的暖色孤光，尾声回到初夏阳光。']:
        bullet(doc, t_)
    doc.add_heading('二、人物造型', 1)
    appear = {}
    for sc_ in S.SCENES:
        for b in sc_['beats']:
            for c in b['chars']: appear.setdefault(S.CID.get(c), []).append(sc_['id'].upper())
    for cid in ['lin', 'chen', 'zhou', 'wang', 'mom', 'classA', 'classB']:
        d = runpy.run_path(os.path.join(ROOT, 'characters', cid, 'character.py'))['CHAR']; n = CHAR_NOTE[cid]
        doc.add_heading('%s（%s）' % (d['cast'][0], n['role']), 2)
        t = doc.add_table(rows=1, cols=3); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
        imgs = [os.path.join(ROOT, 'characters', cid, cid + '.png'), os.path.join(config.ROOT, 'build', 'submission', 'costume_%s_front.png' % cid),
                os.path.join(config.ROOT, 'build', 'submission', 'costume_%s_back.png' % cid)]
        caps = ['定妆照（标准长相）', '三维造型·正面', '三维造型·背面']
        for i, (ip, cap) in enumerate(zip(imgs, caps)):
            c = t.rows[0].cells[i]; c.width = Cm(5.6); c.text = ''
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if os.path.exists(ip):
                src = ip if i == 0 else autocrop(ip, os.path.join(TMP, 'crop_%s_%d.jpg' % (cid, i)))
                if i == 0:
                    im = cv2.imread(ip); h_, w_ = im.shape[:2]; s_ = 900 / max(h_, w_); src = os.path.join(TMP, 'id_%s.jpg' % cid)
                    cv2.imwrite(src, cv2.resize(im, (int(w_ * s_), int(h_ * s_))), [cv2.IMWRITE_JPEG_QUALITY, 88])
                p.add_run().add_picture(src, height=Cm(6.2))
            cp_ = c.add_paragraph(); cp_.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = cp_.add_run(cap); r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        sc_list = '、'.join(dict.fromkeys(appear.get(cid, [])))
        w = [3.0, 14.0]; t2 = table(doc, ['项目', '设计'], w)
        add_row(t2, ['人物', d['look']], w)
        add_row(t2, ['身高', '%.2f 米' % d['height']], w)
        add_row(t2, ['服装与色彩', n['color']], w)
        add_row(t2, ['发型', n['hair']], w)
        add_row(t2, ['化妆', n['makeup']], w)
        add_row(t2, ['出场', sc_list or '—'], w)
        doc.add_paragraph()
    doc.add_heading('三、道具清单', 1)
    w = [4.6, 2.2, 10.2]; t = table(doc, ['道具', '场次', '用途与说明'], w)
    for a, b_, c_ in PROPS: add_row(t, [a, b_, c_], w)
    doc.add_heading('四、场景与陈设', 1)
    para(doc, '场景按真实尺寸搭建（如四人间宿舍 3.4×6.0 米、层高 3.2 米，上床下桌）。下表为各场景的陈设与光线设计，同时作为 AI 写实化渲染时的背景描述。')
    w = [3.4, 2.4, 11.2]; t = table(doc, ['场景', '场次', '陈设与光线'], w)
    used = {}
    for sid, scene, set_name, beats in S.segments(): used.setdefault(set_name, []).append(scene['id'].upper())
    BG_CN = {
     'dorm_am': '四人间：上床下桌、金属爬梯、床栏上搭着衣服，书桌上有书和水杯；清晨阳光透过窗帘',
     'dorm_pm': '同一宿舍的午后：书架、电脑、零食，暖色斜阳', 'dorm_dusk': '同一宿舍的黄昏：只亮一盏暖色台灯，窗外橙色晚霞',
     'dorm_nt': '同一宿舍的深夜：台灯与手机屏幕的微光，窗外深蓝夜色', 'ext_dorm_am': '宿舍楼外：成排窗户与阳台晾晒的衣服，林荫道，楼前停着自行车，清晨',
     'ext_dorm_pm': '宿舍楼外的午后：林荫道、自行车、来往的学生', 'ext_dorm_nt': '宿舍楼外的夜晚：窗户亮着暖黄的灯，路灯，校园安静',
     'ext_library': '现代图书馆正门：宽台阶、玻璃幕墙、树木草坪、背书包的学生', 'lib': '明亮的阅览室：长木桌与台灯、高大的书架、大窗',
     'libdoor': '图书馆门口：玻璃门、台阶与平台、立柱、告示', 'ext_canteen': '午饭时间的食堂外：结伴的学生、树、自行车',
     'canteen': '学生食堂：成排的餐桌与凳子，背景是冒热气的打饭窗口', 'ext_dusk': '黄昏的校园道路：路灯刚亮，树影映着橙紫色的天空',
     'ext_corridor': '教学楼走廊：地砖、教室门、公告栏、窗外日光', 'class': '茶话会活动室：椅子围成一圈，墨绿色黑板，柔和的窗光',
     'track': '夜晚的操场：红色塑胶跑道与白色分道线，绿茵场，看台与树影', 'lawn': '初夏的校园草坪：教学楼与树，蓝天白云，散步的学生',
     'home': '普通家庭客厅：沙发、茶几、电视柜、全家福、绿植，阳台日光', 'home_nt': '夜晚的客厅：暖色落地灯照着沙发与茶几，墙上的全家福'}
    for k, v in used.items():
        add_row(t, [PLACE.get(k, k), '、'.join(dict.fromkeys(v)), BG_CN.get(k, backgrounds.bg(k))], w)
    doc.add_heading('五、化妆与造型统一要求', 1)
    for t_ in ['全片以自然妆为主，男生素颜，林母淡妆红唇；化妆服务于真实感，不做明显修饰。',
               '情绪妆：林晓在茶话会被理解、深夜给妈妈打电话时眼眶与鼻尖微红；周明远保留轻微眼袋。',
               '眼镜、耳环、发箍等配饰固定在同一侧、同一款式，所有场次保持一致（如林母的金色扇形耳环只戴在露出的右耳）。',
               '同一角色全片不换装，保证观众辨认和 AI 写实化渲染时人物前后一致。']:
        bullet(doc, t_)
    p = os.path.join(OUT, '服道化设计_《%s》.docx' % TITLE); doc.save(p); return p

if __name__ == '__main__':
    print('镜头', len(shots), '时长', mmss(TOTAL))
    print(storyboard()); print(costume())
