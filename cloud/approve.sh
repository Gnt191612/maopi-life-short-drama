#!/bin/bash
# 寰€瀹℃牳娓呭崟杩藉姞鏉＄洰锛氬厛淇濊瘉鏂囦欢浠ユ崲琛岀粨灏撅紙11-28锛氭病鎹㈣鏃舵柊鏉＄洰绮樺湪鏈€鍚庝竴涓?id 鍚庨潰锛岄偅涓暅澶寸殑瀹℃牳澶辨晥锛?F=/root/v11_out/kf_ok.txt; [ -n "$(tail -c1 $F)" ] && echo >> $F
for x in "$@"; do grep -qw -- "$x" $F || echo "$x" >> $F; done
tail -c 200 $F; echo
