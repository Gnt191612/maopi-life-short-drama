> **已过时（2026-11-19 的 Wan2.1-VACE 方案）。现行流程见 [cloud/写实化会话流程.md](写实化会话流程.md)。**

# 在仙宫云上做 AI 写实化：操作步骤

> 原则：**人物建模定稿后再上云**（按分钟计费）。先用 `--test` 试跑一个镜头看效果，满意再整片跑。

## 0. 本地准备（在自己电脑上）

```bash
# 1) 全片预演渲染（得到白模画面 + 固定标尺深度图），已跑过可跳过
V11_PREVIEW=1 python run_all.py
# 2) 角色定妆照（长相参考），已生成可跳过：assets/lookdev/
# 3) 打包：导出骨架 + 按镜头切分任务 + 压缩
python cloud/pack_for_cloud.py --pose
```
得到 `dist/cloud_pack.zip`（另外把 `cloud/setup_cloud.sh`、`cloud/realism.py` 一起上传）。

## 1. 开实例

- 控制台：https://www.xiangongyun.com/console/instance
- 显卡：**RTX 4090（24 GB）** 可以跑 14B（自动分块放显存，较慢）；有 48 GB 以上的卡（如 A6000 / A800 / L40）更快。
- 镜像：选 **PyTorch 2.x + CUDA 12.x** 的基础镜像。
- 系统盘 100 GB 足够（14B 模型约 75 GB，1.3B 约 20 GB；空间紧就先用 1.3B 试跑）。

## 2. 上传与准备

用实例自带的 JupyterLab 上传，或 `scp`：
```bash
scp -P <端口> dist/cloud_pack.zip cloud/setup_cloud.sh cloud/realism.py root@<实例地址>:~/v11cloud/
```
在实例终端里：
```bash
cd ~/v11cloud && unzip -q cloud_pack.zip
bash setup_cloud.sh 1.3B      # 先装小模型试跑（下载快、便宜）；正式用 14B：bash setup_cloud.sh 14B
```

## 3. 试跑一个镜头（几分钟）

```bash
source venv/bin/activate
python realism.py --model 1.3B --test
```
下载 `out/` 里的视频看效果：长相是否像定妆照、动作是否和白模一致、有没有闪烁。

## 4. 整片

```bash
nohup python realism.py --model 14B > run.log 2>&1 &     # 后台跑，断开 SSH 也不停；可断点续跑
tail -f out/progress.log                                 # 看进度
```
只重跑某几个镜头：删掉 `out/<任务id>.mp4` 后加 `--only <任务id前缀>`。
控制方式可选 `--control depth|pose|depth+pose`（默认叠加）。

## 5. 取回与合成成片（本地）

把实例上的 `out/` 整个下载到本地，例如 `D:\v11\build\cloud_out\`，然后：
```bash
python run_all.py --previs-only --real=build/cloud_out
```
成片在 `build/final/v11_previs_full.mp4`（配音、配乐、字幕自动加上；没生成的帧用白模补）。

**跑完记得在控制台销毁实例，停止计费。**
