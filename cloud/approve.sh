#!/bin/bash
# 往云端审核清单 kf_ok.txt 追加条目（首帧 <id>、尾帧 <id>@end）：先保证文件以换行结尾
# 11-28：文件末尾没换行时，新条目粘在最后一个 id 后面（s10_00_0860s01_01_1174@end），那个镜头的审核就失效了
# 用法：bash approve.sh s01_01_1174@end s02_01_0606@end ...
F=/root/v11_out/kf_ok.txt
[ -n "$(tail -c1 $F)" ] && echo >> $F
for x in "$@"; do grep -qw -- "$x" $F || echo "$x" >> $F; done
tail -c 200 $F; echo
