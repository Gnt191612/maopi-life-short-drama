# -*- coding: utf-8 -*-
"""锁定角色长相（在仙宫云 Krea2 镜像实例上运行）：
1) 标准正脸：白模正脸 →「二转三」写实化（加人物外貌描述）→ canon_<cid>.png，作为这个角色的长相标准；
2) 其他机位：「双参考编辑」——图1 = 白模该机位（管姿势、构图、服装），图2 = 标准正脸（管长相）→ real_<cid>_<view>.png。
输入图需已放在 /root/ComfyUI/input/<cid>_<view>.png。用法：python3 identity_run.py [角色id ...]"""
import sys, shutil
sys.path.insert(0, '/root')
import comfy_run
LOOK = {   # 外貌描述（与剧本人物设定、当前白模服装一致）
 'lin':    '一位20岁微胖的中国男大学生，圆脸，小眼睛，略有双下巴，黑色碎盖短发，穿深灰色连帽卫衣，憨厚腼腆，',
 'chen':   '一位21岁高瘦的中国男大学生，鹅蛋脸，颧骨分明，戴细圆框金属眼镜，黑色偏分短发，穿白衬衫，沉稳安静，',
 'zhou':   '一位22岁清瘦的中国男研究生，长方脸，高颧骨，轻微眼袋，黑色短寸头，穿橄榄绿针织毛衣，温和踏实，',
 'wang':   '一位38岁的中国男辅导员，方脸，有笑纹，黑色侧分短发，穿浅蓝色衬衫系领带，真诚温暖，',
 'mom':    '一位50岁的中国母亲，圆润和善的脸，有笑纹，乌黑长发及胸，穿米色毛衣，慈爱，',
 'classA': '一位20岁健壮的中国男大学生，菱形脸，下巴突出，小麦色皮肤，黑色上翘短发，穿深蓝色T恤，笑嘻嘻，',
 'classB': '一位20岁苗条的中国女大学生，鹅蛋脸，浓眉大眼，黑色眼睛，乌黑浓密的长发全部向后梳成马尾、没有刘海，穿米色针织毛衣和格纹短裙、黑色丝袜，文静害羞，',
}
EDIT = ('将图1转为真实照片。构图、景别、人物在画面中的位置和大小与图1完全相同：图1是全身就生成从头到脚完整入镜的全身照，是半身就生成半身照，不要裁切、不要放大。'
        '保持图1的姿势、服装、镜头角度和光线。人物的脸换成图2中这个人：同一个人，五官、脸型、眉眼、肤色、发型与图2完全一致。'
        '人物：{look}自然真实的皮肤质感，没有虚化模糊的区域，画面不存在任何文字和水印。')
SEED = 20261119

def main():
  for cid in (sys.argv[1:] or list(LOOK)):
    import os
    canon = '/root/v11_out/canon_%s.png' % cid
    if not os.path.exists(canon):
        canon = comfy_run.run('Krea2-二转三-图生图-新版.json', 'canon_' + cid, {'10.image': cid + '_face_front.png'}, prefix=LOOK[cid])
    if not canon: continue
    shutil.copy(canon, '/root/ComfyUI/input/canon_%s.png' % cid)
    for view in ('face_34', 'half', 'full'):
        comfy_run.run('Krea2-双参考编辑-图生图.json', 'real_%s_%s' % (cid, view),
                      {'66.image': '%s_%s.png' % (cid, view), '52.image': 'canon_%s.png' % cid, '34.prompt': EDIT.format(look=LOOK[cid]), '7.seed': SEED},
                      enable=(48, 50, 52))   # 打开作者默认关掉的「第二参考」分组
  print('IDENTITY DONE', flush=True)

if __name__ == '__main__':   # 被 identity_swap.py 导入（只取 LOOK）时不执行
    main()
