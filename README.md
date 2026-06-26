# AI 分身 - Phase 1 基础架子

## 访问方式

| 项目 | 值 |
|------|-----|
| **公开 URL** | https://birmingham-driving-johnston-tones.trycloudflare.com |
| **QR 码** | `ai-clone-qr.png` |
| **本地地址** | http://localhost:3000 |

## 架构

```
用户浏览器 → Cloudflare Edge → cloudflared tunnel → Open WebUI (3000) → Ollama (11434)
```

## 启动/停止命令

### 启动
```powershell
# 1. Ollama (通常已自启动，确认)
ollama list

# 2. Open WebUI
open-webui serve --host 127.0.0.1 --port 3000

# 3. cloudflared tunnel
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:3000
```

### 停止
```powershell
# Ctrl+C 停止 Open WebUI 和 cloudflared
# Ollama 通常不需要停止
```

## 模型

| 模型 | 大小 | 用途 |
|------|------|------|
| qwen2.5:7b | 4.7 GB | 推理/对话 |
| bge-m3:latest | 1.2 GB | 向量嵌入 |

## 端口

| 端口 | 服务 | 公网暴露 |
|------|------|----------|
| 11434 | Ollama API | ❌ 仅 127.0.0.1 |
| 3000 | Open WebUI | ✅ 通过 cloudflared |
| 20241 | cloudflared metrics | ❌ 仅 127.0.0.1 |

## 首次使用

1. 打开 http://localhost:3000
2. 创建管理员账户（第一个注册用户自动成为管理员）
3. 在 Admin Panel → Settings → Users 中关闭 "Allow User Registration"
4. 选择模型 `qwen2.5:7b` 开始对话

## 注意事项

- trycloudflare URL 是临时的，重启后 URL 会变化
- 正式使用建议注册 Cloudflare 账号创建固定 tunnel + 自有域名
- 当前 CORS 设置为 `*`，正式使用需限制
