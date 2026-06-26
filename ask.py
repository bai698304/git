#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 分身 - 迭代深入问卷系统
原则：不引导、不假设、不预设答案。你说什么，我问什么。
每次运行可以随时中断，下次继续。
"""

import json, os, sys
from datetime import datetime

PROFILE_PATH = r"C:\Users\LEGION\ai-clone\phase2_output\persona_profile.json"
STATE_PATH = r"C:\Users\LEGION\ai-clone\phase2_output\ask_state.json"

# ========== 未覆盖领域（从 phase2_analyze 结果提取，可扩展） ==========
UNCOVERED_DOMAINS = [
    "认知科学", "心理学", "经济学", "历史", "物理", "计算机",
    "文学", "哲学", "社会学", "政治", "宗教/信仰", "审美/艺术",
    "童年经历", "家庭关系", "情感经历", "恐惧与弱点", "梦想与抱负",
    "金钱观", "健康习惯", "社交偏好", "冲突处理方式", "对AI的态度"
]

# 追问触发器 —— 如果用户在回答中提到了这些词，深入追问
DEEPEN_TRIGGERS = {
    "经历": "能说一件具体的事吗？",
    "以前": "那是哪一年的事？后来怎么样了？",
    "我认为": "这个想法是怎么形成的？",
    "喜欢": "还有其他喜欢的吗？",
    "不喜欢": "能说说是为什么吗？",
    "重要": "对你来说为什么重要？",
    "改变": "是什么让你改变了？",
    "例子": "还有别的例子吗？",
    "因为": "这个因果关系你在生活中验证过吗？",
    "但是": "你在纠结什么？两边都说说看？",
}

def load_or_init_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "completed_domains": [],
        "current_domain": None,
        "current_depth": 0,
        "answers": {},
        "started_at": datetime.now().isoformat(),
        "last_updated": None,
    }

def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def pick_next_domain(state):
    for d in UNCOVERED_DOMAINS:
        if d not in state["completed_domains"]:
            return d
    return None

def ask_first(domain):
    """第一次提问——完全开放"""
    return f"关于「{domain}」，你有什么想说的？"

def ask_deepen(answer):
    """基于用户回答的追问——只在用户提到的内容上深入"""
    for trigger, question in DEEPEN_TRIGGERS.items():
        if trigger in answer:
            return question
    # 默认追问：请展开
    return "能再多说一点吗？"

def is_done(answer):
    """用户是否表示说完了"""
    done_markers = ["说完了", "就这些", "没有了", "没了", "差不多", "够了", "done", "ok"]
    short = answer.strip().lower()
    return len(short) < 5 or any(m in short for m in done_markers)

def main():
    state = load_or_init_state()

    # 选择下一个领域
    if state["current_domain"] is None:
        domain = pick_next_domain(state)
        if domain is None:
            print("\n[完成] 所有领域已覆盖。你的回答已保存。")
            return
        state["current_domain"] = domain
        state["current_depth"] = 0
        save_state(state)
        print(f"\n{'='*50}")
        print(ask_first(domain))
        print()
        return

    # 读取用户输入
    print("\n（请输入你的回答，说完了请回复「说完了」或直接简短回复）\n")
    answer = input("> ").strip()

    if not answer:
        print("请至少写点什么，或者说「说完了」跳过。")
        return

    domain = state["current_domain"]
    depth = state["current_depth"]

    # 记录答案
    if domain not in state["answers"]:
        state["answers"][domain] = []
    state["answers"][domain].append({
        "depth": depth,
        "answer": answer,
        "time": datetime.now().isoformat(),
    })

    # 判断是否该深入还是结束这个领域
    if is_done(answer):
        state["completed_domains"].append(domain)
        state["current_domain"] = None
        state["current_depth"] = 0
        save_state(state)
        print(f"\n[已记录] 「{domain}」的回答已保存。")

        # 自动继续下一个
        next_d = pick_next_domain(state)
        if next_d:
            state["current_domain"] = next_d
            state["current_depth"] = 0
            save_state(state)
            print(f"\n{'='*50}")
            print(ask_first(next_d))
            print()
        else:
            print("\n[完成] 所有领域已覆盖！")
    elif depth < 2:
        # 继续深入（最多深入 3 层）
        state["current_depth"] = depth + 1
        save_state(state)
        print(f"\n{ask_deepen(answer)}")
        print()
    else:
        # 深度够了，结束这个领域
        state["completed_domains"].append(domain)
        state["current_domain"] = None
        state["current_depth"] = 0
        save_state(state)
        print(f"\n[已记录] 「{domain}」的回答已保存。")

        next_d = pick_next_domain(state)
        if next_d:
            state["current_domain"] = next_d
            state["current_depth"] = 0
            save_state(state)
            print(f"\n{'='*50}")
            print(ask_first(next_d))
            print()
        else:
            print("\n[完成] 所有领域已覆盖！")

if __name__ == "__main__":
    main()
