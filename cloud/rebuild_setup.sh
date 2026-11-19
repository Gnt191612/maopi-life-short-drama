#!/usr/bin/env bash
# 仙宫云实例上搭「人物重建」环境（基础镜像 Miniconda3 / Ubuntu 22.04）：Blender 4.5 + MPFB/MakeHuman 素材 + 服装包 + 项目代码。
# 由本地 cloud/rebuild_remote.ps1 自动调用；素材包已由本地上传到 /root/v11_upload/
set -e
V=4.5.16; ROOT=/root/v11; UP=/root/v11_upload
mkdir -p $ROOT/.tools /root/v11_assets/mh_community
# 1) 系统库（Blender 无界面运行 EEVEE 需要 EGL）
if ! dpkg -s libegl1 >/dev/null 2>&1; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libxi6 libxkbcommon0 libxrender1 libsm6 libgl1 libegl1 libxxf86vm1 libxfixes3 xz-utils >/dev/null
fi
# 2) Blender 本体（国内镜像优先）
if [ ! -x $ROOT/.tools/blender/blender ]; then
  F=blender-$V-linux-x64.tar.xz; cd /root
  for U in https://mirrors.tuna.tsinghua.edu.cn/blender/release/Blender4.5/$F https://mirrors.ustc.edu.cn/blender/release/Blender4.5/$F https://download.blender.org/release/Blender4.5/$F; do
    curl -fL --retry 3 --connect-timeout 20 -o $F "$U" && break
  done
  tar -xJf $F && rm -rf $ROOT/.tools/blender && mv blender-$V-linux-x64 $ROOT/.tools/blender && rm -f $F
fi
# 3) 素材与代码
[ -f $UP/blender_user.tgz ] && tar -xzf $UP/blender_user.tgz -C $ROOT/.tools && rm $UP/blender_user.tgz
[ -f $UP/mh_hair.tgz ] && tar -xzf $UP/mh_hair.tgz -C $ROOT/.tools && rm $UP/mh_hair.tgz
for z in $UP/*.zip; do
  [ -f "$z" ] || continue
  n=$(basename "$z" | sed -E 's/_(cc0|ccby|cc-by)\.zip$//'); mkdir -p /root/v11_assets/mh_community/$n
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$z" /root/v11_assets/mh_community/$n && rm "$z"
done
[ -f $UP/code.tgz ] && tar -xzf $UP/code.tgz -C $ROOT && rm $UP/code.tgz
$ROOT/.tools/blender/blender -b --factory-startup --python-expr "import bpy; print('BLENDER OK', bpy.app.version_string)" 2>/dev/null | grep 'BLENDER OK'
echo SETUP DONE
