from pathlib import Path
from modules.comfyui_engine.lora_manifest import build_manifest_entry, normalize_base_model, route_loras

def test_normalize_base_model_aliases():
    assert normalize_base_model('Qwen-Image-v1') == 'qwen'
    assert normalize_base_model('Z Image Turbo') == 'z_image'

def test_build_and_route_lora(tmp_path: Path):
    asset_path = tmp_path / 'adapter.safetensors'
    asset_path.write_bytes(b'weights')
    asset = build_manifest_entry(asset_path, base_model='qwen-image', trigger_words=['ink'])
    assert len(asset.sha256) == 64
    assert route_loras([asset], 'qwen')[0].trigger_words == ('ink',)
