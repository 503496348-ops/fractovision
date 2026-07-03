"""Pipeline loading guard for mixed model repository layouts."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

KNOWN_CONFIGS = ("model_index.json", "config.json", "workflow.json", "pipeline.json")


def discover_pipeline_layout(root: str | Path) -> dict[str, object]:
    root = Path(root)
    configs = [str(p.relative_to(root)) for name in KNOWN_CONFIGS for p in root.rglob(name)]
    flat_weights = sorted(str(p.relative_to(root)) for p in root.glob("*.safetensors"))
    nested_weights = sorted(str(p.relative_to(root)) for p in root.rglob("*.safetensors") if p.parent != root)
    layout = "flat" if flat_weights and not nested_weights else "nested" if nested_weights else "metadata-only"
    return {"layout": layout, "configs": sorted(configs), "flat_weights": flat_weights, "nested_weights": nested_weights}


def validate_attention_backend(head_dims: Iterable[int], backend: str) -> list[str]:
    errors: list[str] = []
    dims = list(head_dims)
    if backend.lower() in {"flash3", "fa3"}:
        if any(dim > 256 for dim in dims):
            errors.append("head_dim exceeds fast attention backend limit")
        if len(set(dims)) > 1:
            errors.append("mixed query/key/value head dimensions require math fallback")
    return errors
