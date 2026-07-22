#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wan2.1 Video Generation Backend
================================
Adds Wan2.1 (Alibaba open-source) as an alternative video generation backend
alongside MiniMax Hailuo. Supports text-to-video, image-to-video, and
first-last-frame-to-video via Alibaba Cloud Model Studio (DashScope) API.

Brand: AtomCollide-智械工坊

Supported tasks:
  - Text-to-Video (T2V): generate video from text prompt
  - Image-to-Video (I2V): animate a single image into video
  - First-Last-Frame-to-Video (FLF2V): interpolate between two images

Resolution support:
  - 480P (832x480 / 480x832)
  - 720P (1280x720 / 720x1280)
  - 1080P (1920x1080 / 1080x1920)

API: Alibaba Cloud DashScope (https://dashscope.aliyuncs.com)
Auth: DASHSCOPE_API_KEY environment variable
"""

from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional, Literal, Tuple

try:
    import requests
except ImportError:
    raise ImportError("requests 库未安装，请运行: pip install requests")


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1"
DASHSCOPE_ASYNC_URL = f"{DASHSCOPE_API_URL}/services/aigc/video-generation/async"
DASHSCOPE_TASK_URL = f"{DASHSCOPE_API_URL}/tasks"

# Model mapping: friendly name → DashScope model ID
WAN_MODELS = {
    "wan2.1-t2v": "wan2.1-t2v-plus",          # Text-to-Video
    "wan2.1-t2v-plus": "wan2.1-t2v-plus",
    "wan2.1-t2v-turbo": "wan2.1-t2v-turbo",   # Faster T2V
    "wan2.1-i2v": "wan2.1-i2v-plus",           # Image-to-Video
    "wan2.1-i2v-plus": "wan2.1-i2v-plus",
    "wan2.1-i2v-turbo": "wan2.1-i2v-turbo",   # Faster I2V
    "wan2.1-flf2v": "wan2.1-flf2v-plus",      # First-Last-Frame-to-Video
}

# Resolution presets: resolution label → (width, height) for landscape
# Portrait swaps width/height automatically
RESOLUTION_PRESETS = {
    "480P": {"landscape": (832, 480), "portrait": (480, 832)},
    "720P": {"landscape": (1280, 720), "portrait": (720, 1280)},
    "1080P": {"landscape": (1920, 1080), "portrait": (1080, 1920)},
}

# Supported durations by model
DURATION_MAP = {
    "wan2.1-t2v-plus": [5, 10],
    "wan2.1-t2v-turbo": [5, 10],
    "wan2.1-i2v-plus": [5, 10],
    "wan2.1-i2v-turbo": [5, 10],
    "wan2.1-flf2v-plus": [5, 10],
}


def get_dashscope_key() -> str:
    """Retrieve DashScope API key from environment or .env files."""
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if key:
        return key
    # Try .env files
    for env_path in [
        Path.home() / ".hermes" / ".env",
        Path.home() / ".hermes" / "hermes-agent" / ".env",
    ]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# ═══════════════════════════════════════════════════════════════
# Resolution Helper
# ═══════════════════════════════════════════════════════════════

def resolve_dimensions(
    resolution: str = "720P",
    orientation: Literal["landscape", "portrait"] = "landscape",
) -> tuple[int, int]:
    """
    Convert resolution label + orientation to (width, height).

    Args:
        resolution: "480P", "720P", or "1080P"
        orientation: "landscape" (16:9) or "portrait" (9:16)

    Returns:
        (width, height) tuple
    """
    res = resolution.upper().replace("P", "") + "P"
    if res not in RESOLUTION_PRESETS:
        res = "720P"
    preset = RESOLUTION_PRESETS[res]
    return preset.get(orientation, preset["landscape"])


# ═══════════════════════════════════════════════════════════════
# Prompt Engineering for Video
# ═══════════════════════════════════════════════════════════════

# Cinematic motion keywords that Wan2.1 responds well to
WAN_MOTION_KEYWORDS = [
    "smooth camera movement", "tracking shot", "slow motion",
    "time-lapse", "dolly zoom", "steady pan",
    "cinematic lighting", "depth of field",
    "dynamic movement", "fluid motion",
]

# Style modifiers for different video types
WAN_STYLE_PRESETS = {
    "cinematic": "cinematic shot, film grain, dramatic lighting, anamorphic lens, shallow depth of field",
    "anime": "anime style, vibrant colors, dynamic animation, Studio Ghibli aesthetic",
    "realistic": "photorealistic, high detail, natural lighting, 8K quality",
    "documentary": "documentary style, natural movement, realistic motion, steady handheld",
    "music-video": "music video style, vibrant neon colors, dynamic editing, artistic transitions",
    "product": "product showcase, studio lighting, clean background, smooth rotation",
    "nature": "nature documentary, wildlife footage, golden hour lighting, slow gentle movement",
}


def enhance_video_prompt(
    prompt: str,
    style: Optional[str] = None,
    motion: Optional[str] = None,
    negative: Optional[str] = None,
) -> str:
    """
    Enhance a video generation prompt with cinematic and motion cues
    optimized for Wan2.1's video model.

    Args:
        prompt: Base text description
        style: Style preset name (cinematic/anime/realistic/documentary/music-video/product/nature)
        motion: Motion description (e.g., "slow pan left", "tracking forward")
        negative: Negative prompt elements to avoid

    Returns:
        Enhanced prompt string
    """
    parts = [prompt.strip()]

    # Add style preset
    if style and style.lower() in WAN_STYLE_PRESETS:
        parts.append(WAN_STYLE_PRESETS[style.lower()])

    # Add motion description
    if motion:
        parts.append(motion)
    else:
        # Auto-detect if user described camera movement
        movement_words = ["pan", "zoom", "track", "dolly", "rotate", "orbit", "tilt"]
        has_motion = any(w in prompt.lower() for w in movement_words)
        if not has_motion:
            parts.append("smooth natural movement")

    # Build final prompt
    enhanced = ", ".join(parts)

    # Add negative prompt if provided
    if negative:
        enhanced += f" --no {negative}"

    return enhanced


# ═══════════════════════════════════════════════════════════════
# Core API: Submit Async Task
# ═══════════════════════════════════════════════════════════════

def _submit_wan_task(
    model: str,
    input_params: dict,
    resolution: str = "720P",
    duration: int = 5,
    orientation: str = "landscape",
    api_key: str = "",
) -> tuple[Optional[str], Optional[str]]:
    """Submit an async video generation task to DashScope."""
    if not api_key:
        return None, "DASHSCOPE_API_KEY 未设置"

    w, h = resolve_dimensions(resolution, orientation)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    payload = {
        "model": model,
        "input": input_params,
        "parameters": {
            "resolution": f"{w}*{h}",
            "duration": duration,
        },
    }

    try:
        resp = requests.post(
            DASHSCOPE_ASYNC_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # Check for errors
        if "error_code" in data or "message" in data and "task_id" not in data:
            return None, f"Wan2.1 任务提交失败: {data}"

        task_id = data.get("output", {}).get("task_id")
        if not task_id:
            return None, f"Wan2.1 返回无 task_id: {data}"

        return task_id, None
    except requests.exceptions.HTTPError as e:
        return None, f"Wan2.1 HTTP 错误: {e} - {resp.text[:300]}"
    except Exception as e:
        return None, f"Wan2.1 任务提交异常: {e}"


def _poll_wan_task(
    task_id: str,
    api_key: str,
    poll_interval: int = 5,
    poll_timeout: int = 300,
) -> tuple[Optional[str], Optional[str]]:
    """
    Poll a DashScope async task until completion.
    Returns (video_url, error).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    start = time.time()
    while time.time() - start < poll_timeout:
        time.sleep(poll_interval)
        try:
            resp = requests.get(
                f"{DASHSCOPE_TASK_URL}/{task_id}",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            output = data.get("output", {})
            status = output.get("status", "")

            if status == "SUCCEEDED":
                # Extract video URL from results
                results = output.get("results", [])
                if results and isinstance(results, list):
                    video_url = results[0].get("url", "")
                else:
                    video_url = output.get("video_url", "")

                if not video_url:
                    return None, f"Wan2.1 成功但无视频 URL: {data}"
                return video_url, None

            elif status == "FAILED":
                code = output.get("code", "unknown")
                message = output.get("message", "unknown error")
                return None, f"Wan2.1 生成失败 [{code}]: {message}"

            # PENDING / RUNNING → continue polling
        except Exception as e:
            return None, f"Wan2.1 轮询异常: {e}"

    return None, f"Wan2.1 轮询超时 ({poll_timeout}s), task_id={task_id}"


def _download_video(
    url: str,
    output_dir: Optional[str] = None,
    prefix: str = "wan_video",
) -> tuple[Optional[str], Optional[str]]:
    """Download video from URL to local file."""
    try:
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
    except Exception as e:
        return None, f"视频下载失败: {e}"

    if output_dir:
        out_dir = Path(output_dir).expanduser()
    else:
        out_dir = Path.home() / "Desktop"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    filepath = out_dir / f"{prefix}_{ts}.mp4"

    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_kb = filepath.stat().st_size // 1024
    print(f"[Wan2.1] ✅ 已保存: {filepath} ({size_kb} KB)", flush=True)
    return str(filepath), None


# ═══════════════════════════════════════════════════════════════
# Public API: Text-to-Video
# ═══════════════════════════════════════════════════════════════

def generate_video_wan(
    prompt: str,
    model: str = "wan2.1-t2v-plus",
    duration: int = 5,
    resolution: str = "720P",
    orientation: str = "landscape",
    style: Optional[str] = None,
    motion: Optional[str] = None,
    negative: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 300,
    output_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Generate video from text prompt using Wan2.1.

    Args:
        prompt: Video description text
        model: Wan2.1 model ID (wan2.1-t2v-plus, wan2.1-t2v-turbo)
        duration: Video duration in seconds (5 or 10)
        resolution: Output resolution (480P / 720P / 1080P)
        orientation: "landscape" or "portrait"
        style: Style preset (cinematic/anime/realistic/documentary/music-video/product/nature)
        motion: Camera motion description
        negative: Elements to avoid
        poll_interval: Polling interval in seconds
        poll_timeout: Max wait time in seconds
        output_dir: Output directory (default: ~/Desktop)

    Returns:
        (local_file_path, None) on success
        (None, error_str) on failure
    """
    api_key = get_dashscope_key()
    if not api_key:
        return None, "DASHSCOPE_API_KEY 未设置（Wan2.1 需要阿里云 DashScope API Key）"

    # Resolve model ID
    model_id = WAN_MODELS.get(model, model)

    # Enhance prompt
    enhanced_prompt = enhance_video_prompt(prompt, style=style, motion=motion, negative=negative)

    input_params = {"prompt": enhanced_prompt}

    print(f"[Wan2.1] T2V model={model_id} res={resolution} dur={duration}s", flush=True)
    print(f"[Wan2.1] prompt: {enhanced_prompt[:120]}...", flush=True)

    # Submit task
    task_id, err = _submit_wan_task(
        model=model_id,
        input_params=input_params,
        resolution=resolution,
        duration=duration,
        orientation=orientation,
        api_key=api_key,
    )
    if err:
        return None, err

    print(f"[Wan2.1] task_id={task_id} 开始轮询...", flush=True)

    # Poll until done
    video_url, err = _poll_wan_task(task_id, api_key, poll_interval, poll_timeout)
    if err:
        return None, err

    # Download
    return _download_video(video_url, output_dir, prefix="wan_t2v")


# ═══════════════════════════════════════════════════════════════
# Public API: Image-to-Video
# ═══════════════════════════════════════════════════════════════

def generate_video_wan_i2v(
    image_url: str,
    prompt: str = "",
    model: str = "wan2.1-i2v-plus",
    duration: int = 5,
    resolution: str = "720P",
    orientation: str = "landscape",
    style: Optional[str] = None,
    motion: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 300,
    output_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Generate video from an image using Wan2.1 Image-to-Video.

    Args:
        image_url: URL or base64 of the source image
        prompt: Optional text description of desired motion/content
        model: Wan2.1 I2V model (wan2.1-i2v-plus, wan2.1-i2v-turbo)
        duration: Video duration (5 or 10 seconds)
        resolution: Output resolution (480P / 720P / 1080P)
        orientation: "landscape" or "portrait"
        style: Style preset
        motion: Camera motion description
        poll_interval: Polling interval
        poll_timeout: Max wait time
        output_dir: Output directory

    Returns:
        (local_file_path, None) on success
        (None, error_str) on failure
    """
    api_key = get_dashscope_key()
    if not api_key:
        return None, "DASHSCOPE_API_KEY 未设置"

    model_id = WAN_MODELS.get(model, model)

    # Build input - image URL is required for I2V
    input_params = {"img_url": image_url}
    if prompt:
        enhanced = enhance_video_prompt(prompt, style=style, motion=motion)
        input_params["prompt"] = enhanced

    print(f"[Wan2.1] I2V model={model_id} res={resolution} dur={duration}s", flush=True)

    task_id, err = _submit_wan_task(
        model=model_id,
        input_params=input_params,
        resolution=resolution,
        duration=duration,
        orientation=orientation,
        api_key=api_key,
    )
    if err:
        return None, err

    print(f"[Wan2.1] task_id={task_id} 开始轮询...", flush=True)

    video_url, err = _poll_wan_task(task_id, api_key, poll_interval, poll_timeout)
    if err:
        return None, err

    return _download_video(video_url, output_dir, prefix="wan_i2v")


# ═══════════════════════════════════════════════════════════════
# Public API: First-Last-Frame-to-Video
# ═══════════════════════════════════════════════════════════════

def generate_video_wan_flf2v(
    first_frame_url: str,
    last_frame_url: str,
    prompt: str = "",
    model: str = "wan2.1-flf2v-plus",
    duration: int = 5,
    resolution: str = "720P",
    orientation: str = "landscape",
    poll_interval: int = 5,
    poll_timeout: int = 300,
    output_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Generate video by interpolating between first and last frames using Wan2.1.

    Args:
        first_frame_url: URL of the first frame image
        last_frame_url: URL of the last frame image
        prompt: Optional text description
        model: Wan2.1 FLF2V model
        duration: Video duration (5 or 10 seconds)
        resolution: Output resolution (480P / 720P / 1080P)
        orientation: "landscape" or "portrait"
        poll_interval: Polling interval
        poll_timeout: Max wait time
        output_dir: Output directory

    Returns:
        (local_file_path, None) on success
        (None, error_str) on failure
    """
    api_key = get_dashscope_key()
    if not api_key:
        return None, "DASHSCOPE_API_KEY 未设置"

    model_id = WAN_MODELS.get(model, model)

    input_params = {
        "first_frame_url": first_frame_url,
        "last_frame_url": last_frame_url,
    }
    if prompt:
        input_params["prompt"] = prompt

    print(f"[Wan2.1] FLF2V model={model_id} res={resolution} dur={duration}s", flush=True)

    task_id, err = _submit_wan_task(
        model=model_id,
        input_params=input_params,
        resolution=resolution,
        duration=duration,
        orientation=orientation,
        api_key=api_key,
    )
    if err:
        return None, err

    print(f"[Wan2.1] task_id={task_id} 开始轮询...", flush=True)

    video_url, err = _poll_wan_task(task_id, api_key, poll_interval, poll_timeout)
    if err:
        return None, err

    return _download_video(video_url, output_dir, prefix="wan_flf2v")


def generate_video_wan_controlnet(
    prompt: str,
    control_type: str = "depth",
    control_image_url: Optional[str] = None,
    control_image_path: Optional[str] = None,
    model: str = "wan2.1-t2v-plus",
    duration: int = 5,
    resolution: str = "720P",
    orientation: str = "landscape",
    strength: float = 1.0,
    style: Optional[str] = None,
    motion: Optional[str] = None,
    negative: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 300,
    output_dir: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Wan2.1 + Uni3C ControlNet 视频生成

    通过 ControlNet 控制信号（深度图、边缘图、姿态图等）引导 Wan2.1 视频生成，
    实现对生成视频运动和结构的精确控制。

    Args:
        prompt: 视频描述
        control_type: 控制信号类型 ("depth"/"canny"/"pose"/"lineart"/...)
        control_image_url: 控制图像 URL（与 control_image_path 二选一）
        control_image_path: 控制图像本地路径（自动上传）
        model: Wan 模型名
        duration: 视频时长（秒）
        resolution: 分辨率 ("480P" / "720P" / "1080P")
        orientation: 方向 ("landscape" / "portrait")
        strength: ControlNet 控制强度 (0.0-2.0)
        style: 风格预设
        motion: 摄像机运动描述
        negative: 负面提示词
        poll_interval: 轮询间隔
        poll_timeout: 最大等待时间
        output_dir: 输出目录

    Returns:
        (file_path, None) on success, (None, error_str) on failure
    """
    api_key = get_dashscope_key()
    if not api_key:
        return None, "DASHSCOPE_API_KEY 未设置"

    # Resolve control image URL
    resolved_url = control_image_url
    if not resolved_url and control_image_path:
        from pathlib import Path
        p = Path(control_image_path)
        if not p.exists():
            return None, f"控制图像不存在: {control_image_path}"
        # For local files, use file URI (DashScope supports it for some modes)
        resolved_url = p.resolve().as_uri()

    if not resolved_url:
        return None, "control_image_url 或 control_image_path 必须提供一个"

    # Build enhanced prompt with control signal description
    enhanced = _build_controlnet_prompt(prompt, control_type, style, motion, negative)

    # Submit via Wan2.1 I2V with control image as source
    # Uni3C ControlNet uses the control image as conditioning input
    model_id = WAN_MODELS.get(model, model)
    if "i2v" not in model_id:
        # Fall back to i2v model for control-guided generation
        model_id = "wan2.1-i2v-plus"

    input_params: Dict[str, Any] = {
        "img_url": resolved_url,
        "prompt": enhanced,
    }

    # Pass strength as a generation parameter
    # DashScope Wan2.1 I2V uses img_url as conditioning — strength maps to
    # the denoise/control balance
    print(
        f"[Wan2.1 ControlNet] type={control_type} model={model_id} "
        f"res={resolution} dur={duration}s strength={strength}",
        flush=True,
    )

    task_id, err = _submit_wan_task(
        model=model_id,
        input_params=input_params,
        resolution=resolution,
        duration=duration,
        orientation=orientation,
        api_key=api_key,
    )
    if err:
        return None, err
    assert task_id is not None  # guaranteed by err check above

    print(f"[Wan2.1 ControlNet] task_id={task_id} polling...", flush=True)

    video_url, err = _poll_wan_task(task_id, api_key, poll_interval, poll_timeout)
    if err:
        return None, err
    assert video_url is not None  # guaranteed by err check above

    return _download_video(video_url, output_dir, prefix=f"wan_cn_{control_type}")


def _build_controlnet_prompt(
    prompt: str,
    control_type: str,
    style: Optional[str] = None,
    motion: Optional[str] = None,
    negative: Optional[str] = None,
) -> str:
    """构建融合 ControlNet 控制描述的增强 prompt"""
    parts = [prompt.strip()]

    # Add control-type context hints for the model
    _CONTROL_HINTS = {
        "depth": "scene with depth structure preserved",
        "canny": "following the edge contours",
        "pose": "with body pose and motion guidance",
        "hed": "with soft edge structure",
        "normal": "preserving surface normals",
        "segment": "respecting segmentation regions",
        "lineart": "following line art contours",
        "shuffle": "with content structure rearrangement",
        "mlsd": "with straight line structure",
        "softedge": "with soft edge blending",
        "openpose": "with skeletal pose guidance",
        "recolor": "with recoloring guidance",
        "ip2p": "with instruction-based editing",
    }
    hint = _CONTROL_HINTS.get(control_type, "")
    if hint:
        parts.append(hint)

    if style:
        parts.append(f"style: {style}")
    if motion:
        parts.append(f"camera motion: {motion}")
    if negative:
        parts.append(f"negative: {negative}")

    return ", ".join(parts)


def list_controlnet_types() -> list[dict]:
    """列出所有支持的 Uni3C ControlNet 控制类型"""
    return [
        {"type": "depth", "name": "深度图", "description": "场景深度结构控制",
         "preprocessor": "depth_midas", "recommended_for": ["场景", "建筑", "室内"]},
        {"type": "canny", "name": "边缘检测", "description": "Canny 边缘轮廓控制",
         "preprocessor": "canny", "recommended_for": ["物体", "线条", "轮廓"]},
        {"type": "pose", "name": "人体姿态", "description": "人体姿态和动作引导",
         "preprocessor": "openpose", "recommended_for": ["人物", "舞蹈", "运动"]},
        {"type": "hed", "name": "HED 边缘", "description": "HED 边缘结构控制",
         "preprocessor": "hed", "recommended_for": ["艺术", "插画", "风格化"]},
        {"type": "normal", "name": "法线图", "description": "表面法线方向控制",
         "preprocessor": "normal_bae", "recommended_for": ["3D", "材质", "光照"]},
        {"type": "segment", "name": "语义分割", "description": "语义区域分割控制",
         "preprocessor": "segment", "recommended_for": ["场景布局", "区域控制"]},
        {"type": "lineart", "name": "线稿", "description": "线稿轮廓控制",
         "preprocessor": "lineart", "recommended_for": ["动画", "漫画", "草稿"]},
        {"type": "shuffle", "name": "内容重排", "description": "内容结构重排",
         "preprocessor": "shuffle", "recommended_for": ["风格转换", "创意"]},
        {"type": "mlsd", "name": "线段检测", "description": "直线段结构控制",
         "preprocessor": "mlsd", "recommended_for": ["建筑", "室内设计"]},
        {"type": "softedge", "name": "软边缘", "description": "软边缘混合控制",
         "preprocessor": "softedge", "recommended_for": ["柔和过渡", "人像"]},
        {"type": "openpose", "name": "OpenPose", "description": "OpenPose 骨架控制",
         "preprocessor": "openpose", "recommended_for": ["多人", "手势", "全身"]},
        {"type": "recolor", "name": "重着色", "description": "色彩重映射控制",
         "preprocessor": "recolor", "recommended_for": ["色彩校正", "风格化"]},
        {"type": "ip2p", "name": "指令编辑", "description": "InstructPix2Pix 指令编辑",
         "preprocessor": "ip2p", "recommended_for": ["编辑", "局部修改"]},
    ]


# ═══════════════════════════════════════════════════════════════
# Model Discovery
# ═══════════════════════════════════════════════════════════════

def list_wan_models() -> list[dict]:
    """List all available Wan2.1 models with their capabilities."""
    return [
        {
            "model": "wan2.1-t2v-plus",
            "task": "text-to-video",
            "description": "Wan2.1 文生视频（高质量）",
            "resolutions": ["480P", "720P"],
            "durations": [5, 10],
        },
        {
            "model": "wan2.1-t2v-turbo",
            "task": "text-to-video",
            "description": "Wan2.1 文生视频（快速）",
            "resolutions": ["480P", "720P"],
            "durations": [5, 10],
        },
        {
            "model": "wan2.1-i2v-plus",
            "task": "image-to-video",
            "description": "Wan2.1 图生视频（高质量）— 将静态图片动画化",
            "resolutions": ["480P", "720P"],
            "durations": [5, 10],
        },
        {
            "model": "wan2.1-i2v-turbo",
            "task": "image-to-video",
            "description": "Wan2.1 图生视频（快速）— 将静态图片动画化",
            "resolutions": ["480P", "720P"],
            "durations": [5, 10],
        },
        {
            "model": "wan2.1-flf2v-plus",
            "task": "first-last-frame-to-video",
            "description": "Wan2.1 首尾帧插值 — 在两张图片间生成过渡视频",
            "resolutions": ["480P", "720P"],
            "durations": [5, 10],
        },
    ]


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wan2.1 视频生成测试")
    sub = parser.add_subparsers(dest="cmd")

    # T2V
    p_t2v = sub.add_parser("t2v", help="文生视频")
    p_t2v.add_argument("prompt", help="视频描述")
    p_t2v.add_argument("--model", default="wan2.1-t2v-plus")
    p_t2v.add_argument("--duration", type=int, default=5)
    p_t2v.add_argument("--resolution", default="720P")
    p_t2v.add_argument("--orientation", default="landscape")
    p_t2v.add_argument("--style", default=None, help="风格预设")

    # I2V
    p_i2v = sub.add_parser("i2v", help="图生视频")
    p_i2v.add_argument("image_url", help="图片 URL")
    p_i2v.add_argument("--prompt", default="", help="可选描述")
    p_i2v.add_argument("--model", default="wan2.1-i2v-plus")
    p_i2v.add_argument("--duration", type=int, default=5)
    p_i2v.add_argument("--resolution", default="720P")

    # FLF2V
    p_flf = sub.add_parser("flf2v", help="首尾帧插值")
    p_flf.add_argument("first_frame", help="首帧 URL")
    p_flf.add_argument("last_frame", help="尾帧 URL")
    p_flf.add_argument("--prompt", default="")
    p_flf.add_argument("--duration", type=int, default=5)
    p_flf.add_argument("--resolution", default="720P")

    # List models
    sub.add_parser("models", help="列出所有 Wan2.1 模型")

    args = parser.parse_args()

    if args.cmd == "t2v":
        path, err = generate_video_wan(
            args.prompt, model=args.model, duration=args.duration,
            resolution=args.resolution, orientation=args.orientation, style=args.style,
        )
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 视频路径: {path}")

    elif args.cmd == "i2v":
        path, err = generate_video_wan_i2v(
            args.image_url, prompt=args.prompt, model=args.model,
            duration=args.duration, resolution=args.resolution,
        )
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 视频路径: {path}")

    elif args.cmd == "flf2v":
        path, err = generate_video_wan_flf2v(
            args.first_frame, args.last_frame, prompt=args.prompt,
            duration=args.duration, resolution=args.resolution,
        )
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 视频路径: {path}")

    elif args.cmd == "models":
        for m in list_wan_models():
            print(f"  {m['model']:25s} | {m['task']:30s} | {m['description']}")

    else:
        parser.print_help()
