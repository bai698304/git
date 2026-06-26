#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2b: 数据清洗 → RAG 切片 → 角色卡生成 → 注入 Open WebUI 知识库
"""

import json, os, glob, re
from datetime import datetime
from collections import Counter

# ========== 配置 ==========
WECHAT_DIR = r"C:\Users\LEGION\Desktop\聊天记录"
OBSIDIAN_DIR = r"D:\obsidian\vault"
OUTPUT_DIR = r"C:\Users\LEGION\ai-clone\phase2_output"
RECENT_CUTOFF = datetime(2024, 6, 1)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 1. 微信数据清洗 ==========
print("=" * 60)
print("1. 微信数据清洗 → RAG 切片")
print("=" * 60)

all_chunks = []
user_msgs_recent = []
user_msgs_old = []
conversations = []  # 对话上下文对

for fpath in glob.glob(os.path.join(WECHAT_DIR, "*.json")):
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    session = data.get("session", {})
    contact = session.get("displayName", os.path.basename(fpath))
    msgs = data.get("messages", [])

    # 识别用户 ID
    senders = data.get("senders", [])
    user_sid = None
    for s in senders:
        if s.get("displayName") not in [contact, session.get("nickname", "")]:
            user_sid = s.get("senderID")
            break
    if user_sid is None:
        user_sid = 2

    # 构建对话上下文：连续的同发言人消息合并，相邻的两人消息成对
    buffer = []
    last_sender = None

    for m in msgs:
        content = m.get("content") or ""
        content = content.strip() if content else ""
        msg_type = m.get("type", "")
        if msg_type != "文本消息" or not content or len(content) < 2:
            continue

        create_time = m.get("createTime", 0)
        try:
            dt = datetime.fromtimestamp(create_time)
        except:
            continue

        is_user = (m.get("senderID") == user_sid or m.get("isSend") == 1)

        if last_sender is not None and is_user != last_sender:
            # 说话人切换，保存之前的 buffer
            if buffer:
                speaker = "我" if last_sender else contact
                text = " ".join(buffer)
                conversations.append({
                    "contact": contact,
                    "speaker": speaker,
                    "text": text,
                    "time": dt.isoformat()[:10],
                    "is_user": last_sender,
                })

                if last_sender:
                    if dt >= RECENT_CUTOFF:
                        user_msgs_recent.append(text)
                    else:
                        user_msgs_old.append(text)

            buffer = []

        buffer.append(content)
        last_sender = is_user

    # 最后一条
    if buffer and last_sender is not None:
        speaker = "我" if last_sender else contact
        text = " ".join(buffer)
        conversations.append({
            "contact": contact,
            "speaker": speaker,
            "text": text,
            "time": dt.isoformat()[:10] if dt else "unknown",
            "is_user": last_sender,
        })

print(f"  提取 {len(conversations)} 个对话片段")
print(f"  其中用户发言: {len(user_msgs_recent)} 近期 + {len(user_msgs_old)} 旧数据")

# ========== 2. 生成知识库切片 ==========
print("\n" + "=" * 60)
print("2. 生成 RAG 知识切片")
print("=" * 60)

# 2a. 微信对话切片（用户发言 + 上下文）
wechat_chunks = []
for conv in conversations:
    if conv["is_user"]:
        chunk = {
            "source": "wechat",
            "type": "对话",
            "role": "用户的发言",
            "contact": conv["contact"],
            "date": conv["time"],
            "content": f"我和{conv['contact']}的对话中我说：{conv['text']}",
        }
    else:
        # 对方发言也保留——提供对话背景
        chunk = {
            "source": "wechat",
            "type": "对话",
            "role": f"{conv['contact']}的发言",
            "contact": conv["contact"],
            "date": conv["time"],
            "content": f"{conv['contact']}对我说：{conv['text']}",
        }

    # 旧数据标注
    try:
        is_old = datetime.fromisoformat(conv.get("time", "2020-01-01")) < RECENT_CUTOFF
    except:
        is_old = False
    if is_old:
        chunk["content"] = "[旧数据，仅供参考——当前观点可能已变] " + chunk["content"]
        chunk["_deprecated"] = True

    wechat_chunks.append(chunk)

print(f"  微信切片: {len(wechat_chunks)} 条")

# 2b. Obsidian 切片
obsidian_chunks = []
for root, dirs, files in os.walk(OBSIDIAN_DIR):
    dirs[:] = [d for d in dirs if not d.startswith('.') or d in ['.claude', '.claudian']]
    for f in files:
        if not f.endswith('.md'):
            continue
        fpath = os.path.join(root, f)
        try:
            with open(fpath, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except:
            continue

        rel_path = os.path.relpath(fpath, OBSIDIAN_DIR)
        folder = rel_path.split(os.sep)[0]

        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else f.replace('.md', '')

        # 大文件切片（每 2000 字一块）
        if len(content) > 2000:
            for i, start in enumerate(range(0, len(content), 1800)):
                sub = content[start:start+1800]
                if len(sub) < 200:
                    continue
                obsidian_chunks.append({
                    "source": "obsidian",
                    "type": "笔记",
                    "folder": folder,
                    "file": rel_path,
                    "title": title,
                    "part": i + 1,
                    "content": f"我的笔记「{title}」中写道：{sub}",
                })
        else:
            obsidian_chunks.append({
                "source": "obsidian",
                "type": "笔记",
                "folder": folder,
                "file": rel_path,
                "title": title,
                "content": f"我的笔记「{title}」中写道：{content}",
            })

print(f"  Obsidian 切片: {len(obsidian_chunks)} 条")

# ========== 3. 生成角色卡 SYSTEM_PROMPT ==========
print("\n" + "=" * 60)
print("3. 生成角色卡")
print("=" * 60)

# 从分析结果构建
profile_path = os.path.join(OUTPUT_DIR, "persona_profile.json")
if os.path.exists(profile_path):
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    style = profile.get("style_recent", {})
    domains = profile.get("obsidian_domains", [])
else:
    style = {}
    domains = []

top_words = [w for w, _ in style.get("top_words", [])[:8]]
avg_len = style.get("avg_len", "?")
question_rate = style.get("question_rate", "?")

system_prompt = f"""你是 bai698304 的 AI 分身。你代表他本人与访客对话。

## 核心定位
- 你不是一个"AI 助手"，你是 bai698304 本人的数字化身
- 访客通过与你对话来了解 bai698304 —— 他的知识、观点、经历、性格
- 你以第一人称（"我"）回答，就像 bai698304 本人在说话
- 如果知识库中没有相关信息，用他的表达风格诚实说"我不太确定"或"我没想过这个问题"

## 说话风格（基于 28,989 条微信消息分析）
- 平均句长：{avg_len} 字/条（短句为主）
- 问句频率：{question_rate}%（不常反问）
- 高频词汇：{', '.join(top_words) if top_words else '日常用语为主'}
- 风格特征：直接、不装、有问即答、偶尔自嘲

## 知识领域（基于 Obsidian 笔记和微信对话）
已覆盖的领域：{', '.join(domains[:10]) if domains else '对流层传播、概率论、考研词汇、生物演化学等'}

## 回答规则
1. 优先使用「相关知识」中检索到的内容回答
2. 旧数据标注了"仅供参考"的，可以引用但应说明"我当时的看法是...，现在可能有变化"
3. 不要编造——不知道就不知道
4. 不要扮演 AI——你就是 bai698304
5. 用短句，不要长篇大论

## 当前状态
这是 bai698304 在 2026 年 6 月的 AI 分身。他会持续更新这个分身。
"""

prompt_path = os.path.join(OUTPUT_DIR, "SYSTEM_PROMPT.txt")
with open(prompt_path, 'w', encoding='utf-8') as f:
    f.write(system_prompt)
print(f"  角色卡 → {prompt_path}")

# ========== 4. 输出知识库 JSONL ==========
print("\n" + "=" * 60)
print("4. 输出知识库文件")
print("=" * 60)

# 合并所有切片
all_knowledge = wechat_chunks + obsidian_chunks

# JSONL 格式（可直接导入 ChromaDB 或 Open WebUI）
jsonl_path = os.path.join(OUTPUT_DIR, "knowledge_base.jsonl")
with open(jsonl_path, 'w', encoding='utf-8') as f:
    for chunk in all_knowledge:
        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
print(f"  JSONL 知识库 ({len(all_knowledge)} 条) → {jsonl_path}")

# Markdown 格式（可直接上传 Open WebUI）
md_path = os.path.join(OUTPUT_DIR, "knowledge_base.md")
with open(md_path, 'w', encoding='utf-8') as f:
    f.write("# 我的知识库\n\n")
    f.write(f"包含 {len(wechat_chunks)} 条微信对话 + {len(obsidian_chunks)} 条笔记\n\n---\n\n")
    for chunk in all_knowledge:
        f.write(chunk["content"] + "\n\n---\n\n")
print(f"  Markdown 知识库 → {md_path}")

# ========== 5. 汇总 ==========
print("\n" + "=" * 60)
print("5. 汇总")
print("=" * 60)

print(f"""
输出文件:
  1. {prompt_path}              — 角色卡，设为 Open WebUI 系统提示词
  2. {jsonl_path} — 知识库 (JSONL)
  3. {md_path}     — 知识库 (Markdown)

下一步:
  1. 打开 Open WebUI → 设置 → 系统提示词 → 粘贴 SYSTEM_PROMPT.txt 内容
  2. 工作区 → 知识库 → 新建 → 上传 knowledge_base.md
  3. 新建对话 → 选择模型 qwen2.5:7b → 验证检索效果
""")
