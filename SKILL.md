---
name: fractovision
version: 1.2.0
description: "MiniMax全模态创作引擎。图片+视频+语音+音乐四合一生成。当需要AI生成图片、视频、语音、音乐或多媒体内容时使用。"
trigger:
  manual:
    - "@亦菲 生成图片"
    - "@亦菲 生成视频"
    - "@亦菲 生成语音"
    - "@亦菲 生成音乐"
    - "@亦菲 处理3D模型"
  note: "亦菲对外提供 MiniMax 多媒体能力的技能，所有外部调用统一走 fractovision_media.py"

triggers:
  - 多媒体生成
  - 图片生成
  - 视频生成
  - fractovision
  - 破窗造视
---

# fractovision

> 📖 详细文档见 `references/` 目录

> 破窗造视 · Fractovision统一封装 — 图片、视频、语音、音乐、3D模型，一套接口全部搞定。
> 新增 Wan2.1 视频后端（文生视频 / 图生视频 / 首尾帧插值）+ 统一分辨率路由 + 3D模型处理。

## 核心封装

**`~/.hermes/scripts_lib/fractovision_media.py`** — 唯一入口，所有能力归口。
**`~/.hermes/scripts_lib/wan_video.py`** — Wan2.1 视频后端。
**`~/.hermes/scripts_lib/video_router.py`** — 统一视频路由。
**`modules/model_3d_processor.py`** — 3D模型处理（NEW）。

## 能力总览

| 能力 | 模型 | 状态 | 飞书气泡 |
|------|------|------|---------|
| 图片生成 | image-01 / image-01-pro | ✅ 可用 | ❌ 只能发图片 |
| 视频生成 | Video-01 (Hailuo) | ✅ 可用 | ❌ 只能发视频 |
| 视频生成 (Wan2.1) | wan2.1-t2v / i2v / flf2v | ✅ 可用 | ❌ 只能发视频 |
| 语音合成 | speech-2.8-hd | ✅ 可用 | ✅ 支持 .ogg |
| 音乐生成 | music-02 | ✅ 可用 | ❌ 只能发音频 |
| 3D模型处理 | GLB/GLTF | ✅ 可用 | ❌ 只能发文件 |

## 视频后端对比

| 特性 | MiniMax Hailuo | Wan2.1 (DashScope) |
|------|---------------|---------------------|
| 文生视频 | ✅ | ✅ |
| 图生视频 (I2V) | ❌ | ✅ |
| 首尾帧插值 (FLF2V) | ❌ | ✅ |
| 分辨率 | 544P / 768P / 1080P | 480P / 720P / 1080P |
| 时长 | 3s / 6s / 10s | 5s / 10s |
| 风格预设 | ❌ | ✅ cinematic / anime / realistic 等7种 |
| API Key | MINIMAX_API_KEY | DASHSCOPE_API_KEY |

## 3D模型处理 (NEW)

融合自 ComfyUI v0.25.1 的3D模型处理能力。

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

## 工作流

使用此技能时，按以下步骤执行：
- [ ] 1. 确认用户需求和使用场景
- [ ] 2. 加载相关代码和配置
- [ ] 3. 执行核心功能
- [ ] 4. 验证输出结果
- [ ] 5. 反馈给用户
