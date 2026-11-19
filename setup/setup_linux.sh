#!/usr/bin/env bash
# 《毛坯人生，精装朋友圈》白模管线 —— Linux 一键安装（云端渲染服务器 / 任意 Linux 电脑）
# 用法（在仓库根目录）：  bash setup/setup_linux.sh [--with-tts] [--with-remotion]
# 需要：curl、tar、xz、unzip、python3 (3.10+)、NVIDIA 驱动（GPU 渲染）；可设 HTTPS_PROXY 走代理
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; T="$ROOT/.tools"; DL="$T/_downloads"; mkdir -p "$T" "$DL"
BV=4.5.16
WITH_TTS=0; WITH_REMOTION=0
for a in "$@"; do case "$a" in --with-tts) WITH_TTS=1;; --with-remotion) WITH_REMOTION=1;; esac; done

get() {  # get <输出文件> <URL1> [URL2 ...]
  local out="$1"; shift
  [ -f "$out" ] && { echo "  已存在 $out"; return; }
  for u in "$@"; do
    echo "  下载 $u"
    if curl -L -f --retry 5 -A 'Mozilla/5.0' ${HTTPS_PROXY:+-x "$HTTPS_PROXY"} -o "$out.part" "$u"; then mv "$out.part" "$out"; return; fi
    rm -f "$out.part"
  done
  echo "下载失败：$out（可设置 HTTPS_PROXY 后重试）"; exit 1
}

echo "[0/7] 固定资产（角色、场景、配音）"
if [ ! -f "$ROOT/assets/cast/lin.blend" ]; then
  URL="$(grep -E '^https?://' "$ROOT/setup/assets_release.txt" | head -n1 || true)"
  [ -n "$URL" ] || { echo "仓库中没有资产文件，且 setup/assets_release.txt 未填写资产包地址"; exit 1; }
  get "$DL/assets.zip" "$URL"; mkdir -p "$ROOT/assets"; unzip -q -o "$DL/assets.zip" -d "$ROOT/assets"
fi

echo "[1/7] Blender $BV LTS"
get "$DL/blender-$BV-linux-x64.tar.xz" \
  "https://download.blender.org/release/Blender4.5/blender-$BV-linux-x64.tar.xz" \
  "https://mirrors.aliyun.com/blender/release/Blender4.5/blender-$BV-linux-x64.tar.xz" \
  "https://mirror.clarkson.edu/blender/release/Blender4.5/blender-$BV-linux-x64.tar.xz"
[ -x "$T/blender/blender" ] || { tar -xJf "$DL/blender-$BV-linux-x64.tar.xz" -C "$T"; mv "$T/blender-$BV-linux-x64" "$T/blender"; }
export BLENDER_USER_RESOURCES="$T/blender_user"

echo "[2/7] MPFB 2.0.18（GPL-3.0）"
get "$DL/add-on-mpfb-v2.0.18.zip" "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"
"$T/blender/blender" -b --factory-startup --command extension install-file --repo user_default --enable "$DL/add-on-mpfb-v2.0.18.zip" >/dev/null

echo "[3/7] MakeHuman 系统素材（CC0）"
get "$DL/makehuman_system_assets_cc0.zip" \
  "https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip" \
  "https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip"
MD="$BLENDER_USER_RESOURCES/extensions/.user/user_default/mpfb/data"
[ -d "$MD/skins" ] || { mkdir -p "$MD"; unzip -q -o "$DL/makehuman_system_assets_cc0.zip" -d "$MD"; }

echo "[4/7] Rhubarb Lip Sync 1.14.0（MIT）"
get "$DL/rhubarb-linux.zip" "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Linux.zip"
[ -x "$T/rhubarb/rhubarb" ] || { unzip -q -o "$DL/rhubarb-linux.zip" -d "$DL"; mv "$DL/Rhubarb-Lip-Sync-1.14.0-Linux" "$T/rhubarb"; chmod +x "$T/rhubarb/rhubarb"; }

echo "[5/7] ffmpeg（静态版）"
get "$DL/ffmpeg-static.tar.xz" "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
[ -x "$T/ffmpeg/ffmpeg" ] || { mkdir -p "$T/ffmpeg" "$DL/ff"; tar -xJf "$DL/ffmpeg-static.tar.xz" -C "$DL/ff"; cp "$DL"/ff/*/ffmpeg "$DL"/ff/*/ffprobe "$T/ffmpeg/"; }

echo "[5b] 环境光 HDRI（CC0）与配乐古典录音（CC0/公有领域）"
python3 "$ROOT/setup/get_hdri.py"; python3 "$ROOT/setup/get_music.py"
echo "[6/7] 开源字体 Noto Sans SC（SIL OFL）"
mkdir -p "$T/fonts"; get "$T/fonts/NotoSansSC-Regular.ttf" "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
# 手机屏幕界面要用静态字重（Blender 读可变字体只会用最细的字重）
python3 -m pip install -q fonttools
for w in "400 Regular" "700 Bold"; do set -- $w; [ -f "$T/fonts/NotoSansSC-Static-$2.ttf" ] || python3 -m fontTools.varLib.instancer "$T/fonts/NotoSansSC-Regular.ttf" "wght=$1" -o "$T/fonts/NotoSansSC-Static-$2.ttf"; done

echo "[7/7] CMU 动作捕捉片段 + Python 依赖"
mkdir -p "$ROOT/build/mocap"
grep -E '^[0-9]' "$ROOT/setup/mocap_clips.txt" | cut -f1 | while read -r c; do
  s="${c%%_*}"; get "$ROOT/build/mocap/$c.bvh" "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/0$s/$c.bvh"
done
python3 -m pip install --quiet -r "$ROOT/setup/requirements.txt"

[ "$WITH_REMOTION" = 1 ] && (cd "$ROOT/remotion" && npm install --no-fund --no-audit)
[ "$WITH_TTS" = 1 ] && bash "$ROOT/setup/setup_tts_linux.sh"
echo; echo "安装完成。下一步：  python3 run_all.py"
