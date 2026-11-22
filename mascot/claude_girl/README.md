# Claude 娘（形象 + 音色素材库）

知书达理、温柔体贴的讲解员形象。独立于本片，**以后任何作品都可以直接拿她的形象和声音来创作**。
完整设定（外貌描述、画风规则、音色参数）在 [profile.json](profile.json)。

```
mascot/claude_girl/
├── profile.json                 设定：外貌描述（中/英）、画风规则、音色设计与配音参数
├── image/
│   ├── claude_girl.png          全身立绘（透明背景，834×1411）
│   ├── green_first_portrait.png 绿幕首帧（竖屏 720×1280，生成视频用）
│   └── green_first_landscape.png 绿幕首帧（横屏 1920×1080）
├── video/
│   └── talk_greenscreen_832x480.mp4   绿幕讲解动作（5 秒：微笑讲解 → 手掌示意画面左侧；扇子合着）
├── voice/
│   ├── voice_ref.wav            音色参考音（克隆用）
│   └── sample_本视频由ClaudeOpus5.5领衔制作.wav   示例台词（本片片头）
└── tools/
    ├── say.py                   用她的声音念任意台词
    ├── green_first.py           立绘 → 绿幕首帧
    └── design_voice.py          重新设计音色（Spark-TTS，选定的是 seed 2812）
```

## 让她说话

```powershell
<IndexTTS2 环境的 python> mascot\claude_girl\tools\say.py "大家好，我是 Claude，今天带大家看一个小故事。" out.wav
```
默认温柔微笑的情绪、0.88 倍语速（制作小组 2026-11-22 选定）。数字写成汉字读得更准（「五点五」）。
IndexTTS2 安装：`setup\setup_tts_windows.ps1`（或 `setup_windows.ps1 -WithTTS`）。

## 让她动起来

1. 绿幕首帧：`python mascot\claude_girl\tools\green_first.py first.png --size 720x1280`
2. 云端图生视频（仙宫云 Wan2.2 镜像）：`cloud/intro_video.py`（`INTRO_STYLE=talk` 讲解动作，`INTRO_W=720 INTRO_H=1280` 竖屏）。
   提示词要点见 `profile.json` 的 `look_en` 与 `style_rules`：保持 2D 动漫画风、扇子合着、静止机位、动作优雅。
3. 抠像合成：参考 `blender/intro_compose.py`（`key_green` 绿幕抠像、落地阴影、叠加到背景）。
   注意：工作流输出的 GIF 帧率是错的，要按「总帧数 ÷ 5 秒」重算时间轴（见 docs/踩坑记录.md 第六节）。

## 使用须知

- 立绘由制作小组提供；音色由 Spark-TTS 全新设计，不克隆任何真人。
- 音色设计模型 Spark-TTS 为 CC BY-NC-SA 授权，因此音色与配音素材**仅限非商业使用**（与本仓库资产许可一致）。
