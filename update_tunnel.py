#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每次 cloudflared 重启后运行此脚本，自动更新永久跳转链接"""
import os, sys

INDEX_FILE = r"C:\Users\LEGION\ai-clone\docs\index.html"

new_url = sys.argv[1] if len(sys.argv) > 1 else input("请输入新的 tunnel URL: ").strip()

if not new_url.startswith("https://") or "trycloudflare.com" not in new_url:
    print("URL 格式不对，应该是 https://xxx.trycloudflare.com")
    sys.exit(1)

template = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>AI 分身</title>
<meta http-equiv="refresh" content="0; url={url}">
</head>
<body style="text-align:center;padding-top:40vh;font-family:sans-serif">
  <p>正在跳转...</p>
  <a href="{url}">如果未跳转请点这里</a>
</body>
</html>
'''

with open(INDEX_FILE, 'w', encoding='utf-8') as f:
    f.write(template.format(url=new_url))

os.chdir(r"C:\Users\LEGION\ai-clone")
os.system("git add docs/index.html")
os.system(f'git commit -m "chore: update tunnel URL"')
os.system("git push")

print(f"\n已更新！永久链接不变：https://bai698304.github.io/git/")
