#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax 多媒体能力统一封装
=============================
覆盖：图片生成、语音合成、视频生成、音乐生成

所有 API 认证统一走 MINIMAX_API_KEY（兼容 MINIMAX_DOMESTIC_API_KEY）
所有端点均基于 https://api.minimaxi.com

环境变量：
  MINIMAX_API_KEY / MINIMAX_DOMESTIC_API_KEY
  MINIMAX_API_URL  — 默认 https://api.minimaxi.com

视频生成（异步）：
  POST /v1/video_generation        → task_id
  GET  /v1/query/video_generation  → status + file_id
  GET  /v1/files/retrieve          → download_url

图片生成（同步）：
  POST /v1/image_generation        → base64

语音合成（同步）：
  POST /v1/t2a                    → audio binary

音乐生成（异步）：
  POST /v1/music_generation       → task_id
  GET  /v1/music_generation       → status + download_url
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Optional, Literal

try:
    import requests
except ImportError:
    print("❌ requests 库未安装，请运行: pip install requests")
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════
# 通用配置
# ═══════════════════════════════════════════════════════════════

def get_api_key() -> str:
    return os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_DOMESTIC_API_KEY", "")


def get_config() -> dict:
    return {
        "api_key": get_api_key(),
        "api_url": os.environ.get("MINIMAX_API_URL", "https://api.minimaxi.com"),
        "timeout": 120,
    }


# ═══════════════════════════════════════════════════════════════
# 图片生成  image-01（同步，base64）
# ═══════════════════════════════════════════════════════════════

def generate_image(
    prompt: str,
    size: str = "1:1",
    model: str = "image-01",
) -> tuple[Optional[str], Optional[str]]:
    """
    调用 MiniMax image-01 文生图 API。

    参数：
      prompt     — 图片描述文本
      size       — 尺寸比例，如 "1:1", "16:9", "3:4", "小红书", "海报" 等
      model      — 模型名，默认 image-01

    返回：
      (base64_data_url, None)   — 成功，data:image/png;base64,xxxx
      (None, error_str)         — 失败
    """
    cfg = get_config()
    if not cfg["api_key"]:
        return None, "MINIMAX_API_KEY 未设置"

    # 解析尺寸 → aspect_ratio
    ASPECT_RATIO_MAP = {
        "1:1": "1:1", "3:4": "3:4", "16:9": "16:9", "9:16": "9:16",
        "2:3": "2:3", "4:5": "4:5", "5:7": "5:7", "21:9": "21:9",
        "小红书": "3:4", "海报": "2:3", "视频封面": "16:9", "方形": "1:1",
        "手机壁纸": "9:16", "宽屏": "21:9", "横版封面": "16:9",
        "电影感": "21:9", "竖版": "9:16", "横版": "16:9",
        "ins": "1:1", "头像": "1:1",
    }
    ratio_map = {
        "1:1": (1024, 1024), "3:4": (1024, 1365), "16:9": (1024, 576),
        "9:16": (576, 1024), "2:3": (1024, 1536), "4:5": (1024, 1280),
        "5:7": (1024, 1433), "21:9": (1512, 648),
        "小红书": (1024, 1365), "海报": (1024, 1536), "视频封面": (1024, 576),
        "方形": (1024, 1024), "手机壁纸": (576, 1024), "宽屏": (1512, 648),
        "横版封面": (1024, 576), "电影感": (1512, 648), "竖版": (576, 1024),
        "横版": (1024, 576), "ins": (1024, 1024), "头像": (1024, 1024),
    }

    aspect_ratio = ASPECT_RATIO_MAP.get(size, "1:1")
    w, h = ratio_map.get(size, (1024, 1024))

    from math import gcd
    g = gcd(w, h)
    api_ratio = f"{w//g}:{h//g}"

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": api_ratio,
        "response_format": "base64",
    }

    retry_codes = (429, 503)
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                f"{cfg['api_url']}/v1/image_generation",
                headers=headers, json=payload, timeout=cfg["timeout"],
            )
            if resp.status_code in retry_codes and attempt < 3:
                time.sleep(2 ** (attempt - 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            images = data.get("data", {}).get("image_base64", [])
            if images and images[0]:
                return f"data:image/png;base64,{images[0]}", None
            return None, f"API 返回无图片数据: {data}"
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
                continue
            return None, str(e)

    return None, "重试耗尽"


# ═══════════════════════════════════════════════════════════════
# 语音合成  T2A（同步，返回 MP3 bytes）
# ═══════════════════════════════════════════════════════════════

def generate_speech(
    text: str,
    voice_id: str = "female-tianmei",
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: float = 0,
    emotion: str = "neutral",
    model: str = "speech-2.8-hd",
    output_path: Optional[str] = None,
    to_feishu_ogg: bool = False,
) -> tuple[Optional[bytes], Optional[str]]:
    """
    调用 MiniMax 同步语音合成 API。

    参数：
      text        — 要合成的中文文本
      voice_id    — 音色 ID，默认 female-tianmei
      speed       — 语速，默认 1.0
      vol         — 音量，默认 1.0
      pitch       — 音调偏移，默认 0
      emotion     — 情感，默认 neutral（happy/sad/angry 等）
      model       — 模型，默认 speech-2.8-hd
      output_path — 保存路径，不提供则返回 bytes
      to_feishu_ogg — 是否转换为飞书语音气泡格式（.ogg/Opus）

    返回：
      (mp3_bytes, None)        — 成功，原始 MP3
      (file_path_str, None)    — 成功，保存为文件（to_feishu_ogg=True 时为 .ogg 路径）
      (None, error_str)         — 失败
    """
    cfg = get_config()
    if not cfg["api_key"]:
        return None, "MINIMAX_API_KEY 未设置"

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
            "emotion": emotion,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }

    try:
        resp = requests.post(
            f"{cfg['api_url']}/v1/t2a_v2",
            headers=headers, json=payload, timeout=cfg["timeout"],
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                data = resp.json()
                audio_hex = data.get("data", {}).get("audio")
                if not audio_hex:
                    return None, f"JSON 响应无 audio 字段: {data}"
                audio_bytes = bytes.fromhex(audio_hex)
            else:
                audio_bytes = resp.content

            if to_feishu_ogg:
                # 飞书语音气泡只接受 .ogg（Opus），需要转码
                import subprocess as _sub
                import tempfile as _tempfile
                _tmp_mp3 = _tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                _tmp_mp3.write(audio_bytes)
                _tmp_mp3.close()
                _ogg_path = output_path or _tempfile.NamedTemporaryFile(
                    suffix="_feishu.ogg", delete=False
                ).name
                _res = _sub.run(
                    [
                        "ffmpeg", "-y", "-i", _tmp_mp3.name,
                        "-vn", "-c:a", "libopus", "-b:a", "128k",
                        _ogg_path,
                    ],
                    capture_output=True, text=True,
                )
                os.unlink(_tmp_mp3.name)
                if _res.returncode != 0:
                    return None, f"转码为 Ogg 失败: {_res.stderr[-300:]}"
                return _ogg_path, None

            if output_path:
                Path(output_path).write_bytes(audio_bytes)
                return f"✅ 已保存: {output_path} ({len(audio_bytes)//1024} KB)", None
            return audio_bytes, None
        try:
            err = resp.json()
            return None, f"API 错误 {resp.status_code}: {err}"
        except Exception:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════
# 视频生成  Hailuo（异步，轮询 + 下载）
# ═══════════════════════════════════════════════════════════════

def generate_video(
    prompt: str,
    model: str = "MiniMax-Hailuo-2.3",
    duration: int = 6,
    resolution: str = "768P",  # 支持 768P / 1080P（注意大写P）
    callback_url: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 180,
    output_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    调用 MiniMax Hailuo 文生视频 API（异步），轮询直至视频就绪并下载。

    参数：
      prompt         — 视频描述文本
      model          — 模型，默认 MiniMax-Hailuo-2.3（可用：MiniMax-Hailuo-02, T2V-01, T2V-01-Director）
      duration       — 时长（秒），默认 6（模型限制：Hailuo-2.3 支持 6/10s）
      resolution     — 分辨率，默认 720p（720p / 768p / 1080p）
      callback_url   — 回调 URL（可选，不填则本函数轮询）
      poll_interval  — 轮询间隔（秒），默认 5
      poll_timeout   — 轮询超时（秒），默认 180
      output_dir     — 输出目录，默认 ~/Desktop

    返回：
      (local_file_path, None)  — 成功，MP4 文件路径
      (None, error_str)        — 失败
    """
    cfg = get_config()
    if not cfg["api_key"]:
        return None, "MINIMAX_API_KEY 未设置"

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    # Step 1: 创建视频生成任务
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "aigc_watermark": False,
    }
    if callback_url:
        payload["callback_url"] = callback_url

    try:
        resp = requests.post(
            f"{cfg['api_url']}/v1/video_generation",
            headers=headers, json=payload, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id")
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code") != 0 or not task_id:
            return None, f"创建视频任务失败: {data}"
    except Exception as e:
        return None, f"创建视频任务异常: {e}"

    print(f"[Video] task_id={task_id} 开始轮询...", flush=True)

    # Step 2: 轮询任务状态
    start_time = time.time()
    while time.time() - start_time < poll_timeout:
        time.sleep(poll_interval)
        try:
            qresp = requests.get(
                f"{cfg['api_url']}/v1/query/video_generation?task_id={task_id}",
                headers=headers, timeout=15,
            )
            qresp.raise_for_status()
            qdata = qresp.json()
            status = qdata.get("status")
            print(f"[Video] task_id={task_id} status={status}", flush=True)
            if status == "Success":
                file_id = qdata.get("file_id")
                if not file_id:
                    return None, f"视频成功但无 file_id: {qdata}"
                break
            elif status == "Fail":
                err = qdata.get("base_resp", {}).get("status_msg", "unknown")
                return None, f"视频生成失败: {err}"
            # 否则继续等待（Preparing / Queueing / Processing）
        except Exception as e:
            return None, f"轮询异常: {e}"
    else:
        return None, f"轮询超时（{poll_timeout}s），task_id={task_id}"

    # Step 3: 获取下载 URL
    try:
        fresp = requests.get(
            f"{cfg['api_url']}/v1/files/retrieve?file_id={file_id}",
            headers=headers, timeout=15,
        )
        fresp.raise_for_status()
        fdata = fresp.json()
        download_url = fdata.get("file", {}).get("download_url")
        if not download_url:
            return None, f"无 download_url: {fdata}"
    except Exception as e:
        return None, f"获取下载链接异常: {e}"

    # Step 4: 下载视频文件
    try:
        vresp = requests.get(download_url, timeout=120)
        vresp.raise_for_status()
    except Exception as e:
        return None, f"视频下载失败: {e}"

    # 保存
    if output_dir:
        out_dir = Path(output_dir).expanduser()
    else:
        out_dir = Path.home() / "Desktop"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"hailuo_video_{ts}.mp4"
    out_path = str(out_dir / filename)
    Path(out_path).write_bytes(vresp.content)
    size_kb = len(vresp.content) // 1024
    print(f"[Video] ✅ 已保存: {out_path} ({size_kb} KB)", flush=True)
    return out_path, None


# ═══════════════════════════════════════════════════════════════
# 音乐生成  Music-02（异步，轮询 + 下载）
# ═══════════════════════════════════════════════════════════════

def generate_music(
    prompt: str,
    lyrics: str = "",
    is_instrumental: bool = True,
    model: str = "music-2.6",
    output_dir: Optional[str] = None,
    poll_interval: int = 5,
    poll_timeout: int = 120,
) -> tuple[Optional[str], Optional[str]]:
    """
    调用 MiniMax Music-2.6 音乐生成 API（异步）。

    参数：
      prompt     — 音乐描述（如 "Upbeat pop music, summer vibe"）
      lyrics     — 歌词文本（可为空，纯器乐则不填）
      is_instrumental — 是否纯器乐，默认 True（lyrics 非必填时设为 True）
      model      — 模型，默认 music-2.6
      output_dir — 输出目录，默认 ~/Desktop
      poll_interval  — 轮询间隔（秒）
      poll_timeout   — 轮询超时（秒）

    返回：
      (local_file_path, None)  — 成功，MP3 文件路径
      (None, error_str)         — 失败
    """
    cfg = get_config()
    if not cfg["api_key"]:
        return None, "MINIMAX_API_KEY 未设置"

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "is_instrumental": is_instrumental,
    }
    if lyrics:
        payload["lyrics"] = lyrics

    try:
        resp = requests.post(
            f"{cfg['api_url']}/v1/music_generation",
            headers=headers, json=payload, timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id")
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code") != 0 or not task_id:
            return None, f"创建音乐任务失败: {data}"
    except Exception as e:
        return None, f"创建音乐任务异常: {e}"

    print(f"[Music] task_id={task_id} 开始轮询...", flush=True)

    start_time = time.time()
    while time.time() - start_time < poll_timeout:
        time.sleep(poll_interval)
        try:
            qresp = requests.get(
                f"{cfg['api_url']}/v1/music_generation?task_id={task_id}",
                headers=headers, timeout=15,
            )
            qresp.raise_for_status()
            qdata = qresp.json()
            status = qdata.get("status")
            print(f"[Music] task_id={task_id} status={status}", flush=True)
            if status == "Success":
                download_url = qdata.get("audio_url")
                if not download_url:
                    return None, f"音乐成功但无 audio_url: {qdata}"
                break
            elif status == "Fail":
                return None, f"音乐生成失败: {qdata.get('base_resp', {}).get('status_msg')}"
        except Exception as e:
            return None, f"轮询异常: {e}"
    else:
        return None, f"轮询超时（{poll_timeout}s）"

    # 下载
    try:
        vresp = requests.get(download_url, timeout=120)
        vresp.raise_for_status()
    except Exception as e:
        return None, f"音乐下载失败: {e}"

    if output_dir:
        out_dir = Path(output_dir).expanduser()
    else:
        out_dir = Path.home() / "Desktop"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"minimax_music_{ts}.mp3"
    out_path = str(out_dir / filename)
    Path(out_path).write_bytes(vresp.content)
    size_kb = len(vresp.content) // 1024
    print(f"[Music] ✅ 已保存: {out_path} ({size_kb} KB)", flush=True)
    return out_path, None


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MiniMax 多媒体能力测试")
    sub = parser.add_subparsers(dest="cmd")

    p_img = sub.add_parser("image", help="图片生成")
    p_img.add_argument("prompt", help="图片描述")
    p_img.add_argument("--size", default="1:1", help="尺寸比例")

    p_tts = sub.add_parser("speech", help="语音合成")
    p_tts.add_argument("text", help="合成文本")
    p_tts.add_argument("--voice", default="female-tianmei", help="音色ID")
    p_tts.add_argument("--speed", type=float, default=1.0)

    p_vid = sub.add_parser("video", help="视频生成")
    p_vid.add_argument("prompt", help="视频描述")
    p_vid.add_argument("--model", default="MiniMax-Hailuo-2.3")
    p_vid.add_argument("--duration", type=int, default=6)
    p_vid.add_argument("--resolution", default="720p")

    p_mus = sub.add_parser("music", help="音乐生成")
    p_mus.add_argument("prompt", help="音乐描述")

    args = parser.parse_args()

    if args.cmd == "image":
        result, err = generate_image(args.prompt, args.size)
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ base64 length: {len(result)}")

    elif args.cmd == "speech":
        result, err = generate_speech(args.text, args.voice, args.speed)
        if err:
            print(f"❌ {err}")
        else:
            path = str(Path.home() / "Desktop" / "test_speech.mp3")
            Path(path).write_bytes(result)
            print(f"✅ 已保存: {path}")

    elif args.cmd == "video":
        path, err = generate_video(args.prompt, args.model, args.duration, args.resolution)
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 视频路径: {path}")

    elif args.cmd == "music":
        path, err = generate_music(args.prompt)
        if err:
            print(f"❌ {err}")
        else:
            print(f"✅ 音乐路径: {path}")

    else:
        parser.print_help()
