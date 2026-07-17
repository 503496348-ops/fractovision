#!/usr/bin/env python3
"""Fractovision helper bridge for OpenCut task summaries.

Minimal PoC adapter: convert an OpenCut-like summary into Fractovision-friendly payload.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize_summary(summary: dict) -> dict:
    return {
        "source_job_id": summary.get("job_id"),
        "artifact_type": summary.get("type", "summary"),
        "duration_sec": summary.get("summary", {}).get("duration_sec"),
        "frames": summary.get("summary", {}).get("frames"),
        "codec": summary.get("summary", {}).get("codec"),
        "download_url": summary.get("download_url"),
    }


def run_smoke() -> int:
    mock = {
        "job_id": "mock-frac-0001",
        "type": "summary",
        "download_url": None,
        "summary": {"frames": 120, "duration_sec": 8, "codec": "h264"},
    }
    print(json.dumps({"status": "ok", "summary": normalize_summary(mock)}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fractovision OpenCut summary bridge")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--input", default="")
    args = parser.parse_args()
    if args.smoke:
        return run_smoke()
    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
        summary = json.loads(raw)
        print(json.dumps({"status": "ok", "summary": normalize_summary(summary)}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"status": "ok", "summary": normalize_summary({})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
