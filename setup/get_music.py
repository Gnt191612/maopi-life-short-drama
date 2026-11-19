# -*- coding: utf-8 -*-
"""下载配乐里的古典录音（维基共享资源，公有领域/CC0），并核对许可；结果放 assets/music/<id>.<ext>，许可写 assets/music/LICENSES.txt。
运行：python setup/get_music.py   （需要联网；有代理就设 HTTPS_PROXY）"""
import os, sys, json, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
OUT = os.path.join(config.ROOT, 'assets', 'music'); os.makedirs(OUT, exist_ok=True)
SRC = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'music_sources.json'), encoding='utf-8'))
# 维基媒体要求带联系方式的 User-Agent，且请求要慢一点，否则返回 429
UA = {'User-Agent': 'maopi-life-short-drama/1.0 (https://github.com/Gnt191612/maopi-life-short-drama) python-urllib'}

def get(url, tries=8):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e: print('  重试', i + 1, e); time.sleep(min(120, 10 * 2 ** i))
    raise RuntimeError('下载失败 ' + url)

lic = []
for key, s in SRC.items():
    if key.startswith('_'): continue
    api = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(
        {'action': 'query', 'titles': s['commons'], 'prop': 'imageinfo', 'iiprop': 'url|extmetadata', 'format': 'json'})
    page = next(iter(json.loads(get(api))['query']['pages'].values())); ii = page['imageinfo'][0]
    got = ii['extmetadata'].get('LicenseShortName', {}).get('value')
    if got not in ('CC0', 'Public domain'): sys.exit('许可不符，停止：%s -> %s' % (s['commons'], got))
    ext = os.path.splitext(s['commons'])[1]; dst = os.path.join(OUT, key + ext)
    if not os.path.exists(dst) or os.path.getsize(dst) == 0:
        data = get(ii['url'].split('?')[0])                      # 先下完再写文件，失败不会留下空文件
        open(dst, 'wb').write(data); print('OK', key, round(len(data) / 1e6, 1), 'MB')
        time.sleep(5)
    lic.append('%s\t%s\t%s\t%s' % (key + ext, s['title'], got, ii.get('descriptionurl', 'https://commons.wikimedia.org/wiki/' + s['commons'])))
open(os.path.join(OUT, 'LICENSES.txt'), 'w', encoding='utf-8').write('文件\t曲目\t许可\t来源\n' + '\n'.join(lic) + '\n')
print('配乐古典录音就绪：', OUT)
