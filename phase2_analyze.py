#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2: 微信 + Obsidian 数据解析、分层、人格特征提取、知识盲区检测
输出：人格画像初稿 + 补充问卷
"""

import json, os, glob, re
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# ========== 配置 ==========
WECHAT_DIR = r"C:\Users\LEGION\Desktop\聊天记录"
OBSIDIAN_DIR = r"D:\obsidian\vault"
OUTPUT_DIR = r"C:\Users\LEGION\ai-clone\phase2_output"
RECENT_CUTOFF = datetime(2024, 6, 1)  # 近两年分界

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 工具函数 ==========
def safe_read_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [ERROR] {os.path.basename(path)}: {e}")
        return None

# ========== 1. 微信数据解析 ==========
print("=" * 60)
print("1. 微信聊天记录解析")
print("=" * 60)

all_contacts = {}
recent_msgs = []      # 近两年用户发言
old_msgs = []          # 旧数据用户发言
all_user_msgs = []     # 所有用户发言
other_msgs = []        # 对方发言（上下文）
recent_topics = Counter()
old_topics = Counter()

for fpath in glob.glob(os.path.join(WECHAT_DIR, "*.json")):
    fname = os.path.basename(fpath)

    data = safe_read_json(fpath)
    if not data:
        continue

    session = data.get("session", {})
    contact = session.get("displayName", fname)
    msg_count = session.get("messageCount", 0)

    senders = data.get("senders", [])
    # 找出用户的 senderID（remark 为空或 displayName 不是联系人的那个）
    user_sender_id = None
    for s in senders:
        if s.get("displayName") not in [contact, session.get("nickname", "")]:
            user_sender_id = s.get("senderID")
            break
    # 如果没找到，默认 senderID=2 是用户
    if user_sender_id is None:
        user_sender_id = 2

    msgs = data.get("messages", [])
    user_recent = []
    user_old = []

    for m in msgs:
        content = m.get("content", "")
        if not content or len(content.strip()) < 1:
            continue

        create_time = m.get("createTime", 0)
        try:
            dt = datetime.fromtimestamp(create_time)
        except:
            continue

        is_user = (m.get("senderID") == user_sender_id or m.get("isSend") == 1)
        msg_type = m.get("type", "")

        # 只处理文本消息
        if msg_type != "文本消息":
            continue

        msg_obj = {
            "contact": contact,
            "content": content,
            "time": dt.isoformat(),
            "is_user": is_user,
        }

        if is_user:
            all_user_msgs.append(msg_obj)
            if dt >= RECENT_CUTOFF:
                user_recent.append(msg_obj)
            else:
                user_old.append(msg_obj)
                msg_obj["_deprecated"] = True  # 标记旧数据
        else:
            other_msgs.append(msg_obj)

    recent_msgs.extend(user_recent)
    old_msgs.extend(user_old)
    all_contacts[contact] = {
        "total": msg_count,
        "recent_user": len(user_recent),
        "old_user": len(user_old),
    }

    print(f"  {contact}: {len(user_recent)} 近期 + {len(user_old)} 旧数据 = {msg_count} 总消息")

print(f"\n  总计: {len(recent_msgs)} 条近期用户发言, {len(old_msgs)} 条旧数据, {len(other_msgs)} 条对方发言")

# ========== 2. 说话风格分析 ==========
print("\n" + "=" * 60)
print("2. 说话风格分析")
print("=" * 60)

def analyze_style(msgs, label):
    if not msgs:
        return {}

    all_text = " ".join([m["content"] for m in msgs])
    lengths = [len(m["content"]) for m in msgs]

    # 平均长度
    avg_len = sum(lengths) / len(lengths)

    # 高频词（2-4字中文词）
    words = re.findall(r'[一-鿿]{2,4}', all_text)
    word_freq = Counter(words).most_common(30)

    # 标点偏好
    question_count = all_text.count("?") + all_text.count("？")
    exclaim_count = all_text.count("!") + all_text.count("！")
    ellipsis_count = all_text.count("...") + all_text.count("…")

    # 表情/语气词
    ha_count = len(re.findall(r'[哈嘿呵嘻哼呃诶哇呀]{2,}', all_text))

    # emoji
    emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', all_text))

    stats = {
        "avg_len": round(avg_len, 1),
        "total_msgs": len(msgs),
        "question_rate": round(question_count / len(msgs) * 100, 1),
        "exclaim_rate": round(exclaim_count / len(msgs) * 100, 1),
        "ha_count": ha_count,
        "emoji_count": emoji_count,
        "top_words": word_freq[:15],
    }

    print(f"  {label}: 均长{stats['avg_len']}字, 问句率{stats['question_rate']}%, 感叹率{stats['exclaim_rate']}%")
    print(f"  高频词: {[w for w, _ in stats['top_words'][:8]]}")

    return stats

recent_style = analyze_style(recent_msgs, "近期风格")
old_style = analyze_style(old_msgs, "旧数据风格")

# ========== 3. Obsidian 解析 ==========
print("\n" + "=" * 60)
print("3. Obsidian 知识库解析")
print("=" * 60)

obsidian_domains = {}
obsidian_files = []

for root, dirs, files in os.walk(OBSIDIAN_DIR):
    # 跳过隐藏目录和系统目录
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

        # 提取标签
        tags = re.findall(r'#[一-鿿\w]+', content)

        obsidian_files.append({
            "path": rel_path,
            "folder": folder,
            "title": title,
            "size": len(content),
            "tags": tags,
        })

        if folder not in obsidian_domains:
            obsidian_domains[folder] = {"count": 0, "files": [], "tags": []}
        obsidian_domains[folder]["count"] += 1
        obsidian_domains[folder]["files"].append(title)
        obsidian_domains[folder]["tags"].extend(tags)

print(f"  总文件数: {len(obsidian_files)}")
for domain, info in sorted(obsidian_domains.items(), key=lambda x: x[1]['count'], reverse=True):
    if domain.startswith('.'):
        continue
    print(f"  {domain}: {info['count']} 篇")

# ========== 4. 主题/知识领域提取 ==========
print("\n" + "=" * 60)
print("4. 已覆盖知识领域")
print("=" * 60)

# 从 Obsidian 文件夹名 + 标签提取
covered_domains = set()
for domain in obsidian_domains:
    if not domain.startswith('.'):
        covered_domains.add(domain)

# 从微信聊天高频词推断话题（简单方法）
topic_keywords = {
    "技术/编程": ["代码", "程序", "bug", "python", "github", "AI", "算法", "数据", "服务器", "接口", "前端", "后端"],
    "游戏": ["游戏", "打游戏", "steam", "LOL", "王者", "原神", "赛博", "Switch", "PS5", "xbox"],
    "学习/教育": ["考试", "学习", "课程", "论文", "考研", "复习", "作业", "导师", "毕业", "学分", "绩点"],
    "社交/人际关系": ["朋友", "同学", "室友", "老师", "爸妈", "家里", "对象", "分手", "聚会", "喝酒"],
    "生活/日常": ["吃饭", "睡觉", "快递", "外卖", "医院", "看病", "健身", "跑步", "减肥", "做饭"],
    "消费/购物": ["买", "多少钱", "便宜", "贵", "淘宝", "京东", "拼多多", "薅羊毛", "链接"],
    "情绪/心理": ["烦", "累", "开心", "难过", "焦虑", "压力", "emo", "崩溃", "无语", "哈哈"],
    "职业/规划": ["工作", "实习", "面试", "简历", "工资", "加班", "跳槽", "老板", "同事", "行业"],
    "哲学/思想": ["意义", "人生", "命运", "自由", "死亡", "幸福", "存在", "价值", "选择"],
    "政治/社会": ["政府", "政策", "美国", "中国", "经济", "房价", "教育", "医疗", "法律"],
}

recent_content = " ".join([m["content"] for m in recent_msgs])
topic_coverage = {}
for topic, keywords in topic_keywords.items():
    score = 0
    matched = []
    for kw in keywords:
        count = recent_content.count(kw)
        if count > 0:
            score += count
            matched.append(kw)
    if score > 0:
        topic_coverage[topic] = {"score": score, "matched": matched}

# Obsidian 领域
obsidian_domain_names = {d for d in covered_domains if not d[0].isdigit()}
print("  Obsidian 覆盖:")
for d in sorted(obsidian_domain_names):
    print(f"    - {d}")

print("\n  微信对话中检测到的主题:")
for topic, info in sorted(topic_coverage.items(), key=lambda x: x[1]['score'], reverse=True):
    print(f"    - {topic} (匹配词: {', '.join(info['matched'][:5])})")

# ========== 5. 生成补充问卷 ==========
print("\n" + "=" * 60)
print("5. 知识盲区 → 补充问卷")
print("=" * 60)

# 常见人生领域，检查是否被覆盖
all_life_domains = [
    ("童年经历", ["小时候", "童年", "小学", "幼儿园", "儿时", "长大", "爸妈", "小时候"]),
    ("家庭关系", ["爸爸", "妈妈", "父母", "兄弟", "姐妹", "亲戚", "家庭", "家人"]),
    ("情感经历", ["恋爱", "前任", "喜欢", "暗恋", "分手", "在一起", "对象", "男女朋友"]),
    ("价值观/信念", ["我认为", "我觉得", "原则", "底线", "价值观", "信仰", "相信", "坚持"]),
    ("恐惧/弱点", ["害怕", "担心", "不敢", "恐惧", "弱点", "缺点", "短板"]),
    ("梦想/抱负", ["梦想", "目标", "理想", "想成为", "未来", "规划", "野心"]),
    ("金钱观", ["钱", "消费", "存钱", "理财", "投资", "穷", "富", "工资"]),
    ("健康/身体", ["身体", "健康", "生病", "医院", "锻炼", "跑步", "睡眠", "体检"]),
    ("审美/品味", ["好看", "丑", "风格", "穿搭", "音乐", "电影", "书", "艺术", "审美"]),
    ("社交偏好", ["社交", "朋友", "聚会", "独处", "内向", "外向", "社恐", "社牛"]),
    ("政治立场", ["政治", "政策", "政府", "自由", "民主", "体制", "左", "右"]),
    ("宗教/灵性", ["宗教", "神", "佛", "灵魂", "意义", "宇宙", "冥想"]),
    ("知识获取方式", ["读书", "看视频", "听课", "搜索引擎", "问人", "自学习惯"]),
    ("对AI的态度", ["AI", "人工智能", "ChatGPT", "机器人", "自动化", "取代"]),
    ("对人际冲突的处理", ["吵架", "矛盾", "冲突", "冷战", "和解", "道歉", "原谅"]),
]

# 合并所有已覆盖的文本进行匹配
all_covered_text = recent_content + " "
for f in obsidian_files:
    try:
        all_covered_text += f.get("title", "") + " "
    except:
        pass

questionnaire = []
for domain_name, keywords in all_life_domains:
    score = sum([all_covered_text.count(kw) for kw in keywords])
    if score < 5:  # 覆盖不足
        questionnaire.append({
            "领域": domain_name,
            "覆盖度": "低" if score == 0 else "中",
            "待补充问题": f"关于「{domain_name}」，你有什么想说的？（当前数据中几乎未涉及）"
        })

# 也从 Obsidian 领域反向检查
obsidian_covered_names = {d.lower() for d in covered_domains}
expected_knowledge = ["认知科学", "心理学", "经济学", "历史", "物理", "生物", "计算机", "文学", "哲学", "社会学"]
missing_knowledge = [k for k in expected_knowledge if k not in obsidian_covered_names and not any(k in d for d in obsidian_covered_names)]

for mk in missing_knowledge:
    questionnaire.append({
        "领域": mk,
        "覆盖度": "低",
        "待补充问题": f"你对「{mk}」有了解吗？有什么看法或想记录的内容？"
    })

print(f"\n  共计 {len(questionnaire)} 个补充问题:\n")
for i, q in enumerate(questionnaire, 1):
    print(f"  {i}. [{q['领域']}] ({q['覆盖度']}覆盖)")
    print(f"     {q['待补充问题']}\n")

# ========== 6. 输出汇总 ==========
print("=" * 60)
print("6. 输出文件")
print("=" * 60)

# 人格画像初稿
profile = {
    "generated_at": datetime.now().isoformat(),
    "data_sources": {
        "wechat_contacts": len(all_contacts),
        "wechat_recent_msgs": len(recent_msgs),
        "wechat_old_msgs": len(old_msgs),
        "obsidian_files": len(obsidian_files),
        "obsidian_domains": list(obsidian_domain_names),
    },
    "style_recent": recent_style,
    "style_old": old_style,
    "topic_coverage": {k: v["score"] for k, v in topic_coverage.items()},
    "covered_domains": list(covered_domains),
    "questionnaire": questionnaire,
}

profile_path = os.path.join(OUTPUT_DIR, "persona_profile.json")
with open(profile_path, 'w', encoding='utf-8') as f:
    json.dump(profile, f, ensure_ascii=False, indent=2)
print(f"  人格画像 → {profile_path}")

# 补充问卷 Markdown
q_path = os.path.join(OUTPUT_DIR, "questionnaire.md")
with open(q_path, 'w', encoding='utf-8') as f:
    f.write("# AI 分身补充问卷\n\n")
    f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    f.write("以下领域在当前数据（微信近两年 + Obsidian）中覆盖不足，请逐一回答以完善人格画像。\n\n")
    f.write("---\n\n")
    for i, q in enumerate(questionnaire, 1):
        f.write(f"## {i}. {q['领域']}（{q['覆盖度']}覆盖）\n\n")
        f.write(f"{q['待补充问题']}\n\n")
        f.write("> 你的回答：\n\n")
        f.write("---\n\n")
print(f"  补充问卷 → {q_path}")

print("\n完成！")
