# 提示词资产库（2026-11-27）

这部短剧用到的全部提示词，以及「怎么写才能让 AI 视频动作自然、运镜可控、人物不走样」的规则。下一部片照着改就能用。

| 文件 | 内容 |
|---|---|
| [全片提示词.md](全片提示词.md) / [prompts.json](prompts.json) | 129 个镜头逐个：剧情动作（中文）、画面描述（英文）、首帧中文前缀、H3 视频提示词（官方格式）、台词 |
| [角色与声音.md](角色与声音.md) | 7 个角色的中英文外貌描述、声音特征 |
| [场景与运镜.md](场景与运镜.md) | 每个场景的背景描述、环境音；白模运镜类型 → H3 官方运镜词 |
| [风格与通用句.md](风格与通用句.md) | 真人动作、质感、对齐句、说话格式、首帧前缀模板、换脸指令 |
| [_official/](_official/) | MiniMax 官方 H3 提示词写作规范原文（base：T2VA/I2VA/FL2VA/L2VA；ref：参考生视频） |

生成方式：全部由代码拼出来，源头在 `story/story_scenes.py`（剧情动作、节拍画面）、`cloud/shot_prompts.py`（按镜头改写、kf_hint）、人物库 `characters/`（外貌）、`cloud/backgrounds.py`（场景）、`cloud/h3_prompt.py`（H3 格式、运镜、环境音、声音）。改完源头运行 `python cloud/export_prompts.py` 重新导出。

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
4. 打包后先运行 `python cloud/export_prompts.py`，通读 `全片提示词.md`：人数、左右、衣着、和白模是否一致，问题镜头写进 `shot_prompts.py`。
5. 开机先试 3 个镜头再全片（见 [../模型选型.md](../模型选型.md)）。
