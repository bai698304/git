#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每次 cloudflared 重启后运行此脚本，自动更新永久跳转链接"""
import os, sys

TUNNEL_FILE = r"C:\Users\LEGION\ai-clone\docs\tunnel.txt"

new_url = sys.argv[1] if len(sys.argv) > 1 else input("请输入新的 tunnel URL: ").strip()

if not new_url.startswith("https://") or "trycloudflare.com" not in new_url:
    print("URL 格式不对，应该是 https://xxx.trycloudflare.com")
    sys.exit(1)

with open(TUNNEL_FILE, 'w') as f:
    f.write(new_url + "\n")

os.chdir(r"C:\Users\LEGION\ai-clone")
os.system("git add docs/tunnel.txt")
os.system(f'git commit -m "chore: update tunnel URL to {new_url.split(\"//\")[1][:30]}"')
os.system("git push")

print(f"\n已更新！永久链接不变：https://bai698304.github.io/git/")
