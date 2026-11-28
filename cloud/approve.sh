#!/bin/bash
# 往云端审核清单 kf_ok.txt 追加条目（首帧 <id>、尾帧 <id>@end）：先保证文件以换行结尾
# 11-28：文件末尾没换行时，新条目粘在最后一个 id 后面（s10_00_0860s01_01_1174@end），那个镜头的审核就失效了
# 用法：bash approve.sh s01_01_1174@end s02_01_0606@end ...
#       bash approve.sh --remove s05_00_0001      撤销审核（首帧要重做时）。清单里一行可能有多个 id（空格隔开），按单词删，不能按整行删
F=/root/v11_out/kf_ok.txt
if [ "$1" = "--remove" ]; then
  shift; for x in "$@"; do sed -i -E "s/(^| )$x( |$)/\1\2/g; s/  +/ /g; /^ *$/d" $F; done
  for x in "$@"; do echo "$x 剩 $(grep -ow -- "$x" $F | wc -l) 条"; done; exit
fi
[ -n "$(tail -c1 $F)" ] && echo >> $F
for x in "$@"; do grep -qw -- "$x" $F || echo "$x" >> $F; done
tail -c 200 $F; echo
