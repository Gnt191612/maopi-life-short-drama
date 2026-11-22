#!/usr/bin/env bash
# 在任意仙宫云实例上装「人物重建 / 白模渲染」环境（不依赖从本地上传大文件）：
# Blender 4.5.16、MPFB 2.0.18 + MakeHuman 系统素材、社区服装包都由云端直接下载；
# 本地只需上传 /root/v11_upload/ 下的 mh_hair.tgz（发型包）、film_assets.tgz（代码/场景/配音等）。
set -e
ROOT=/root/v11; T=$ROOT/.tools; UP=/root/v11_upload; DL=/root/v11_dl; BV=4.5.16
mkdir -p $T $DL /root/v11_assets/mh_community $ROOT/build/mocap
export BLENDER_USER_RESOURCES=$T/blender_user
get() { out=$1; shift; [ -s "$out" ] && return 0; for u in "$@"; do curl -fsL --retry 3 --connect-timeout 20 -o "$out.part" "$u" && mv "$out.part" "$out" && return 0; done; echo "下载失败 $out"; return 1; }
dpkg -s libegl1 >/dev/null 2>&1 || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libxi6 libxkbcommon0 libxrender1 libsm6 libgl1 libegl1 libxxf86vm1 libxfixes3 xz-utils unzip ffmpeg >/dev/null; }
get $DL/blender.tar.xz https://mirrors.tuna.tsinghua.edu.cn/blender/release/Blender4.5/blender-$BV-linux-x64.tar.xz https://download.blender.org/release/Blender4.5/blender-$BV-linux-x64.tar.xz
[ -x /opt/v11blender/blender ] || { tar -xJf $DL/blender.tar.xz -C /opt && mv /opt/blender-$BV-linux-x64 /opt/v11blender; }
ln -sfn /opt/v11blender $T/blender
get $DL/mpfb.zip "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"
[ -d $T/blender_user/extensions/user_default/mpfb ] || /opt/v11blender/blender -b --factory-startup --command extension install-file --repo user_default --enable $DL/mpfb.zip >/dev/null
get $DL/mh_sys.zip https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
MD=$T/blender_user/extensions/.user/user_default/mpfb/data; [ -d $MD/skins ] || { mkdir -p $MD; unzip -q -o $DL/mh_sys.zip -d $MD; }
for f in shirts01/shirts01_cc0.zip shirts02/shirts02_ccby.zip pants01/pants01_cc0.zip pants02/pants02_ccby.zip skirts02/skirts02_cc-by.zip shoes01/shoes01_cc0.zip; do
  n=${f%%/*}; [ -d /root/v11_assets/mh_community/$n/clothes ] && continue
  get $DL/$n.zip https://files.makehumancommunity.org/asset_packs/$f https://files2.makehumancommunity.org/asset_packs/$f
  mkdir -p /root/v11_assets/mh_community/$n && unzip -q -o $DL/$n.zip -d /root/v11_assets/mh_community/$n
done
grep -E '^[0-9]' /dev/null >/dev/null
for c in 07_01 13_33 13_01; do get $ROOT/build/mocap/$c.bvh https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/0${c%%_*}/$c.bvh || true; done
[ -f $UP/mh_hair.tgz ] && tar -xzf $UP/mh_hair.tgz -C $T
[ -f $UP/film_assets.tgz ] && tar -xzf $UP/film_assets.tgz -C $ROOT
python3 -c "import numpy" 2>/dev/null || pip install -q numpy
/opt/v11blender/blender -b --factory-startup --python-expr "import bpy; print('BLENDER OK', bpy.app.version_string)" 2>/dev/null | grep 'BLENDER OK'
echo ENV DONE
