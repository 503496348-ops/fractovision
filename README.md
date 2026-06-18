# fractovision

破窗造视 · Fractovision — 图片、视频、语音、音乐四大能力统一封装，支持飞书语音气泡直出。

## 快速开始

```bash
# 克隆到本地 Hermes skills 目录
git clone https://github.com/503496348-ops/fractovision.git \
  ~/.hermes/skills/fractovision
```

## 能力一览

| 能力 | 模型 | 调用方式 |
|------|------|---------|
| 图片生成 | image-01 / image-01-pro | `generate_image(prompt)` |
| 视频生成 | Video-01 (Hailuo) | `generate_video(prompt)` |
| 语音合成 | speech-2.8-hd | `generate_speech(text)` |
| 音乐生成 | music-02 | `generate_music(prompt)` |

详细文档见 [SKILL.md](./SKILL.md)。

## 依赖

- Python 3.10+
- `requests`
- `ffmpeg`（含 libopus 支持，用于飞书语音气泡转码）

## License

MIT
