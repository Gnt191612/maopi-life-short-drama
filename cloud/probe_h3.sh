#!/bin/bash
# 开机后查 MiniMax H3（2026-08 发布，开放权重，原生 24fps、单段最长约 15 秒，支持 Depth/Pose 控制视频）在这个镜像里的情况，只看不改：
#   镜像标题写着「Moss/Krea2 超写实人像+Wan2.2/MiniMaxH3」，但 11-26 版只用了其中的 Wan2.2 图生视频，H3 从没用过
#   输出 /root/h3_probe.txt：H3 相关模型文件、相关工作流（含 ComfyUI 官方模板 fun_controlnet_union / i2v / r2v）、相关节点的输入定义、ComfyUI 版本
R=/root/h3_probe.txt; : > $R
say() { echo "$@" | tee -a $R; }
say "== ComfyUI 版本"; (cd /root/ComfyUI && git log -1 --format='%cd %h' 2>/dev/null; cat comfyui_version.py 2>/dev/null) | tee -a $R
say "== H3 模型文件"; find -L /root/ComfyUI/models -iname '*h3*' -o -iname '*minimax*' 2>/dev/null | xargs -r ls -la --block-size=M 2>/dev/null | tee -a $R
say "== 含 H3/MiniMax 的工作流"; grep -lis 'minimax\|h3' /root/ComfyUI/user/default/workflows/*.json 2>/dev/null | tee -a $R
say "== 官方模板里的 H3 工作流"; find / -path /proc -prune -o -iname '*minimax_h3*.json' -print 2>/dev/null | head -20 | tee -a $R
say "== 相关节点输入定义"
curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json,sys; d=json.load(sys.stdin)
for k,v in d.items():
    if any(s in k.lower() for s in ('minimax','h3','controlnetunion','union','addguide','fastvideo')):
        print(k, json.dumps(v['input'], ensure_ascii=False)[:900])
" | tee -a $R
echo "写在 $R"
