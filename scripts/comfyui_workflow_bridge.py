#!/usr/bin/env python3
"""ComfyUI workflow bridge.

将外部 workflow JSON 转为 Fractovision 的内部 prompt 兼容格式。
- 支持 UI 格式与 API 格式自动识别
- 支持 dry-run 检查与快速归一化统计
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.comfyui_engine.workflow_queue import WorkflowQueue


def load_workflow(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow must be JSON object")
    return data


def normalize_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    q = WorkflowQueue()
    return q._normalize_workflow(workflow)  # type: ignore[attr-defined]


def run_once(source: str, dry_run: bool, output: str | None) -> int:
    wf = load_workflow(source)
    prompt = normalize_workflow(wf)
    result = {
        "node_count": len(prompt),
        "node_types": sorted({v.get("class_type") for v in prompt.values() if isinstance(v, dict) and "class_type" in v}),
    }
    if output:
        Path(output).write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"normalized workflow saved: {output}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not dry_run else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge external ComfyUI workflow to Fractovision prompt format")
    parser.add_argument("--source", required=True, help="Input workflow JSON path")
    parser.add_argument("--output", help="Optional normalized prompt output path")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print normalized stats")
    args = parser.parse_args()

    return run_once(args.source, dry_run=args.dry_run, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
