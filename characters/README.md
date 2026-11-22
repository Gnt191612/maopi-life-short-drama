# 人物库

每个角色一个文件夹，**这个角色的全部东西都在这里**。新增人物、优化人物只改这里，不用碰建模代码；
建模程序（`blender/build_cast.py`）启动时通过 `blender/charlib.py` 自动读取，同名参数以人物库为准。

```
characters/
├── README.md              本说明
├── _template/             新人物模板（复制改名即可）
└── <cid>/                 角色代号（英文、无空格）
    ├── character.py       全部参数（CHAR 字典）
    ├── <cid>.png          标准长相照片（正脸，人挑定的那张）
    ├── <cid>_landmarks_full.json   照片关键点标注
    ├── <cid>_face_fit.json         脸型拟合结果（程序生成，不要手改）
    ├── <cid>_noglasses.png         （可选）戴眼镜角色去掉镜框的照片，贴脸用
    ├── voice.wav          配音参考音色（IndexTTS2 克隆用；怎么设计出来的记在 character.py 的 voice_design）
    └── preview/            效果图（对比图、全身图），方便不开 Blender 就能看
```

现有角色：`lin` 林晓、`chen` 陈瑶、`zhou` 周明远、`wang` 王老师、`mom` 林母、`classA` 同学甲、`classB` 同学乙。

## 新增一个人物

1. 复制 `_template/` 为 `characters/<代号>/`，改 `character.py` 里的身高、性别、服装、发型、外貌描述。
2. 剧本里的中文名 → 代号：仓库根目录 `segments.py` 的 `CID` 加一行。
3. **定长相**：先用模板建个大致白模 → 云端「二转三」出几张写实候选（`cloud/candidates.py`）→ 选一张存为 `<cid>.png`。
4. **标注**照片关键点 `<cid>_landmarks_full.json`（格式和各点含义见 [docs/人物定妆与建模.md](../docs/人物定妆与建模.md)，可参考 `mom/` 的）。
5. **拟合**脸型：
   ```powershell
   .tools\blender\blender.exe -b --factory-startup -P blender\face_fit_export.py -- <cid> build\face_fit\<cid>_head.npz
   python blender\face_fit_solve.py <cid>
   copy build\face_fit\<cid>_fit.json characters\<cid>\<cid>_face_fit.json
   ```
6. **精修**（反复）：`powershell -ExecutionPolicy Bypass -File blender\tests\identity_round.ps1 -Cid <cid> -Tag r1 -Body`
   看 `build\face_fit\` 下的对比图，改 `character.py` 再跑。
7. 满意后把对比图放进 `preview/`，提交（见下）。

## 优化已有人物

改 `characters/<cid>/character.py`（或重标 `<cid>_landmarks_full.json` 后重新拟合）→ 跑一轮 `identity_round.ps1` 看对比图 →
满意后更新 `preview/` 里的图 → 提交。常见问题和对应参数见 [docs/踩坑记录.md](../docs/踩坑记录.md) 第二~四节。

## `character.py` 的键

| 键 | 作用 |
|---|---|
| `cast` | MakeHuman 宏参数：(中文名, 性别0女1男, 年龄, 体重, 肌肉, 身高, 比例, 系统服装, 系统发型, 上衣色, 下装色) |
| `height` | 目标身高（米），建好后整体缩放到这个高度 |
| `skin` `skin_tint` `iris` `eyebrow` | 皮肤、肤色乘数、虹膜、眉形 |
| `face` `face_scale` | 拟合前的五官形态目标、生效比例 |
| `fit_adjust` | 照片拟合后的手动微调（深度方向：胖瘦、双下巴、嘴突、鼻梁…） |
| `fit_smooth` `fit_crown` `fit_shoulder` | 局部磨平褶皱、压低头顶、收肩头 |
| `lip_seal` | 唇缝封口（照片拟合角色都要 True） |
| `lip_tint` | 手调唇色（贴了照片就不要设，会盖掉照片唇色） |
| `body` `cup` `firm` | 身体形态目标（不要动宏「体重」，会让脸型拟合失效）、胸部 |
| `outfit` `shoes` `shoe_tint` `top_fit` `drape` | 服装（MakeHuman 社区服装 + 改色/改贴图）、鞋、上衣合身 |
| `sailor` `vtop` | 从身体表面生成的衣服（水手服、V 领上衣），参数见 `blender/lib/jk_sailor.py` |
| `earring` | 饰品（`blender/lib/accessories.py`） |
| `hair` | 照片发型（`blender/lib/hair_cards.py`：短发 / 马尾 / 长发，发际线、碎发、发流） |
| `hair_shape` `hair_color` `keep_shell` | 用社区发型做轮廓；`keep_shell` = 直接用轮廓、不再长发丝 |
| `look` `look_en` | 写实化提示词（中/英），要和白模造型一致 |
| `voice` `voice_design` | 配音参考音色文件（本文件夹的 `voice.wav`）与它的 Spark-TTS 设计参数（音色丢了可按参数重新生成） |

## 提交更新

```powershell
git checkout -b 人物-<cid>-<改了什么>      # 例：人物-mom-上衣加长
git add characters/<cid>
git commit -m "人物 <cid>：<改了什么>"
git push -u origin 人物-<cid>-<改了什么>
```
然后在 GitHub 上开 Pull Request，附上 `preview/` 的对比图。合并后，正式出片前用
`cloud\prep_trial.ps1 -Cast <cid> -Segs <该角色出场的片段>` 重建到 `assets/cast` 并重拍；定稿资产用 `setup\pack_assets.ps1` 发新 Release。

**一个人物同一时间只让一个人改**（多人同时改同一个人物很容易把身材改废，2026-11-21 发生过）。
