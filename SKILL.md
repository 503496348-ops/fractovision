---
name: fractovision
version: 1.5.0
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

## 核心能力

- **图片生成**：image-01 / image-01-pro 模型，支持多种风格
- **视频生成**：MiniMax Hailuo + Wan2.1 双后端，支持文生视频/图生视频/首尾帧插值
- **语音合成**：speech-2.8-hd，支持飞书 .ogg 气泡
- **音乐生成**：music-02 模型
- **3D模型处理**：GLB/GLTF/OBJ/FBX 格式加载与导出
- **统一路由**：fractovision_media.py 单一入口，自动分发到对应后端

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

## ComfyUI 本地生成 (NEW)

新增 ComfyUI 本地 GPU 加速生成能力，无需 API Key，支持自定义工作流。

### 核心引擎模块

| 模块 | 功能 | 能力 |
|------|------|------|
| `vram_manager.py` | VRAM 管理 | 智能显存分配、模型卸载到CPU、VRAM估算、soft_lock防并发 |
| `dag_executor.py` | DAG 执行引擎 | 拓扑排序、dirty标记部分重执行、缓存哈希、循环检测 |
| `workflow_queue.py` | 工作流队列 | ComfyUI标准workflow JSON解析、执行队列、事件通知 |
| `conditioning_composer.py` | 条件组合管线 | ControlNet注入、LoRA堆叠/合并、IP-Adapter |
| `node_registry.py` | 节点注册系统 | 节点分类、类型转换链、输入验证器 |

### 视频生成

```python
from modules.comfyui_engine.comfyui_video import ComfyUIVideo

tool = ComfyUIVideo()
result = tool.execute({
    "prompt": "A cat walking in the rain",
    "operation": "text_to_video",
    "width": 512,
    "height": 512,
    "num_frames": 16,
    "fps": 8,
})

if result.success:
    print(f"视频生成成功: {result.artifacts}")
```

### 图片生成

```python
from modules.comfyui_engine.comfyui_image import ComfyUIImage

tool = ComfyUIImage()
result = tool.execute({
    "prompt": "A beautiful sunset over the ocean",
    "operation": "text_to_image",
    "width": 1024,
    "height": 1024,
    "steps": 20,
    "cfg_scale": 7.0,
})

if result.success:
    print(f"图片生成成功: {result.artifacts}")
```

### 支持的操作

| 操作 | 说明 | 需要参数 |
|------|------|---------|
| text_to_video | 文生视频 | prompt |
| image_to_video | 图生视频 | prompt, image_path |
| text_to_image | 文生图片 | prompt |
| image_to_image | 图片转换 | prompt, image_path |
| inpainting | 局部重绘 | prompt, image_path, mask_path |
| workflow_video | 自定义工作流 | workflow_path |
| workflow_image | 自定义工作流 | workflow_path |

### 系统要求

- NVIDIA GPU (6GB+ VRAM 推荐)
- PyTorch + CUDA
- ComfyUI 已安装

### 优势

- **无 API Key**：本地运行，无需网络
- **隐私保护**：数据不出本地
- **自定义工作流**：支持任意 ComfyUI 节点组合
- **批量生成**：支持 batch_size 参数

## 3D模型处理 (NEW)


- VRAM Manager 支持 `dtype="int8"` 加载模型，显存占用减半
- 适用于 LOW_VRAM / NO_VRAM 状态下的大模型推理
- INT8 tensor-wise 量化，质量损失极小（<1%）

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
## 2026-07-02 融合增强

- 破窗造视新增幻灯片级图片生成提示词包：强制真实可见文字、配色完整性、版式节奏与 manifest 证据。


## 2026-07-03 运行时增强

- 新增模型管线加载守卫：识别 flat/nested 仓库布局，并在注意力后端不兼容时要求 fallback。
- 验证：新增模块通过 py_compile 和定向 pytest，代码不依赖外部服务。
