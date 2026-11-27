> **已过时（2026-11-19 的 Wan2.1-VACE 方案）。现行流程见 [cloud/写实化会话流程.md](../cloud/写实化会话流程.md)。**

# 云端 AI 写实化：输入素材说明

白模管线负责「对」（走位、动作、机位、道具、谁是谁），云端视频模型负责「真」（照片级质感）。
下面是交给云端的全部素材，都由本仓库自动生成，可随时重新生成。

## 每个片段（`build/renders/<片段>/`，正式渲染用 Cycles，`V11_PREVIEW` 不要设）

| 文件 | 内容 | 用途 |
|---|---|---|
| `beauty_####.png` | 白模画面（写实材质、HDRI 光照） | 视频到视频的底图 / 首帧 |
| `depth_####.png` | 深度图，16 位灰度，**固定 0.1~40 米映射**（近白远黑），全片同一标尺、不闪 | ControlNet Depth / VACE 深度控制 |
| `pose_####.png` / `pose_####.json` | OpenPose BODY-18 骨架图与关键点（`person_id` = 固定角色编号） | 姿态控制，防止动作走形 |
| `mask_####.png` | 物体编号遮罩（灰度 = 编号/20） | 分人物、分背景处理 |
| `ctrl_####.exr` | 多层 EXR：真实深度（米）、世界空间法线、物体编号、Cryptomatte | 需要更精细控制时用 |

骨架图：`blender -b --factory-startup -P blender/export_pose.py -- <片段> [--step 1] [--size 960x540]`

## 角色编号（全片固定，`build/shots/<片段>_ids.json` 里有每段的对照）

1 林晓 · 2 陈瑶 · 3 周明远 · 4 王老师 · 5 林母 · 6 同学甲 · 7 同学乙 · 10 起 路人 · 15 手机

## 角色长相参考（`assets/lookdev/`）

每个角色 5 张照片级定妆照：`face_front` / `face_34` / `face_side` / `half` / `full`。
由 `blender/lookdev_renders.py`（白模底图 + 深度）→ `lookdev/portraits.py`（RealVisXL + ControlNet Depth + IP-Adapter Face）生成，
在云端用作参考图（IP-Adapter / 角色 LoRA 训练素材），保证全片 9 分钟里同一个人始终是同一张脸。

## 建议的云端流程（服务器确定后细化）

1. 先挑 5~10 秒的镜头做小样，确认质感与长相一致性。
2. 逐镜头：底图 + 深度 + 骨架作控制，定妆照作长相参考，写实化生成。
3. 手机屏幕上的文字、片头片尾字卡由 Remotion 后期合成（预演里的黄字只是示意）。
