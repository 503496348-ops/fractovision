"""LoRA manifest normalization and routing helpers for media pipelines."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib, json, re
from typing import Dict, Iterable, List
MODEL_ALIASES={'qwen-image':'qwen','qwen':'qwen','z-image':'z_image','zimage':'z_image','sdxl':'sdxl','wan':'wan'}
@dataclass(frozen=True)
class LoraAsset:
    path: str; sha256: str; base_model: str; strength: float = 0.8; trigger_words: tuple[str, ...] = (); metadata: Dict[str, str] | None = None
    def to_dict(self) -> dict:
        d=asdict(self); d['trigger_words']=list(self.trigger_words); return d
def file_sha256(path: str | Path) -> str:
    h=hashlib.sha256(); p=Path(path)
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def normalize_base_model(value: str) -> str:
    key=re.sub(r'[^a-z0-9]+','-', (value or '').lower()).strip('-')
    for prefix, canonical in MODEL_ALIASES.items():
        if key.startswith(prefix): return canonical
    return key or 'unknown'
def build_manifest_entry(path: str | Path, *, base_model: str, strength: float=0.8, trigger_words: Iterable[str]=()) -> LoraAsset:
    p=Path(path)
    return LoraAsset(str(p), file_sha256(p), normalize_base_model(base_model), max(0.0, min(2.0, float(strength))), tuple(t.strip() for t in trigger_words if t and t.strip()), {})
def route_loras(assets: Iterable[LoraAsset], target_model: str) -> List[LoraAsset]:
    target=normalize_base_model(target_model); return [a for a in assets if a.base_model in {target, 'unknown'}]
def save_manifest(assets: Iterable[LoraAsset], output: str | Path) -> Path:
    p=Path(output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps([a.to_dict() for a in assets], ensure_ascii=False, indent=2), encoding='utf-8'); return p
def load_manifest(path: str | Path) -> List[LoraAsset]:
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    return [LoraAsset(path=i['path'], sha256=i['sha256'], base_model=i.get('base_model','unknown'), strength=float(i.get('strength',0.8)), trigger_words=tuple(i.get('trigger_words',())), metadata=i.get('metadata') or {}) for i in data]
