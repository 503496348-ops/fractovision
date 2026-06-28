# 破窗造视 · Fractovision

> 图片、视频、语音、音乐 — 四大 AI 创作能力，一套接口全部搞定。
> 新增 **Wan2.1 视频后端**（文生视频 / 图生视频 / 首尾帧插值）+ 统一分辨率路由。

Fractovision 基于 [MiniMax](https://platform.minimaxi.com/) API + [Wan2.1](https://github.com/Wan-Video/Wan2.1)（阿里 DashScope），将图片生成、视频生成、语音合成、音乐生成统一封装为简洁的 Python 函数。支持飞书语音气泡直出、多后端视频路由、批量管线处理，适用于自动化工作流和 Hermes Agent 技能集成。

---

## 能力总览

| 能力 | 模型 | 调用函数 | 同步/异步 | 飞书气泡 |
|------|------|----------|-----------|----------|
| 🖼️ 图片生成 | image-01 / image-01-pro | `generate_image()` | 同步 | ❌ 图片消息 |
| 🎬 视频生成 | MiniMax-Hailuo-2.3 / Video-01 | `generate_video()` | 异步轮询 | ❌ 视频消息 |
| 🎬 视频生成 (Wan2.1) | wan2.1-t2v / i2v / flf2v | `generate_video_wan()` | 异步轮询 | ❌ 视频消息 |
| 🗣️ 语音合成 | speech-2.8-hd | `generate_speech()` | 同步 | ✅ `.ogg` 气泡 |
| 🎵 音乐生成 | music-2.6 | `generate_music()` | 异步轮询 | ❌ 音频附件 |

---

## 🎬 视频后端对比

| 特性 | MiniMax Hailuo | Wan2.1 (DashScope) |
|------|---------------|---------------------|
| 文生视频 (T2V) | ✅ | ✅ |
| 图生视频 (I2V) | ❌ | ✅ |
| 首尾帧插值 (FLF2V) | ❌ | ✅ |
| 分辨率 | 544P / 768P / 1080P | 480P / 720P / 1080P |
| 时长 | 3s / 6s / 10s | 5s / 10s |
| 风格预设 | ❌ | ✅ cinematic / anime / realistic / ... |
| 提示词增强 | ❌ | ✅ 运动/镜头语言优化 |
| API Key | `MINIMAX_API_KEY` | `DASHSCOPE_API_KEY` |

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
### 第 4 步：生成视频
```python
from scripts.minimax_media import generate_video

video_path, err = generate_video(
    prompt="一只橘猫在窗台上晒太阳，慵懒地伸了个懒腰",
    model="MiniMax-Hailuo-2.3",
    duration=6,
    resolution="768P",
)
print(video_path)
```

### 第 4b 步：用 Wan2.1 生成视频

```python
from scripts.wan_video import generate_video_wan

# 文生视频
video_path, err = generate_video_wan(
    prompt="一只橘猫在窗台上晒太阳，慵懒地伸了个懒腰",
    model="wan2.1-t2v-plus",
    duration=5,
    resolution="720P",
    style="cinematic",     # 风格预设
)

# 图生视频（Wan2.1 独有）
from scripts.wan_video import generate_video_wan_i2v
video_path, err = generate_video_wan_i2v(
    image_url="https://example.com/cat.jpg",
    prompt="猫伸懒腰",
    resolution="720P",
)

# 统一路由（自动选择后端）
from scripts.video_router import generate_video
video_path, err = generate_video(
    prompt="日落延时摄影",
    model="wan2.1-t2v-plus",   # 自动路由到 Wan2.1
    resolution="480P",
    style="nature",
)
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

### 视频生成 (Wan2.1) `generate_video_wan()`

```python
generate_video_wan(
    prompt: str,                         # 视频描述（必填）
    model: str = "wan2.1-t2v-plus",     # 模型（t2v-plus / t2v-turbo）
    duration: int = 5,                   # 时长：5 / 10 秒
    resolution: str = "720P",           # 分辨率：480P / 720P / 1080P
    orientation: str = "landscape",      # landscape / portrait
    style: str = None,                   # 风格预设：cinematic/anime/realistic/...
    motion: str = None,                  # 镜头运动描述
    negative: str = None,               # 负面提示词
    output_dir: str = None,
) -> tuple[file_path | None, error | None]
```

### 图生视频 (Wan2.1) `generate_video_wan_i2v()`

```python
generate_video_wan_i2v(
    image_url: str,                      # 图片 URL（必填）
    prompt: str = "",                    # 运动描述
    model: str = "wan2.1-i2v-plus",     # 模型
    duration: int = 5,
    resolution: str = "720P",
    orientation: str = "landscape",
) -> tuple[file_path | None, error | None]
```

### 首尾帧插值 (Wan2.1) `generate_video_wan_flf2v()`

```python
generate_video_wan_flf2v(
    first_frame_url: str,               # 首帧图片 URL
    last_frame_url: str,                # 尾帧图片 URL
    prompt: str = "",                   # 可选描述
    duration: int = 5,
    resolution: str = "720P",
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
    ├── minimax_media.py       # 核心封装 — MiniMax 图片/视频/语音/音乐四合一
    ├── media_pipeline.py      # 批量管线 — MediaBatch 多任务编排
    ├── wan_video.py           # Wan2.1 后端 — 文生视频/图生视频/首尾帧插值
    └── video_router.py        # 统一路由 — MiniMax + Wan2.1 多后端选择
```

---

## 依赖安装

```bash
# Python 依赖
pip install requests  # 核心依赖

# Wan2.1 后端（可选，需要阿里云 DashScope API Key）
export DASHSCOPE_API_KEY="your_dashscope_key"

# 系统依赖（语音气泡转码需要 ffmpeg + libopus）
sudo apt install ffmpeg
ffmpeg -formats | grep opus  # 验证 libopus 可用
```

---

## API Key 配置

| 后端 | 环境变量 | 获取地址 |
|------|----------|----------|
| MiniMax | `MINIMAX_API_KEY` | [MiniMax 开放平台](https://platform.minimaxi.com/) |
| Wan2.1 | `DASHSCOPE_API_KEY` | [阿里云 DashScope](https://dashscope.console.aliyun.com/) |

两个 Key 可以同时配置，系统会根据模型名自动路由到对应后端。

---

## Wan2.1 风格预设

| 预设名 | 效果 |
--------|------|
| `cinematic` | 电影感，胶片颗粒，戏剧性光线 |
| `anime` | 动画风格，鲜艳色彩，吉卜力美学 |
| `realistic` | 照片级真实，高细节，自然光线 |
| `documentary` | 纪录片风格，自然运动，手持感 |
| `music-video` | MV风格，霓虹色彩，动态剪辑 |
| `product` | 产品展示，影棚灯光，干净背景 |
| `nature` | 自然纪录片，黄金时刻，缓慢优雅运动 |

使用示例：
```python
from scripts.wan_video import generate_video_wan
video_path, err = generate_video_wan(
    prompt="一朵玫瑰花缓缓绽放",
    style="cinematic",
    motion="slow dolly zoom in",
    resolution="720P",
)
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

## 🧊 3D模型处理 (NEW)


**处理能力**:
- GLB格式保存
- 网格打包/切片
- 顶点颜色/UV支持
- 纹理嵌入

```python
from modules.model_3d_processor import Model3DProcessor
import numpy as np

processor = Model3DProcessor()

# 准备数据
vertices = np.array([
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
], dtype=np.float32)

faces = np.array([
    [0, 1, 2],
    [0, 1, 3],
    [0, 2, 3],
    [1, 2, 3],
], dtype=np.int64)

# 保存GLB
result = processor.save_glb(
    vertices, faces, "output.glb",
    metadata={"name": "test_cube"},
)

# 加载GLB
load_result = processor.load_glb("output.glb")
if load_result.mesh_data:
    print(f"顶点数: {len(load_result.mesh_data.vertices)}")
    print(f"面数: {len(load_result.mesh_data.faces)}")
```

**支持格式**:
- GLB (二进制glTF)
- GLTF (JSON glTF)
- OBJ (Wavefront)
- FBX (Autodesk)
