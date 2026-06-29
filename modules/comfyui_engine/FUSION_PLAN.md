# ComfyUI × OpenMontage 融合方案

## 目标
将破窗造视的 ComfyUI 引擎能力接入 OpenMontage 的 BaseTool 生态，实现：
- ComfyUI 视频生成 → OpenMontage 流水线
- ComfyUI 图片生成 → OpenMontage 流水线
- 统一的 ToolResult 返回格式

## 架构设计

```
OpenMontage Pipeline
    ↓ (BaseTool.execute)
comfyui_video.py / comfyui_image.py (适配层)
    ↓ (调用)
Fractovision ComfyUI Engine
    ├── dag_executor.py (DAG 执行)
    ├── node_registry.py (节点注册)
    ├── vram_manager.py (VRAM 管理)
    └── conditioning_composer.py (条件组合)
```

## 新增文件

### 1. `comfyui_video.py` (OpenMontage tools/video/)
- 继承 `BaseTool`
- 实现 `execute()` → 调用 Fractovision DAG 执行器
- 支持：text_to_video, image_to_video
- 返回 `ToolResult` 格式

### 2. `comfyui_image.py` (OpenMontage tools/video/)
- 继承 `BaseTool`
- 实现 `execute()` → 调用 Fractovision 节点注册器
- 支持：text_to_image, image_to_image
- 返回 `ToolResult` 格式

## 对接点

| OpenMontage 接口 | Fractovision 对应 |
|-----------------|------------------|
| `BaseTool.execute(inputs)` | `DAGExecutor.execute(workflow)` |
| `ToolResult.artifacts` | 输出文件路径列表 |
| `ToolResult.cost_usd` | cost_tracker 计算 |
| `ToolResult.duration_seconds` | 执行耗时 |
| `input_schema` | NodeDefinition.inputs |

## 融合增量

| 能力 | 破窗造视现有 | OpenMontage 增强 |
|------|-------------|-----------------|
| 视频后端 | Hailuo + Wan2.1 | +Kling, Runway, Veo, CogVideo, Seedance |
| 图片后端 | MiniMax image-01 | +DALL-E, Midjourney, SDXL, Flux |
| 工作流 | 单步生成 | 12条完整流水线 |
| 成本控制 | 无 | cost_tracker 每步报价 |
| 质量自审 | 无 | ffprobe/帧采样/音量分析 |
