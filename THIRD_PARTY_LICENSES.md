# 第三方组件与许可证

本仓库**不直接包含**以下软件本体，它们由 `setup/` 下的安装脚本从官方来源下载；使用时请遵守各自的许可证。

| 组件 | 用途 | 许可证 | 来源 |
|---|---|---|---|
| Blender 4.5.16 LTS | 白模搭建、动画、渲染 | GPL-2.0-or-later | https://www.blender.org |
| MPFB 2.0.18 | MakeHuman 角色生成插件 | GPL-3.0 | https://extensions.blender.org/add-ons/mpfb/ |
| MakeHuman 系统素材 | 皮肤、发型、服装、眼睛等 | CC0 1.0 | http://www.makehumancommunity.org |
| CMU Graphics Lab 动作捕捉数据库 | 走路、坐下、爬梯等动作 | 可自由使用（含商业作品），不得直接转售数据；请署名 | http://mocap.cs.cmu.edu |
| cmu-mocap（BVH 转换版） | CMU 数据的 BVH 格式 | 同 CMU 数据 | https://github.com/una-dinosauria/cmu-mocap |
| Rhubarb Lip Sync 1.14.0 | 配音 → 口型序列 | MIT | https://github.com/DanielSWolf/rhubarb-lip-sync |
| FFmpeg | 视频/音频处理 | LGPL/GPL（视构建而定） | https://ffmpeg.org |
| Noto Sans SC | 字幕与字卡字体 | SIL Open Font License 1.1 | https://fonts.google.com/noto/specimen/Noto+Sans+SC |
| Spark-TTS（代码） | 音色设计 | Apache-2.0 | https://github.com/SparkAudio/Spark-TTS |
| Spark-TTS-0.5B（模型权重） | 音色设计 | **CC BY-NC-SA 4.0（仅限非商业用途）** | https://huggingface.co/SparkAudio/Spark-TTS-0.5B |
| IndexTTS2（代码与模型权重） | 台词配音（音色克隆 + 逐句情绪控制） | bilibili Model Use License Agreement（全文见 `licenses/`） | https://github.com/index-tts/index-tts |
| MakeHuman 社区发型包 hair02 / hair03 | 发型轮廓参考（林母） | CC-BY（作者署名见包内说明） | http://www.makehumancommunity.org |
| Whisper | 配音字错率自动校验 | MIT | https://github.com/openai/whisper |
| Remotion | 最终合成 | Remotion License（个人及 3 人以下团队免费，其他需购买公司许可） | https://www.remotion.dev/license |
| three.js | 网页预演查看器 | MIT | https://threejs.org |

## 关于配音资产的特别说明

`assets/audio/` 中的全部台词配音由 **IndexTTS2** 生成（音色参考由 Spark-TTS 设计，不克隆任何真人；情绪按台词表的语气说明逐句控制）。
按 bilibili Model Use License Agreement 的要求特此声明：

> Any modifications made to the original model in this Derivative Work are not endorsed, warranted, or guaranteed by the original right-holder of the original model, and the original right-holder disclaims all liability related to this Derivative Work.
> （本衍生作品对原模型所做的任何修改均未获得原权利人的认可、保证或担保，原权利人不承担与本衍生作品有关的任何责任。）

协议全文随仓库（`licenses/bilibili_IndexTTS2_LICENSE*.txt`）和配音资产包（`assets/audio/bilibili_IndexTTS2_LICENSE.txt`）一并分发；
使用、再分发本仓库配音的人同样须遵守该协议。
由于 Spark-TTS 模型权重采用 CC BY-NC-SA 4.0 许可，本仓库的配音及参考音色同样以 **CC BY-NC-SA 4.0** 发布，**仅限非商业用途**。
如需商业使用，请换用商业许可的配音方案重新配音（`voice_tools/` 提供了完整流程）。

## 角色资产说明

`assets/cast/` 中的角色由 MPFB（GPL-3.0 插件）调用 MakeHuman CC0 素材生成。生成的 .blend 资产本身（网格、贴图引用、骨骼）
基于 CC0 素材，按本仓库资产许可（CC BY-NC-SA 4.0）发布；MPFB 插件本身不随仓库分发。
