import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.pipeline_loading_guard import discover_pipeline_layout, validate_attention_backend


def test_discover_flat_pipeline_layout(tmp_path):
    (tmp_path / "model_index.json").write_text("{}")
    (tmp_path / "model.safetensors").write_text("x")
    assert discover_pipeline_layout(tmp_path)["layout"] == "flat"


def test_attention_guard_requires_fallback_for_mixed_dims():
    errors = validate_attention_backend([128, 320], "fa3")
    assert len(errors) == 2
