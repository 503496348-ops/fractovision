# -*- coding: utf-8 -*-
"""
破窗造视-Fractovision · Post-Processing Engine
AtomCollide-智械工坊 · 2026

轻量化适配（API优先，无需本地GPU）。

能力:
  - BG1: 背景移除 (rembg API / 本地fallback)
  - AU1: 音频提取 (ffmpeg)
  - AU2: 音频叠加 (ffmpeg)
  - IC1: 图片A/B对比 (HTML side-by-side)
  - RE1: 分辨率优化器 (社交平台适配)

Usage:
    from post_processing import PostProcessor
    pp = PostProcessor()
    pp.remove_bg("input.png", "output.png")
    pp.extract_audio("video.mp4", "audio.mp3")
    pp.overlay_audio("video.mp4", "audio.mp3", "output.mp4")
    html = pp.compare_images("before.png", "after.png")
    dims = pp.optimal_resolution("抖音", is_video=True)
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class ProcessResult:
    """后处理结果"""
    success: bool
    input_path: str
    output_path: str
    operation: str
    details: str
    duration_sec: float = 0.0


# ── RE1: 社交平台分辨率规范 ──

PLATFORM_SPECS: Dict[str, Dict[str, Dict[str, int]]] = {
    "抖音": {
        "video": {"width": 1080, "height": 1920, "ratio": "9:16"},
        "image": {"width": 1080, "height": 1920, "ratio": "9:16"},
        "cover": {"width": 1080, "height": 1440, "ratio": "3:4"},
    },
    "小红书": {
        "video": {"width": 1080, "height": 1440, "ratio": "3:4"},
        "image": {"width": 1080, "height": 1440, "ratio": "3:4"},
        "cover": {"width": 1080, "height": 810, "ratio": "4:3"},
    },
    "B站": {
        "video": {"width": 1920, "height": 1080, "ratio": "16:9"},
        "image": {"width": 1920, "height": 1080, "ratio": "16:9"},
        "cover": {"width": 1146, "height": 717, "ratio": "16:10"},
    },
    "YouTube": {
        "video": {"width": 1920, "height": 1080, "ratio": "16:9"},
        "image": {"width": 1280, "height": 720, "ratio": "16:9"},
        "cover": {"width": 1280, "height": 720, "ratio": "16:9"},
    },
    "Instagram": {
        "video": {"width": 1080, "height": 1080, "ratio": "1:1"},
        "image": {"width": 1080, "height": 1080, "ratio": "1:1"},
        "story": {"width": 1080, "height": 1920, "ratio": "9:16"},
        "cover": {"width": 1080, "height": 1080, "ratio": "1:1"},
    },
    "微信视频号": {
        "video": {"width": 1080, "height": 1260, "ratio": "6:7"},
        "image": {"width": 1080, "height": 1260, "ratio": "6:7"},
        "cover": {"width": 1080, "height": 1260, "ratio": "6:7"},
    },
    "Twitter": {
        "video": {"width": 1280, "height": 720, "ratio": "16:9"},
        "image": {"width": 1200, "height": 675, "ratio": "16:9"},
        "cover": {"width": 1500, "height": 500, "ratio": "3:1"},
    },
}


class PostProcessor:
    """后处理器"""

    def __init__(self, output_dir: str = "/tmp/fractovision_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _run_cmd(self, cmd: List[str], timeout: int = 120) -> Tuple[bool, str]:
        """执行外部命令"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode == 0, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, f"Command not found: {cmd[0]}"
        except Exception as e:
            return False, str(e)

    # ── BG1: 背景移除 ──

    def remove_bg(self, input_path: str, output_path: Optional[str] = None,
                  method: str = "rembg") -> ProcessResult:
        """
        移除图片背景。

        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径 (默认: output_dir/input_nobg.png)
            method: "rembg" (API) 或 "ffmpeg" (边缘检测fallback)

        Returns:
            处理结果
        """
        import time
        start = time.time()

        if output_path is None:
            stem = Path(input_path).stem
            output_path = str(self.output_dir / f"{stem}_nobg.png")

        if method == "rembg":
            # Try rembg CLI (pip install rembg)
            ok, msg = self._run_cmd([
                "rembg", "i", "-a", input_path, output_path
            ])
            if ok:
                return ProcessResult(
                    success=True, input_path=input_path, output_path=output_path,
                    operation="BG1:background_removal",
                    details="Background removed via rembg",
                    duration_sec=time.time() - start,
                )
            # Fallback: try Python import
            try:
                from rembg import remove
                from PIL import Image
                img = Image.open(input_path)
                output = remove(img)
                output.save(output_path)
                return ProcessResult(
                    success=True, input_path=input_path, output_path=output_path,
                    operation="BG1:background_removal",
                    details="Background removed via rembg (Python)",
                    duration_sec=time.time() - start,
                )
            except ImportError:
                pass

        # Fallback: ImageMagick
        ok, msg = self._run_cmd([
            "convert", input_path, "-fuzz", "20%",
            "-trim", "+repage", output_path
        ])
        if ok:
            return ProcessResult(
                success=True, input_path=input_path, output_path=output_path,
                operation="BG1:background_removal",
                details="Background trimmed via ImageMagick (approximate)",
                duration_sec=time.time() - start,
            )

        return ProcessResult(
            success=False, input_path=input_path, output_path="",
            operation="BG1:background_removal",
            details=f"Failed: {msg}. Install rembg (pip install rembg) or ImageMagick",
        )

    # ── AU1: 音频提取 ──

    def extract_audio(self, video_path: str, output_path: Optional[str] = None,
                      format: str = "mp3") -> ProcessResult:
        """
        从视频中提取音频。

        Args:
            video_path: 输入视频路径
            output_path: 输出音频路径
            format: 输出格式 (mp3/wav/aac)

        Returns:
            处理结果
        """
        import time
        start = time.time()

        if output_path is None:
            stem = Path(video_path).stem
            output_path = str(self.output_dir / f"{stem}.{format}")

        ok, msg = self._run_cmd([
            "ffmpeg", "-i", video_path, "-vn", "-acodec",
            "libmp3lame" if format == "mp3" else "copy",
            "-y", output_path
        ])

        return ProcessResult(
            success=ok, input_path=video_path, output_path=output_path,
            operation="AU1:audio_extraction",
            details=f"Audio extracted as {format}" if ok else f"Failed: {msg}",
            duration_sec=time.time() - start,
        )

    # ── AU2: 音频叠加 ──

    def overlay_audio(self, video_path: str, audio_path: str,
                      output_path: Optional[str] = None,
                      replace: bool = True, volume: float = 1.0) -> ProcessResult:
        """
        将音频叠加到视频上。

        Args:
            video_path: 输入视频路径
            audio_path: 音频路径
            output_path: 输出视频路径
            replace: True=替换原音, False=混合
            volume: 音量倍数 (0.0-2.0)

        Returns:
            处理结果
        """
        import time
        start = time.time()

        if output_path is None:
            stem = Path(video_path).stem
            output_path = str(self.output_dir / f"{stem}_with_audio.mp4")

        if replace:
            cmd = [
                "ffmpeg", "-i", video_path, "-i", audio_path,
                "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                "-af", f"volume={volume}",
                "-shortest", "-y", output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-i", video_path, "-i", audio_path,
                "-filter_complex", f"[0:a][1:a]amix=inputs=2:duration=shortest,volume={volume}",
                "-c:v", "copy", "-y", output_path
            ]

        ok, msg = self._run_cmd(cmd, timeout=300)

        return ProcessResult(
            success=ok, input_path=video_path, output_path=output_path,
            operation="AU2:audio_overlay",
            details=f"Audio {'replaced' if replace else 'mixed'}" if ok else f"Failed: {msg}",
            duration_sec=time.time() - start,
        )

    # ── IC1: 图片对比 ──

    def compare_images(self, image_a: str, image_b: str,
                       labels: Tuple[str, str] = ("Before", "After")) -> str:
        """
        生成HTML A/B对比页面。

        Args:
            image_a: 图片A路径
            image_b: 图片B路径
            labels: 标签 (默认: Before/After)

        Returns:
            HTML字符串
        """
        import base64

        def img_to_base64(path: str) -> str:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            ext = Path(path).suffix.lower().lstrip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                    "webp": "webp"}.get(ext, "png")
            return f"data:image/{mime};base64,{data}"

        a_b64 = img_to_base64(image_a)
        b_b64 = img_to_base64(image_b)

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Image Comparison</title>
<style>
body {{ margin: 0; padding: 20px; background: #1a1a1a; display: flex; gap: 20px; justify-content: center; }}
.container {{ text-align: center; }}
img {{ max-width: 45vw; max-height: 80vh; border: 2px solid #333; border-radius: 8px; }}
.label {{ color: #fff; font-family: system-ui; font-size: 18px; margin-bottom: 10px; }}
</style>
</head>
<body>
<div class="container">
  <div class="label">{labels[0]}</div>
  <img src="{a_b64}" alt="{labels[0]}">
</div>
<div class="container">
  <div class="label">{labels[1]}</div>
  <img src="{b_b64}" alt="{labels[1]}">
</div>
</body>
</html>"""
        output_path = str(self.output_dir / "comparison.html")
        with open(output_path, "w") as f:
            f.write(html)
        return html

    # ── RE1: 分辨率优化器 ──

    def optimal_resolution(self, platform: str, is_video: bool = True,
                           content_type: str = "default") -> Dict[str, int]:
        """
        获取社交平台最优分辨率。

        Args:
            platform: 平台名 (抖音/小红书/B站/YouTube/Instagram/微信视频号/Twitter)
            is_video: 是否视频
            content_type: 内容类型 (default/cover/story)

        Returns:
            {"width": int, "height": int, "ratio": str}
        """
        specs = PLATFORM_SPECS.get(platform, {})
        media_type = content_type if content_type in specs else ("video" if is_video else "image")
        result = specs.get(media_type, specs.get("video", specs.get("image", {})))
        if not result:
            return {"width": 1920, "height": 1080, "ratio": "16:9", "note": "default fallback"}
        return result

    def list_platforms(self) -> List[str]:
        """列出支持的平台"""
        return list(PLATFORM_SPECS.keys())


# ── Self-test ──

if __name__ == "__main__":
    pp = PostProcessor()
    print("Supported platforms:", pp.list_platforms())
    for p in pp.list_platforms():
        r = pp.optimal_resolution(p)
        print(f"  {p}: {r['width']}x{r['height']} ({r['ratio']})")
