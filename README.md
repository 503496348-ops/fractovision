# 破窗造视 · Fractovision

> 图片、视频、语音、音乐 — 四大 AI 创作能力，一套接口全部搞定。

Fractovision 基于 [MiniMax](https://platform.minimaxi.com/) API，将图片生成、视频生成、语音合成、音乐生成统一封装为简洁的 Python 函数。支持飞书语音气泡直出、批量管线处理，适用于自动化工作流和 Hermes Agent 技能集成。

---

## 能力总览

| 能力 | 模型 | 调用函数 | 同步/异步 | 飞书气泡 |
|------|------|----------|-----------|----------|
| 🖼️ 图片生成 | image-01 / image-01-pro | `generate_image()` | 同步 | ❌ 图片消息 |
| 🎬 视频生成 | MiniMax-Hailuo-2.3 / Video-01 | `generate_video()` | 异步轮询 | ❌ 视频消息 |
| 🗣️ 语音合成 | speech-2.8-hd | `generate_speech()` | 同步 | ✅ `.ogg` 气泡 |
| 🎵 音乐生成 | music-2.6 | `generate_music()` | 异步轮询 | ❌ 音频附件 |

---

## 快速开始

### 第 1 步：克隆仓库

```bash
git clone https://github.com/503496348-ops/fractovision.git \
  ~/.hermes/skills/fractovision
```

### 第 2 步：配置 API Key

```bash
# 方式一：环境变量
export MINIMAX_API_KEY="your_api_key_here"

# 方式二：写入 .env 文件
echo 'MINIMAX_API_KEY=your_api_key_here' >> ~/.hermes/.env
```

### 第 3 步：生成第一张图片

```python
from scripts.minimax_media import generate_image

result, err = generate_image(
    prompt="一杯手冲咖啡放在木桌上，阳光从窗户洒进来",
    size="16:9",        # 1:1 / 16:9 / 9:16 / 3:4 / 4:3
    model="image-01",   # 或 image-01-pro
)
print(result)  # data:image/png;base64,...
```

### 第 4 步：生成视频

```python
from scripts.minimax_media import generate_video

video_path, err = generate_video(
    prompt="一只橘猫在窗台上晒太阳，慵懒地伸了个懒腰",
    model="MiniMax-Hailuo-2.3",
    duration=6,
    resolution="768P",
)
print(video_path)  # ~/Desktop/hailuo_video_20260619_120000.mp4
```

### 第 5 步：语音合成

```python
from scripts.minimax_media import generate_speech

# 标准 MP3 输出
audio_bytes, err = generate_speech(
    text="锋哥，今天的晨报来了。",
    voice_id="female-tianmei",
    emotion="happy",
)

# 飞书语音气泡输出
ogg_path, err = generate_speech(
    text="锋哥，今天的晨报来了。",
    to_feishu_ogg=True,   # 转码为 .ogg (Opus)
)
# MEDIA:/tmp/xxx_feishu.ogg → 飞书显示为语音气泡 🎵
```

---

## API 参考

### 图片生成 `generate_image()`

```python
generate_image(
    prompt: str,              # 图片描述（必填）
    size: str = "1:1",       # 尺寸比例：1:1 / 16:9 / 9:16 / 3:4 / 小红书 / 海报
    model: str = "image-01", # 模型名
) -> tuple[data_url | None, error | None]
```

支持的尺寸别名：`"小红书"` → 3:4，`"海报"` → 2:3，`"手机壁纸"` → 9:16，`"电影感"` → 21:9。

### 视频生成 `generate_video()`

```python
generate_video(
    prompt: str,                       # 视频描述（必填）
    model: str = "MiniMax-Hailuo-2.3", # 模型
    duration: int = 6,                 # 时长（秒）：6 / 10
    resolution: str = "768P",          # 分辨率：544P / 768P / 1080P（大写 P）
    poll_interval: int = 5,            # 轮询间隔
    output_dir: str = None,            # 输出目录，默认 ~/Desktop
) -> tuple[file_path | None, error | None]
```

### 语音合成 `generate_speech()`

```python
generate_speech(
    text: str,                        # 合成文本（必填）
    voice_id: str = "female-tianmei", # 音色 ID
    speed: float = 1.0,               # 语速
    emotion: str = "neutral",         # 情感：happy / neutral / sad / angry / anxious
    model: str = "speech-2.8-hd",     # 模型
    to_feishu_ogg: bool = False,      # True → 转码为飞书语音气泡 .ogg
) -> tuple[bytes | file_path | None, error | None]
```

### 音乐生成 `generate_music()`

```python
generate_music(
    prompt: str,                     # 音乐风格描述（必填）
    lyrics: str = "",               # 歌词（纯器乐可不填）
    is_instrumental: bool = True,   # True=纯器乐
    model: str = "music-2.6",       # 模型
    duration: int = 60,             # 时长：30 / 60 / 120 / 180 秒
    output_dir: str = None,         # 输出目录
) -> tuple[file_path | None, error | None]
```

---

## 文件结构

```
fractovision/
├── README.md                  # 本文件 — 项目总览
├── SKILL.md                   # 技能详细文档（能力说明、技术细节、踩坑记录）
├── MANIFEST.yaml              # 技能包清单（脚本、依赖、清理策略）
├── LICENSE                    # MIT 许可证
├── requirements.txt           # Python 依赖（requests）
└── scripts/
    ├── minimax_media.py       # 核心封装 — 图片/视频/语音/音乐四合一入口
    └── media_pipeline.py      # 批量管线 — MediaBatch 多任务编排
```

---

## 依赖安装

```bash
# Python 依赖
pip install requests

# 系统依赖（语音气泡转码需要 ffmpeg + libopus）
sudo apt install ffmpeg
ffmpeg -formats | grep opus  # 验证 libopus 可用
```

---

## 飞书语音气泡说明

飞书客户端根据 MIME type 判断消息类型：

| 格式 | 飞书表现 |
|------|----------|
| `.mp3` / `.m4a` / `.aac` | 📎 文件附件 |
| `.ogg`（Opus 编码） | 🎵 语音气泡 |

使用 `generate_speech(to_feishu_ogg=True)` 自动完成 MP3 → OGG 转码，无需手动调用 ffmpeg。

> **提示**：晨报、日报等需要文字存档的内容建议用卡片发送。语音气泡适合临时通知、信息推送等不需要留档的场景。

---

## 常见问题（FAQ）

**Q: API Key 在哪里获取？**
A: 前往 [MiniMax 开放平台](https://platform.minimaxi.com/) 注册并创建 API Key。

**Q: 视频生成很慢怎么办？**
A: 视频生成为异步流程（创建任务 → 轮询状态 → 下载），通常需要 1-3 分钟。可通过 `poll_interval` 调整轮询频率，`poll_timeout` 调整超时时间。

**Q: 报错 `MINIMAX_API_KEY 未设置` 怎么解决？**
A: 函数按以下顺序查找 Key：① 环境变量 `MINIMAX_API_KEY` → ② `~/.hermes/.env` → ③ `~/.hermes/hermes-agent/.env`。确认任一位置已配置即可。

**Q: 分辨率参数为什么用 `768P` 而不是 `768p`？**
A: MiniMax API 要求大写 P（`544P` / `768P` / `1080P`），小写会报错。

**Q: 图片尺寸参数怎么填？**
A: 使用比例字符串（`"1:1"` / `"16:9"` / `"9:16"`），也支持中文别名（`"小红书"` / `"海报"` / `"手机壁纸"`）。不要用 `"720p"` 之类的分辨率字符串。

**Q: 如何验证凭证是否有效？**
A: 运行以下代码：
```python
from scripts.minimax_media import get_config
cfg = get_config()
print("API Key:", cfg["api_key"][:8] + "..." if cfg["api_key"] else "❌ 未配置")
```

---

## 许可证

[MIT](./LICENSE)
