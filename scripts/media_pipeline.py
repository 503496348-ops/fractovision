"""
MiniMax Creative — Media Pipeline
==================================
Unified pipeline for image/video/audio/music generation via MiniMax API.

Features:
- Type-based routing (image → /image, video → /video, etc.)
- Batch processing with progress tracking
- Output metadata collection
- Error retry with exponential backoff
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    MUSIC = "music"


@dataclass
class MediaTask:
    """Single media generation task."""
    task_id: str
    media_type: MediaType
    prompt: str
    params: dict = field(default_factory=dict)
    status: str = "pending"
    output_url: str = ""
    output_path: str = ""
    error: str = ""
    retries: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "media_type": self.media_type.value,
            "prompt": self.prompt[:100],
            "status": self.status,
            "output_url": self.output_url,
            "error": self.error,
            "retries": self.retries,
        }


@dataclass
class MediaBatch:
    """Batch media generation with progress tracking."""
    batch_id: str
    tasks: list[MediaTask] = field(default_factory=list)
    completed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def progress(self) -> float:
        return (self.completed + self.failed) / max(self.total, 1) * 100

    def add_task(self, media_type: MediaType, prompt: str, **params):
        task = MediaTask(
            task_id=f"{self.batch_id}_{len(self.tasks)}",
            media_type=media_type,
            prompt=prompt,
            params=params,
        )
        self.tasks.append(task)

    def summary(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "progress": f"{self.progress:.0f}%",
            "tasks": [t.to_dict() for t in self.tasks],
        }


# ──── API Parameter Builders ────

def build_image_params(prompt: str, **kwargs) -> dict:
    return {"model": "image-01", "prompt": prompt,
            "width": kwargs.get("width", 1024), "height": kwargs.get("height", 1024)}


def build_video_params(prompt: str, **kwargs) -> dict:
    return {"model": "video-01", "prompt": prompt,
            "duration": kwargs.get("duration", 5), "resolution": kwargs.get("resolution", "720p")}


def build_audio_params(text: str, **kwargs) -> dict:
    return {"model": "speech-01", "text": text,
            "voice_id": kwargs.get("voice_id", "female-1"), "speed": kwargs.get("speed", 1.0)}


def build_music_params(prompt: str, **kwargs) -> dict:
    return {"model": "music-01", "prompt": prompt,
            "duration": kwargs.get("duration", 30)}


PARAM_BUILDERS = {
    MediaType.IMAGE: build_image_params,
    MediaType.VIDEO: build_video_params,
    MediaType.AUDIO: build_audio_params,
    MediaType.MUSIC: build_music_params,
}


if __name__ == "__main__":
    batch = MediaBatch(batch_id="demo")
    batch.add_task(MediaType.IMAGE, "一只猫在月光下")
    batch.add_task(MediaType.VIDEO, "日出延时摄影")
    batch.add_task(MediaType.AUDIO, "你好，欢迎使用MiniMax", voice_id="male-1")
    batch.add_task(MediaType.MUSIC, "轻快的电子音乐")
    print(json.dumps(batch.summary(), ensure_ascii=False, indent=2))
