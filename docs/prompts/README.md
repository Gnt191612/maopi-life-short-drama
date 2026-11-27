# 提示词资产库（2026-11-27）

只收**以后任何短剧都能通用**的提示词写法、模板和踩过的坑；本片专属的逐镜头提示词不放这里。

| 文件 | 内容 |
|---|---|
| [通用提示词模板.md](通用提示词模板.md) | 换一部片照样能用的句式：H3 视频提示词骨架、运镜句、说话格式、常见地点环境音、首帧前缀和 kf_hint、人物外貌写法、情绪细节的安全写法 |
| [_official/](_official/) | MiniMax 官方 H3 提示词写作规范原文（base：T2VA/I2VA/FL2VA/L2VA；ref：参考生视频） |

代码版：`cloud/h3_prompt.py`（按模板自动拼每个镜头的 H3 提示词）。本片每个镜头实际用的提示词不入库，开机前运行 `python cloud/export_prompts.py` 导出到 `build/review/prompts/` 逐个审查。

## 一、分工：白模管动作，提示词管「是谁、什么情绪、什么质感」

- **人在哪、怎么动、镜头怎么走** —— 由白模的姿态骨架（0.7）和深度图（0.3）逐帧控制，提示词只要和它一致，不要另编动作。
- **首帧（Krea2 二转三）只读中文前缀**：「画面中的人物是……，不要改变人物的性别、人数和衣着。」+ `kf_hint`。英文画面描述对首帧**不起作用**（踩坑记录 56）。要纠正首帧里的人数、站位、体型，写 kf_hint。
- **视频（H3）读英文提示词**，按官方格式写。

## 二、H3 视频提示词的写法（官方规范 + 本片验证）

1. 首帧模式第一行固定：`For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`，空一行再写三个字段。
2. `integrated_multimodal_description: [Shot 1] Live-action, cinematic, {景别}.` 开头交代风格和构图；接着说「<Picture 1> 里的人保持位置、长相、发型、衣着、体型、房间布局和光线」；再按 **首帧状态 → 动作开始 → 连续发展 → 结果或反应** 写动作。
3. **运镜 = 类型 + 幅度 + 速度**，写成句子里的自然动作：`The camera pushes in with small amplitude at slow speed toward him.`。类型只用官方词表：Push In / Pull Out、Pan、Truck、Tilt、Pedestal、Arc Shot、Tracking Shot、Static Shot、Shake Slightly、POV。
4. **真人感靠具体的正面描述**：呼吸起伏、偶尔眨眼、重心轻微移动、手放松、衣褶和头发随动作自然摆动。
5. **说话**：说话人编号 (S1)(S2)，第一次出场写清年龄、性别、音高、音色、语速；台词放 `<d>[Chinese] 原话</d>`，语气写在标签外；加 `with realistic lip articulation and no exaggerated mouth opening`。一句话一个标签，台词太长会说乱（约 15 秒 20 个词）。**不说话的镜头写明** `Nobody speaks in this shot; lips stay relaxed and closed`。
6. `overall_soundscape` 只写环境音和动作声（1～4 句），`non_diegetic_music: N/A`（配乐本地加）。
7. **不写负面提示词**：H3 用 BasicGuider、cfg 1，没有负面分支，写「no extra people」不起作用，要正面写「画面里只有这两个人」。
8. 画面里要出现的中文字，原样放在英文双引号里。

## 三、踩过的提示词坑（每条都返工过）

| 写法 | 结果 | 改成 |
|---|---|---|
| eyes red and swollen / eyes slowly turning red | 眼睛发红光 | eyes slightly puffy from crying, natural eyes |
| face clearly visible（白模里只露头顶） | 凭空补出第二张脸 | 照白模写：at first only the top of his hair is visible, he slowly lifts his head |
| 体型写 round belly / 肚子圆 | 露出整块肚皮 | broad heavy stocky build, fully clothed（只写整体轮廓，不点名身体部位） |
| 只写「微胖」且多人镜头不换脸 | 胖角色被画成普通身材 | noticeably overweight, chubby ... broad heavy build |
| 一拍的描述给两个机位共用（「两个人、胖的在右」） | 单人镜头补出第二张脸、左右画反 | 按镜头写（shot_prompts.py）：几个人、谁在左谁在右、谁戴眼镜 |
| 剧本写周明远 buzz cut，人物库是卷发 | 同一角色发型来回变 | 提示词外貌和人物库逐字一致 |
| 白模里只露半截肩膀 | 画成白色圆球 | 在控制图/首帧上把它抹掉，提示词写 the left foreground is the empty table edge |
| 近景看不到帽子，只写 hoodie | 画成黑西装外套 + 白 T 恤 | dark grey open zip hoodie with the hood resting behind his neck over a dark grey T-shirt |
| slow orbiting camera move（旧运镜写法） | 运镜幅度、速度没法控制 | 官方三要素写法（场景与运镜.md） |
| 关键帧改人用双参考编辑「把图1的人改成图2」 | 往画面里加一个人 | kf_hint 重做首帧 + 本地 face_unify 换脸 |
| 多人镜头关键帧逐个 Qwen 换脸 | 连衣服一起换、换错人 | 多人镜头不在关键帧换脸 |

## 四、下一部片怎么复用

1. 复制 `story/story_scenes.py` 的格式写剧情：每拍 `en`（英文画面）+ `act`（中文动作）+ 台词。
2. 人物外貌写进人物库，**中英文都写体型的整体轮廓、发型、完整衣着**（帽子、内搭、外套）。
3. 场景写进 `cloud/backgrounds.py`，环境音写进 `h3_prompt.SOUND`。
4. 打包后先运行 `python cloud/export_prompts.py`，通读 `build/review/prompts/全片提示词.md`：人数、左右、衣着、和白模是否一致，问题镜头写进 `shot_prompts.py`。
5. 开机先试 3 个镜头再全片（见 [../模型选型.md](../模型选型.md)）。
