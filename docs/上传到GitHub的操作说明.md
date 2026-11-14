# 任务：把《毛坯人生，精装朋友圈》白模管线开源到 GitHub

你好！请帮我把本地工程上传为一个公开的 GitHub 仓库。工程已经整理好了，你只需要按下面的步骤操作，不要修改任何代码或文档内容。

## 基本信息
- 本地工程目录：`D:\v11`（以下所有命令都在这个目录下执行）
- 仓库名建议：`maopi-life-short-drama`（如我另有指定以我为准）
- 仓库描述：`《毛坯人生，精装朋友圈》思政短剧：Blender 白模 + 云端 AI 写实化的完整开源管线（大连理工大学）`
- 仓库可见性：Public（公开）
- 话题标签（topics）：`blender`, `short-drama`, `previs`, `makehuman`, `lip-sync`, `ai-filmmaking`, `remotion`

## 第 1 步：打包固定资产（大文件不进 Git，作为 Release 附件发布）
```powershell
cd D:\v11
powershell -ExecutionPolicy Bypass -File setup\pack_assets.ps1 -Version v1.0
```
会生成 `dist\assets_v1.0.zip`（约 300 MB，包含角色、场景、配音）和 `dist\assets_v1.0.sha256`。

## 第 2 步：初始化 Git 并检查要上传的内容
```powershell
cd D:\v11
git init -b main
git add .
git status
```
**请核对 `git status` 的结果**，应当只包含下面这些（`.gitignore` 已经配置好排除规则）：

| 应该上传 | 说明 |
|---|---|
| `README.md`、`LICENSE`、`THIRD_PARTY_LICENSES.md`、`.gitignore`、`.gitattributes` | 说明与许可证 |
| `config.py`、`run_all.py`、`segments.py` | 主控代码 |
| `story/` | 剧本结构、台词、走位表 |
| `blender/`（含 `lib/`、`tests/`） | Blender 端脚本 |
| `voice_tools/`（含 `voices_v2/` 选定音色） | 配音工具 |
| `setup/` | 一键安装脚本、依赖清单、资产包地址 |
| `remotion/`（**不含** `node_modules/`） | 合成工程 |
| `docs/` | 文档与示意图 |

**绝对不能上传**（如果出现在 `git status` 里，说明 `.gitignore` 没生效，请停下来告诉我）：
`.tools/`（外部工具，数 GB）、`build/`（运行产物）、`dist/`（资产包，走 Release）、`assets/cast/`、`assets/sets/`、`assets/audio/`、`remotion/node_modules/`、任何 `.log` 文件。

再确认没有单个文件超过 50 MB（GitHub 普通文件上限 100 MB）：
```powershell
git ls-files | ForEach-Object { Get-Item $_ } | Where-Object { $_.Length -gt 50MB } | Select-Object FullName, Length
```
这条命令应当没有任何输出。

## 第 3 步：提交并推送到 GitHub
```powershell
git commit -m "开源：毛坯人生精装朋友圈 白模+渲染管线 v1.0"
```
然后在 GitHub 上创建仓库（网页创建，或用 GitHub CLI：`gh repo create maopi-life-short-drama --public --description "..." --source . --push`）。
如果用网页创建：**不要**勾选「添加 README / .gitignore / License」（本地已有），创建后执行：
```powershell
git remote add origin https://github.com/<用户名>/maopi-life-short-drama.git
git push -u origin main
```

## 第 4 步：发布 Release 并上传资产包
在仓库页面 → Releases → Draft a new release：
- Tag：`v1.0`，标题：`v1.0 固定资产`
- 说明：`角色（7 个）、场景（19 个）、配音（73 句）固定资产。安装脚本会自动下载本附件。资产许可：CC BY-NC-SA 4.0（仅限非商业用途）。`
- 附件：上传 `D:\v11\dist\assets_v1.0.zip` 和 `D:\v11\dist\assets_v1.0.sha256`
- 点击 Publish release

（GitHub CLI 也可以：`gh release create v1.0 dist\assets_v1.0.zip dist\assets_v1.0.sha256 --title "v1.0 固定资产" --notes "..."`）

## 第 5 步：把资产包地址写回仓库
发布后，复制 `assets_v1.0.zip` 的下载地址（形如 `https://github.com/<用户名>/maopi-life-short-drama/releases/download/v1.0/assets_v1.0.zip`），
在 `setup\assets_release.txt` 的**最后新增一行**写入这个地址（不要删除 `#` 开头的说明行），然后：
```powershell
git add setup\assets_release.txt
git commit -m "填写固定资产包下载地址"
git push
```

## 第 6 步：验证（在另一个空目录里模拟新电脑）
```powershell
cd D:\
git clone https://github.com/<用户名>/maopi-life-short-drama.git verify_clone
cd verify_clone
powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1
```
安装脚本应当依次完成 `[0/7]` 到 `[7/7]`，并在 `assets\cast\` 下出现 7 个 `.blend` 文件。验证通过后可以删除 `D:\verify_clone`。
（如果网络需要代理，先执行 `$env:HTTPS_PROXY="http://127.0.0.1:7897"`。）

## 完成后请告诉我
1. 仓库地址；
2. Release 地址；
3. 第 6 步验证是否通过（如有报错，请把完整报错原文发给我）。

## 注意事项
- 不要修改代码、文档、许可证内容；遇到任何报错先停下来告诉我，不要自行改动文件来绕过。
- 不要把任何账号密码、令牌写进文件或提交记录。
- 之后作品还会更新：届时重新运行第 1 步打包（版本号改为 v1.1 等）、发布新 Release，并把新地址追加到 `setup\assets_release.txt`（脚本只读取第一个地址，请把新地址放在旧地址前面，或删除旧地址行）。
