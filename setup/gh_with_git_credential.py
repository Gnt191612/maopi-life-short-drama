# -*- coding: utf-8 -*-
"""用 git 凭据管理器里已保存的 GitHub 令牌运行 gh 命令（令牌只在本进程内存中传给 gh，不显示、不写盘）。
用法：python setup/gh_with_git_credential.py release create v1.1 dist/assets_v1.1.zip --repo <用户>/<仓库> ...
（Windows PowerShell 5.1 向 git 传标准输入会带 BOM/编码问题，所以用 Python 实现）"""
import os, subprocess, sys

def github_token():
    r = subprocess.run(['git', 'credential', 'fill'], input=b'protocol=https\nhost=github.com\n\n', capture_output=True, timeout=120)
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        if line.startswith('password='): return line[len('password='):].strip()
    sys.exit('凭据管理器里没有找到 github.com 的令牌（先用 git push 登录一次）')

if __name__ == '__main__':
    env = dict(os.environ, GH_TOKEN=github_token())
    sys.exit(subprocess.run(['gh'] + sys.argv[1:], env=env).returncode)
