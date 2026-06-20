#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Video Generation Router
=================================
Routes video generation requests to the appropriate backend:
  - MiniMax Hailuo (text-to-video, via MiniMax API)
  - Wan2.1 (text-to-video, image-to-video, FLF2V, via DashScope API)

Brand: AtomCollide-智械工坊

Provides a single `generate_video()` function with backend selection,
unified resolution mapping, and prompt engineering.

Resolution map (shared across backends):
  480P  → 832×480 (landscape) / 480×832 (portrait)
  720P  → 1280×720 / 720×1280
  1080P → 1920×1080 / 1080×1920
"""

from __future__ import annotations

import os
from typing import Optional, Literal

# Import backends
try:
    from scripts.minimax_media import generate_video as minimax_generate_video
except ImportError:
    minimax_generate_video = None

try:
    from scripts.wan_video import (
        generate_video_wan,
        generate_video_wan_i2v,
        generate_video_wan_flf2v,
        enhance_video_prompt,
        list_wan_models,
        resolve_dimensions,
    )
except ImportError:
    try:
        from wan_video import (
            generate_video_wan,
            generate_video_wan_i2v,
            generate_video_wan_flf2v,
            enhance_video_prompt,
            list_wan_models,
            resolve_dimensions,
        )
    except ImportError:
        generate_video_wan = None
        generate_video_wan_i2v = None
        generate_video_wan_flf2v = None
        enhance_video_prompt = None
        list_wan_models = None
        resolve_dimensions = None


# ═══════════════════════════════════════════════════════════════
# Backend Registry
# ═══════════════════════════════════════════════════════════════

BACKENDS = {
    "minimax": {
        "name": "MiniMax Hailuo",
        "models": ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02", "video-01"],
        "tasks": ["text-to-video"],
        "resolutions": ["544P", "768P", "1080P"],
        "durations": [3, 6, 10],
        "requires_key": "MINIMAX_API_KEY",
    },
    "wan2.1": {
        "name": "Wan2.1 (Alibaba)",
        "models": [
            "wan2.1-t2v-plus", "wan2.1-t2v-turbo",
            "wan2.1-i2v-plus", "wan2.1-i2v-turbo",
            "wan2.1-flf2v-plus",
        ],
        "tasks": ["text-to-video", "image-to-video", "first-last-frame-to-video"],
        "resolutions": ["480P", "720P", "1080P"],
        "durations": [5, 10],
        "requires_key": "DASHSCOPE_API_KEY",
    },
}

# Model → backend auto-detection
MODEL_TO_BACKEND = {
    "MiniMax-Hailuo-2.3": "minimax",
    "MiniMax-Hailuo-02": "minimax",
    "video-01": "minimax",
    "wan2.1-t2v-plus": "wan2.1",
    "wan2.1-t2v-turbo": "wan2.1",
    "wan2.1-i2v-plus": "wan2.1",
    "wan2.1-i2v-turbo": "wan2.1",
    "wan2.1-flf2v-plus": "wan2.1",
}


# ═══════════════════════════════════════════════════════════════
# Resolution Normalization
# ═══════════════════════════════════════════════════════════════

def normalize_resolution(resolution: str, backend: str) -> str:
    """
    Normalize resolution label to backend-specific format.

    MiniMax uses: "544P", "768P", "1080P" (capital P)
    Wan2.1 uses:  "480P", "720P", "1080P" (capital P)

    Cross-map when needed:
      480P → 544P (MiniMax closest)
      720P → 768P (MiniMax closest)
      768P → 720P (Wan2.1 closest)
      544P → 480P (Wan2.1 closest)
    """
    res = resolution.upper().strip()

    # Normalize common variations
    res = res.replace("P", "P").replace("p", "P")

    if backend == "minimax":
        mapping = {"480P": "544P", "720P": "768P", "1080P": "1080P"}
        return mapping.get(res, res)
    elif backend == "wan2.1":
        mapping = {"544P": "480P", "768P": "720P", "1080P": "1080P"}
        return mapping.get(res, res)

    return res


# ═══════════════════════════════════════════════════════════════
# Unified Video Generation
# ═══════════════════════════════════════════════════════════════

def generate_video(
    prompt: str,
    model: str = "MiniMax-Hailuo-2.3",
    duration: int = 6,
    resolution: str = "720P",
    backend: Optional[str] = None,
    orientation: str = "landscape",
    style: Optional[str] = None,
    motion: Optional[str] = None,
    negative: Optional[str] = None,
    image_url: Optional[str] = None,
    last_frame_url: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 300,
    output_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Unified video generation — routes to MiniMax or Wan2.1 backend.

    Args:
        prompt: Video description
        model: Model name (auto-detects backend)
        duration: Duration in seconds
        resolution: "480P" / "720P" / "1080P"
        backend: Force backend ("minimax" / "wan2.1"), or auto-detect from model
        orientation: "landscape" or "portrait" (Wan2.1 only)
        style: Style preset for Wan2.1 (cinematic/anime/realistic/...)
        motion: Camera motion description for Wan2.1
        negative: Negative prompt for Wan2.1
        image_url: Source image URL for I2V (Wan2.1 only)
        last_frame_url: Last frame URL for FLF2V (Wan2.1 only)
        poll_interval: Polling interval
        poll_timeout: Max wait time
        output_dir: Output directory

    Returns:
        (file_path, None) on success
        (None, error_str) on failure
    """
    # Auto-detect backend from model name
    if not backend:
        backend = MODEL_TO_BACKEND.get(model)
        if not backend:
            # Default to minimax for backward compatibility
            backend = "minimax"

    # Normalize resolution for target backend
    norm_res = normalize_resolution(resolution, backend)

    if backend == "minimax":
        if minimax_generate_video is None:
            return None, "MiniMax 后端未加载 (minimax_media.py)"
        return minimax_generate_video(
            prompt=prompt,
            model=model,
            duration=duration,
            resolution=norm_res,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            output_dir=output_dir,
        )

    elif backend == "wan2.1":
        if generate_video_wan is None:
            return None, "Wan2.1 后端未加载 (wan_video.py)"

        # Determine task type
        if last_frame_url and image_url:
            # First-Last-Frame-to-Video
            if generate_video_wan_flf2v is None:
                return None, "Wan2.1 FLF2V 后端未加载"
            return generate_video_wan_flf2v(
                first_frame_url=image_url,
                last_frame_url=last_frame_url,
                prompt=prompt,
                model="wan2.1-flf2v-plus",
                duration=duration,
                resolution=norm_res,
                orientation=orientation,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
                output_dir=output_dir,
            )
        elif image_url:
            # Image-to-Video
            if generate_video_wan_i2v is None:
                return None, "Wan2.1 I2V 后端未加载"
            i2v_model = model if "i2v" in model else "wan2.1-i2v-plus"
            return generate_video_wan_i2v(
                image_url=image_url,
                prompt=prompt,
                model=i2v_model,
                duration=duration,
                resolution=norm_res,
                orientation=orientation,
                style=style,
                motion=motion,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
                output_dir=output_dir,
            )
        else:
            # Text-to-Video
            t2v_model = model if "t2v" in model or model in MODEL_TO_BACKEND else "wan2.1-t2v-plus"
            return generate_video_wan(
                prompt=prompt,
                model=t2v_model,
                duration=duration,
                resolution=norm_res,
                orientation=orientation,
                style=style,
                motion=motion,
                negative=negative,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
                output_dir=output_dir,
            )

    return None, f"未知后端: {backend}"


# ═══════════════════════════════════════════════════════════════
# Backends Listing
# ═══════════════════════════════════════════════════════════════

def list_backends() -> list[dict]:
    """List all available video backends and their status."""
    result = []
    for key, info in BACKENDS.items():
        key_env = info["requires_key"]
        has_key = bool(os.environ.get(key_env, ""))
        result.append({
            "backend": key,
            "name": info["name"],
            "status": "✅ 就绪" if has_key else f"❌ 需要 {key_env}",
            "tasks": info["tasks"],
            "resolutions": info["resolutions"],
            "models": info["models"],
        })
    return result


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="统一视频生成路由")
    sub = parser.add_subparsers(dest="cmd")

    # Generate
    p_gen = sub.add_parser("generate", help="生成视频")
    p_gen.add_argument("prompt", help="视频描述")
    p_gen.add_argument("--model", default="MiniMax-Hailuo-2.3")
    p_gen.add_argument("--backend", default=None, help="强制指定后端")
    p_gen.add_argument("--duration", type=int, default=6)
    p_gen.add_argument("--resolution", default="720P")
    p_gen.add_argument("--orientation", default="landscape")
    p_gen.add_argument("--style", default=None)
    p_gen.add_argument("--image-url", default=None, help="图生视频：源图片URL")

    # List backends
    sub.add_parser("backends", help="列出所有后端状态")

    args = parser.parse_args()

    if args.cmd == "generate":
        path, err = generate_video(
            prompt=args.prompt,
            model=args.model,
            backend=args.backend,
            duration=args.duration,
            resolution=args.resolution,
            orientation=args.orientation,
            style=args.style,
            image_url=args.image_url,
        )
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 视频路径: {path}")

    elif args.cmd == "backends":
        for b in list_backends():
            print(f"  {b['backend']:12s} | {b['name']:20s} | {b['status']}")

    else:
        parser.print_help()
