# 毛坯人生，精装朋友圈 —— AI 辅助写实短剧（白模 + 渲染管线）

大连理工大学思政课程短剧作品（约 9–10 分钟）。本仓库包含**从剧本到成片的完整工具链和全部固定资产**，
在任何一台空白电脑上按下面的步骤即可重新下载并做出整部影片。

> 讲述大学生林晓在朋友圈里经营「精装人设」、翻车、在室友与学长的帮助下学会接纳「毛坯人生」的故事。

## 为什么是「白模 + 渲染」

早期版本用 AI 视频模型逐镜头生成，存在角色认不出、道具变形、动作衔接断裂、口型不对等根本问题。
本版改为影视工业的预演流程：

```
剧本 ──► 分场拍摄表（逐拍动作、台词时间）──► 走位表
                                        │
角色白模（MakeHuman/MPFB，写实皮肤+真实发丝）─┤
场景白模（按真实尺寸程序化搭建）──────────────┤──► Blender 自动拍摄引擎 ──► 白模画面 / 深度图 / 每段 .blend
动作捕捉（CMU）＋ 姿态库 ───────────────────┤      （机位、180° 轴线、遮挡规避、景深、口型）
配音（Spark-TTS 设计音色 + IndexTTS2 情绪配音）──┤
口型（Rhubarb，按配音驱动面部骨骼）───────────┘
                                                         │
                                       云端 AI 写实化渲染（以深度/骨骼图层为约束）
                                                         │
                                         Remotion 合成（字卡、手机界面、字幕、混音）──► 成片
```

人物位置、动作、道具形状、口型都由 3D 白模锁定，AI 只负责最后的「写实化」，因此不会再出现角色漂移和道具变形。

## 快速开始

### 1. 安装（只需一次）
Windows（PowerShell，在仓库根目录）：
```powershell
powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1
```
Linux / 云服务器：
```bash
bash setup/setup_linux.sh
```
安装脚本会先下载固定资产包（GitHub Release 附件，地址见 `setup/assets_release.txt`），再把所有外部工具下载到仓库内的 `.tools/` 目录（不改动系统）：Blender 4.5.16 LTS、MPFB 2.0.18、MakeHuman CC0 素材、
Rhubarb、ffmpeg、Noto Sans SC 字体、CMU 动作捕捉片段，并安装 Python 依赖（numpy、pillow）。
网络受限时先设置代理：`$env:HTTPS_PROXY="http://127.0.0.1:7890"`（Linux：`export HTTPS_PROXY=...`）。

可选参数：`-WithTTS` / `--with-tts`（安装配音模型，仅在需要改台词、重新配音时用，约 10 GB）；
`-WithRemotion` / `--with-remotion`（安装最终合成用的 Remotion，需要 Node.js 18+）。

### 2. 生成全片白模预演
```bash
python run_all.py
```
自动完成：口型序列 → 逐片段搭建与动画 → Cycles 写实渲染 → 每场及全片预演视频（带配音和字幕）。
输出在 `build/`（可随时删除后重新生成）。中断后重新运行会自动跳过已完成的部分。

只想快速看剧情（走位、镜头、节奏、台词）时，用实时引擎出低分辨率预览（RTX 4060 约 2 小时出全片）：
```bash
V11_PREVIEW=1 python run_all.py          # Windows PowerShell：$env:V11_PREVIEW='1'; python run_all.py
```
输出在 `build/previs_preview/`，与正式渲染互不覆盖。手机屏幕上的文字（评论、来电、动态）在预览里以画面上方黄字示意。

> **导演原则：全片没有旁白。** 能用人物的台词、动作、表情和场景表现的，一律不用画外音：网友评论、来电、朋友圈动态
> 都显示在手机屏幕上（`story/lines.py` 的 `SCREEN`），回忆段落是无声画面加环境声。

### 3. 云端写实化与成片
见 `docs/cloud_render.md`（云服务器确定后补充）。

## 目录结构

| 目录 | 内容 | 是否入库 |
|---|---|---|
| `story/` | 分场拍摄表、台词表、走位表 | 是 |
| `blender/` | Blender 端脚本：角色/场景搭建、拍摄引擎、姿态库、口型、发丝、动作重定向 | 是 |
| `assets/cast/` | 7 个角色白模（.blend，固定资产） | Release 附件（安装脚本自动下载） |
| `assets/sets/` | 19 个场景白模（.blend，固定资产） | Release 附件（安装脚本自动下载） |
| `assets/audio/` | 73 句台词配音（.wav）与时长表 | Release 附件（安装脚本自动下载） |
| `voice_tools/` | 音色设计、自动挑选、重新配音的脚本与各角色选定的参考音色 | 是 |
| `remotion/` | 最终合成工程 | 是（不含 node_modules） |
| `setup/` | 一键安装脚本、依赖清单 | 是 |
| `build/` | 运行产物（口型、动画 .blend、渲染帧、预演视频） | 否，可重新生成 |
| `.tools/` | 外部工具（安装脚本下载） | 否 |

## 固定资产与可复现性

- 角色、场景、配音已经定稿，作为固定资产打包发布在 GitHub Release（`setup/pack_assets.ps1` 生成），安装脚本自动下载，结果与原作完全一致。
- 同时保留了生成它们的脚本（`blender/build_cast.py`、`blender/build_sets.py`、`voice_tools/`），所有随机过程都使用固定种子，
  在同一版本工具下重新生成会得到相同的结果。
- 重新生成角色：`.tools/blender/blender -b --factory-startup -P blender/build_cast.py`（需先完成安装）。

## 演职员与工具

- 编剧/制作：大连理工大学思政课程小组
- AI 协作：Claude（Anthropic）
- 工具与素材：见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

## 许可证

- 代码：MIT（见 [LICENSE](LICENSE)）
- 本仓库原创的资产（角色、场景、配音、剧本）：CC BY-NC-SA 4.0（因为配音音色由 CC BY-NC-SA 授权的 Spark-TTS 设计，为统一起见全部资产采用此协议）
- 第三方组件各自遵循其许可证，详见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)
