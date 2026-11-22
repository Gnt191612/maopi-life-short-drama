# 毛坯人生，精装朋友圈 —— AI 辅助写实短剧（白模 + AI 写实化管线）

大连理工大学思政课程短剧作品（约 9–10 分钟）。本仓库包含**从剧本到成片的完整工具链、全部固定资产和踩过的坑**：
一台什么都没装的电脑按本文步骤即可重新做出整部影片，也可以拿它做新的短剧（见 [docs/制作新短剧指南.md](docs/制作新短剧指南.md)）。

> 讲述大学生林晓在朋友圈里经营「精装人设」、翻车、在室友与学长的帮助下学会接纳「毛坯人生」的故事。

**制作小组**：队长 郭宁桐；队员 梁钧咏、王启元、刘洋、蔡磊、仝启瀚、刘译阳　　**AI 协作**：Claude Opus 5.5（Anthropic）

## 管线总览

```
剧本（story/）──► 分场拍摄表（逐拍动作、台词、机位描述）──► 走位表
      │
标准长相照片（每个角色 AI 出候选，人挑一张：characters/<cid>/<cid>.png）
      │ 关键点标注 → 脸型拟合 → 照片贴脸 → 照着照片做发型 → 身体与服装
      ▼
角色白模（MakeHuman/MPFB，blender/build_cast.py）  场景白模（blender/build_sets.py）
配音（Spark-TTS 设计音色 + IndexTTS2 情绪配音）  口型（Rhubarb）  动作（姿态库 + CMU 动捕）
      │
      ▼  Blender 自动拍摄引擎（机位、180° 轴线、遮挡规避、景深）── run_all.py
白模画面 + 深度图 + 骨架图（每个片段）
      │  cloud/pack_for_cloud.py：按镜头切任务 + 高清首帧
      ▼  云端（仙宫云 ComfyUI 镜像）
每个镜头：首帧白模 → Krea2「二转三」写实关键帧 → Qwen 只换脸（锁定标准长相）→ Wan2.2 图生视频
      │
      ▼  本地 cloud/make_final.ps1
片头（Claude 娘讲解 + 场记板）＋ 写实正片（配音、字幕、配乐）──► 成片
```

人物的长相、位置、动作、道具、口型都由白模锁定，AI 只负责最后的「写实化」，所以不会出现角色漂移和道具变形。

## 一、从零安装（只需一次）

需要：Windows 10/11 或 Linux，NVIDIA 显卡（本地 8GB 即可；写实化在云端跑），约 60GB 硬盘，能访问 GitHub。

```powershell
git clone https://github.com/Gnt191612/maopi-life-short-drama.git
cd maopi-life-short-drama
powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1          # Linux：bash setup/setup_linux.sh
powershell -ExecutionPolicy Bypass -File setup\get_mh_community.ps1       # MakeHuman 社区服装包 + 发型包（重建人物时需要）
```
- `setup_windows.ps1` 先下载固定资产包（GitHub Release，地址在 `setup/assets_release.txt`：定稿角色、场景、配音、配乐），
  再把外部工具装进仓库内的 `.tools/`（不改系统）：Blender 4.5.16 LTS、MPFB 2.0.18、MakeHuman CC0 素材、Rhubarb、ffmpeg、
  Noto Sans SC 字体、CMU 动捕片段，并 `pip install -r setup/requirements.txt`。
- 可选：`-WithTTS`（配音模型，改台词/重新配音时才需要，约 10GB；Windows 另见 `setup/setup_tts_windows.ps1`）。
- 网络受限先设代理：`$env:HTTPS_PROXY="http://127.0.0.1:7890"`。

## 二、白模预演（本地，免费）

```powershell
$env:V11_PREVIEW='1'; python run_all.py          # 实时引擎预览画质，全片约 2~3 小时；输出 build/previs_preview/
python run_all.py                                 # 正式画质（Cycles）
$env:V11_ONLY='s03_00,s03_01'; python run_all.py  # 只拍指定片段
```
自动完成：口型 → 逐片段搭景、动画、机位 → 渲染白模画面与深度图 → 每场及全片预演（配音、字幕、配乐）。中断后重跑会跳过已完成部分。
**导演原则：全片没有旁白**——网友评论、来电、朋友圈都显示在手机屏幕上（`story/lines.py` 的 `SCREEN`）。

## 三、人物（已定稿；改人物或做新角色时看这里）

人物全部集中在**人物库 `characters/`**（同事新增/优化人物看 [characters/README.md](characters/README.md)）。详细流程：[docs/人物定妆与建模.md](docs/人物定妆与建模.md)。一轮精修：
```powershell
powershell -ExecutionPolicy Bypass -File blender\tests\identity_round.ps1 -Cid mom -Tag r1 [-Body] [-Back]
```
建模 → 贴标准长相照片 → 出「照片 / 带皮肤 / 素模」对比图（`build/face_fit/`）。人物定稿后：
```powershell
powershell -ExecutionPolicy Bypass -File cloud\prep_trial.ps1 -Segs <要拍的片段>   # 重建到 assets/cast + 重拍 + 打包
```

## 四、云端写实化与成片

详细说明：[cloud/写实化会话流程.md](cloud/写实化会话流程.md)。平台：仙宫云，社区镜像「Moss/Krea2 超写实人像 + Wan2.2/MiniMaxH3 图生视频」+ RTX 4090D（约 ¥1.89/时）。
```powershell
# 1) 本地（免费）：重拍全片 + 高清首帧 + 打包 dist/cloud_pack.zip
powershell -ExecutionPolicy Bypass -File cloud\prep_trial.ps1 -SkipCast -Segs <全部片段>
# 2) 控制台开机，SSH 地址在控制台「SSH」里看；本机密钥 ~/.ssh/xiangongyun_ed25519（公钥登记到平台）
powershell -ExecutionPolicy Bypass -File cloud\session.ps1 -SshHost root@<主机> -Port <端口> -Stage probe     # 新镜像先探查节点
powershell -ExecutionPolicy Bypass -File cloud\session.ps1 -SshHost root@<主机> -Port <端口> -Stage final -MaxHours 8
# 3) 关机 → 本地合成成片
powershell -ExecutionPolicy Bypass -File cloud\make_final.ps1 -Result build\cloud_out\final_<时间>
```
成片：`build/final/毛坯人生，精装朋友圈_成片.mp4`。**云端按时计费：一个阶段跑完、下一步不是马上要跑就关机。**

## 五、片头

`blender/intro_compose.py`：背景为大连理工大学官网「校园风光」雪中雕像照（本地修补去掉行人）+ 官网校徽；
Claude 娘绿幕讲解视频抠像叠加；场记板写片名、队长、队员与开源地址。
**Claude 娘的形象和音色单独成库：[mascot/claude_girl/](mascot/claude_girl/README.md)**（立绘、绿幕视频、音色参考音、`say.py` 用她的声音念任意台词），以后的作品可以直接引用。

## 目录结构

| 目录 | 内容 | 入库 |
|---|---|---|
| `story/` | 剧本、分场拍摄表、台词表、走位表、配乐表 | 是 |
| `blender/` | 角色/场景搭建、拍摄引擎、脸型拟合、照片贴脸、片头合成 | 是 |
| `blender/lib/` | 姿态库、机位、发型（`hair_cards.py`）、程序服装（`jk_sailor.py`）、饰品等 | 是 |
| `blender/tests/` | 对比图、全身检查、精修一轮脚本 `identity_round.ps1` | 是 |
| `characters/` | **人物库**：每个角色一个文件夹（全部参数 `character.py`、标准长相照片、关键点、拟合结果、音色 `voice.wav`、效果图）；新增/优化人物只改这里，见 [characters/README.md](characters/README.md) | 是 |
| `mascot/claude_girl/` | **Claude 娘素材库**：形象、绿幕视频、音色、念台词工具 | 是 |
| `assets/intro/` | 片头背景（大工雪景照、校徽） | 是 |
| `assets/cast/` `sets/` `audio/` `music/` | 定稿角色、场景、配音、配乐 | Release 附件 |
| `voice_tools/` | 音色设计、挑选、配音脚本与各角色选定的参考音 | 是 |
| `cloud/` | 云端写实化套件（打包、会话、关键帧、视频、成片） | 是 |
| `setup/` | 一键安装、资产打包、依赖清单 | 是 |
| `docs/` | 人物流程、[踩坑记录](docs/踩坑记录.md)、新短剧指南 | 是 |
| `build/` `.tools/` `dist/` | 运行产物、外部工具、打包输出 | 否（可重新生成/下载） |

## 可复现性

- 定稿资产作为 Release 附件发布（`setup/pack_assets.ps1` 生成），安装脚本自动下载，结果与原作一致。
- 生成它们的脚本全部入库，随机过程使用固定种子；同版本工具下重新生成结果相同。
- 遇到问题先查 [docs/踩坑记录.md](docs/踩坑记录.md)。

## 许可证

- 代码：MIT（[LICENSE](LICENSE)）
- 原创资产（角色、场景、配音、剧本）：CC BY-NC-SA 4.0（配音音色由 CC BY-NC-SA 授权的 Spark-TTS 设计）
- 大连理工大学校徽与校园照片版权归大连理工大学所有，仅用于本课程作品；第三方组件见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)
