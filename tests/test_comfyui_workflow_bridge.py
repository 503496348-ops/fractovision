import json
from pathlib import Path

from scripts.comfyui_workflow_bridge import normalize_workflow


def test_normalize_api_workflow(tmp_path: Path):
    wf = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
    }
    path = tmp_path / "api.json"
    path.write_text(json.dumps(wf), encoding="utf-8")

    normalized = normalize_workflow(wf)
    assert "1" in normalized and "2" in normalized
    assert normalized["1"]["class_type"] == "KSampler"


def test_normalize_ui_workflow(tmp_path: Path):
    wf = {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["foo.safetensors"]},
            {"id": 2, "type": "KSampler", "widgets_values": [20, "euler"]},
        ],
        "links": [[0, 1, 0, 2, 0, "output"]],
    }
    prompt = normalize_workflow(wf)
    assert len(prompt) == 2
    assert any(v["class_type"] == "CheckpointLoaderSimple" for v in prompt.values())
