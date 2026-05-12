---
name: minimax-creative
description: "MiniMax 多媒体创作能力 — 图片(image-01)、视频(Video-01/Hailuo)、语音(TTS)、音乐(Music-02) 四大能力的统一封装，支持飞书语音气泡直出"
trigger:
  manual:
    - "@亦菲 生成图片"
    - "@亦菲 生成视频"
    - "@亦菲 生成语音"
    - "@亦菲 生成音乐"
  note: "亦菲对外提供 MiniMax 多媒体能力的技能，所有外部调用统一走 minimax_media.py"
---

# minimax-creative

> MiniMax 多媒体创作能力统一封装 — 图片、视频、语音、音乐，一套接口全部搞定。

## 核心封装

**`scripts/minimax_media.py`** — 唯一入口，所有能力归口。

## 能力总览

| 能力 | 模型 | 状态 | 飞书气泡 |
|------|------|------|---------|
| 图片生成 | image-01 / image-01-pro | ✅ 可用 | ❌ 只能发图片 |
| 视频生成 | Video-01 (Hailuo) | ✅ 可用 | ❌ 只能发视频 |
| 语音合成 | speech-2.8-hd | ✅ 可用 | ✅ 支持 .ogg |
| 音乐生成 | music-02 | ✅ 可用 | ❌ 只能发音频 |

---

## 图片生成

```python
from minimax_media import generate_image

result, err = generate_image(
    prompt="一杯手冲咖啡放在木桌上，阳光从窗户洒进来",
    model="image-01",       # 或 "image-01-pro"
    resolution="1536P",      # 1K/1536P/2K（注意大写P）
)
# result: {"image_url": "https://..."} 或 {"image_bytes": b"..."}
```

**分辨率说明**：不是 `"720p"` 不是 `"1080p"`，是 `"1536P"` / `"2K"`（大写 P）。

---

## 视频生成

```python
from minimax_media import generate_video

task_id, err = generate_video(
    prompt="a cup of coffee on a wooden table",
    model="video-01",        # 可选 video-01 / video-01-pro
    duration=6,              # 3/6 秒
    resolution="768P",       # 768P / 1080P（大写P）
    poll_interval=5,        # 轮询间隔（秒）
)
# 返回 task_id，函数内部自动轮询直至完成并下载
# 最终文件保存在: ~/.hermes/cron/output/hailuo_{task_id}.mp4
```

**异步流程**：创建任务 → 轮询状态 → 下载视频 → 返回本地路径。

---

## 语音合成

### 标准 MP3 用法

```python
from minimax_media import generate_speech

audio_bytes, err = generate_speech(
    text="锋哥，今天的晨报来了。今天重点推进和君纵达的数据对接。",
    voice_id="female-tianmei",  # 音色 ID
    speed=1.0,
    emotion="happy",            # happy / neutral / sad / angry / anxious
)
```

### 飞书语音气泡用法 ⚠️

飞书群聊中，MP3 会被当作**文件附件**，不会显示为语音气泡。

**解决方案**：转码为 `.ogg`（Opus），飞书才会识别为语音气泡。

```python
ogg_path, err = generate_speech(
    text="锋哥，今天的晨报来了。",
    voice_id="female-tianmei",
    to_feishu_ogg=True,        # ← 关键参数，返回 .ogg 路径
)
# 返回: "/tmp/xxx_feishu.ogg"
# 发送: MEDIA:/tmp/xxx_feishu.ogg → 飞书显示为 🎵 语音气泡
```

**参数**：`to_feishu_ogg=True` 时，返回值为 `.ogg` 文件路径，不是 MP3 bytes。

**注意**：晨报/日报等需要文字存档的工作记录，建议只发**卡片**，不发语音气泡。语音气泡适合的场景：临时通知、信息推送，不需要留档的内容。

---

## 音乐生成

```python
from minimax_media import generate_music

result, err = generate_music(
    prompt="relaxing ambient music, soft piano, nature sounds",
    lyrics=None,               # 纯器乐时可不填
    is_instrumental=True,      # True=纯器乐，False=需要 lyrics
    duration=60,               # 30/60/120/180 秒
)
# 返回: {"music_url": "https://..."} 或 {"music_bytes": b"..."}
```

---

## API 凭证配置

### 自动读取

`minimax_media.py` 会按以下顺序查找 `MINIMAX_API_KEY`：

```python
# 1. 环境变量
os.environ.get("MINIMAX_API_KEY")
# 2. ~/.hermes/.env
# 3. ~/.hermes/hermes-agent/.env
```

### 手动注入（cron job 中）

```python
import os
os.environ["MINIMAX_API_KEY"] = "your_key_here"
```

### 验证凭证是否有效

```python
from minimax_media import get_config
cfg = get_config()
print(cfg["api_key"])  # 确认能读到
```

---

## 飞书语音气泡技术细节

### 为什么是 .ogg 而不是 .mp3？

飞书客户端根据 **MIME type + 文件扩展名** 判断消息类型：
- `.mp3` / `.m4a` / `.aac` → 文件附件
- `.ogg`（Opus codec）→ 语音气泡 🎵

### 转码命令

```bash
ffmpeg -i input.mp3 -vn -c:a libopus -b:a 128k output.ogg
```

**关键参数**：
- `-c:a libopus`：使用 Opus 编码器（不是 opus 也不是其他）
- `-vn`：去掉视频轨道
- `-b:a 128k`：码率 128kbps

### 验证是否为 Opus

```bash
ffprobe -show_streams output.ogg | grep codec_name
# 输出 codec_name = opus 即为正确格式
```

---

## 已知技术教训

| 时间 | 教训 | 修复 |
|------|------|------|
| 2026-05-13 | 视频 API 分辨率参数 | Video-01 模型只接受 544P/720P/1080P（大写P），768P 仅用于旧版 Hailuo 端点 |
| 2026-05-13 | 远程服务器 API Key 不在环境变量中 | lusi 服务器的 key 由 hermes-agent 进程管理，审计时验证"功能是否正常"而非"key 在哪里" |
| 2026-05-13 | lusi 服务器的 MiniMax MCP 是系统 pip 包 | `python3 -c "import minimax_mcp"` 即可确认，无需额外配置 |
| 2026-05-12 | 语音端点 `/v1/t2a` 返回 404 | 正确端点为 `/v1/t2a_v2` |
| 2026-05-12 | 语音 API 字段名是 `vol` 不是 `volume`，`emotion` 不可省略 | 修正请求体 |
| 2026-05-12 | TTS API 返回 JSON `{data: {audio: "hex..."}}`，不是原始二进制 | 先解析 JSON 再提取 hex |
| 2026-05-12 | MiniMax 视频任务创建和查询分离 | 创建用 POST /v1/video_generation，查状态用 GET /v1/query/video_generation?task_id= |
| 2026-05-12 | 飞书群聊发 MP3 显示为文件不是气泡 | MP3 → ffmpeg 转码为 .ogg（libopus）→ MEDIA: 发送 |
| 2026-05-12 | 晨报/日报是工作记录，应该用卡片存档 | 语音气泡适合临时推送，不需要留档的内容 |
| 2026-05-13 | 向露丝部署前必须Spec-First确认方案，未确认直接执行违反工程纪律SOP | 会触发锋哥追问，验收时补交检查清单 |

---

## 依赖检查

```bash
# 确认 ffmpeg 支持 libopus
ffmpeg -formats | grep opus

# 确认 Python 依赖
python3 -c "import requests; print('requests ok')"
```

## 跨Agent部署：向露丝服务器部署

**⚠️ 部署约束**：向露丝服务器部署本能力相关文件时，必须先输出设计方案给锋哥确认，违反者会被锋哥追问"是否遵守工程纪律和PRD"。

部署执行记录（2026-05-13 已完成）：
- 脚本：`/home/agentuser/scripts_lib/minimax_media.py` ✅
- Skill：`/home/agentuser/skills/minimax-creative/SKILL.md` ✅

---

## 快速验证

```python
# 语音气泡验证（完整链路）
from minimax_media import generate_speech
ogg_path, err = generate_speech("测试语音气泡", to_feishu_ogg=True)
print(ogg_path)  # /tmp/xxx_feishu.ogg
# 用 send_message 发送: MEDIA:ogg_path

# 图片验证
from minimax_media import generate_image
result, err = generate_image("一只橘猫在窗台上晒太阳")
print(result.get("image_url"))

# 视频验证
from minimax_media import generate_video
path, err = generate_video("一只橘猫在窗台上晒太阳")
print(path)  # ~/.hermes/cron/output/hailuo_xxx.mp4
```
