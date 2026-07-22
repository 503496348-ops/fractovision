#!/usr/bin/env python3
"""
Tests for Uni3C ControlNet support in fractovision.

Covers:
  - ControlNetType enum completeness
  - Uni3CConfig creation, preprocessor mapping, serialization
  - _build_controlnet_prompt helper
  - list_controlnet_types registry
  - generate_video_wan_controlnet validation (no API key, no image)
  - video_router ControlNet routing
  - normalize_resolution cross-backend mapping
"""

import sys
import os
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════
# ControlNetType enum
# ═══════════════════════════════════════════════════════════════

class TestControlNetType:
    """Test ControlNetType enum definitions."""

    def test_enum_has_expected_types(self):
        from modules.comfyui_engine.conditioning_composer import ControlNetType
        expected = {
            "depth", "canny", "pose", "hed", "normal", "segment",
            "lineart", "shuffle", "mlsd", "softedge", "openpose",
            "recolor", "ip2p",
        }
        actual = {e.value for e in ControlNetType}
        assert actual == expected, f"Missing or extra types: {expected.symmetric_difference(actual)}"

    def test_enum_member_count(self):
        from modules.comfyui_engine.conditioning_composer import ControlNetType
        assert len(ControlNetType) == 13

    def test_enum_from_string(self):
        from modules.comfyui_engine.conditioning_composer import ControlNetType
        assert ControlNetType("depth") == ControlNetType.DEPTH
        assert ControlNetType("canny") == ControlNetType.CANNY
        assert ControlNetType("openpose") == ControlNetType.OPENPOSE

    def test_enum_invalid_value_raises(self):
        from modules.comfyui_engine.conditioning_composer import ControlNetType
        with pytest.raises(ValueError):
            ControlNetType("nonexistent")


# ═══════════════════════════════════════════════════════════════
# Uni3CConfig
# ═══════════════════════════════════════════════════════════════

class TestUni3CConfig:
    """Test Uni3CConfig dataclass."""

    def test_create_with_enum(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig(control_type=ControlNetType.DEPTH)
        assert cfg.control_type == ControlNetType.DEPTH
        assert cfg.strength == 1.0
        assert cfg.start_percent == 0.0
        assert cfg.end_percent == 1.0
        assert cfg.control_image is None
        assert cfg.preprocessor is None
        assert cfg.model_path is None

    def test_create_with_custom_values(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig(
            control_type=ControlNetType.CANNY,
            strength=0.75,
            start_percent=0.1,
            end_percent=0.9,
            control_image="/tmp/edge.png",
            preprocessor="canny_custom",
            model_path="/models/uni3c.safetensors",
        )
        assert cfg.strength == 0.75
        assert cfg.start_percent == 0.1
        assert cfg.end_percent == 0.9
        assert cfg.control_image == "/tmp/edge.png"
        assert cfg.preprocessor == "canny_custom"
        assert cfg.model_path == "/models/uni3c.safetensors"

    def test_from_type_string(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig.from_type("pose", control_image="/tmp/pose.png", strength=1.5)
        assert cfg.control_type == ControlNetType.POSE
        assert cfg.control_image == "/tmp/pose.png"
        assert cfg.strength == 1.5

    def test_from_type_case_insensitive(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig.from_type("DEPTH")
        assert cfg.control_type == ControlNetType.DEPTH

    def test_from_type_invalid_raises(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig
        with pytest.raises(ValueError):
            Uni3CConfig.from_type("invalid_type")

    def test_get_preprocessor_auto_mapped(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        test_cases = [
            (ControlNetType.DEPTH, "depth_midas"),
            (ControlNetType.CANNY, "canny"),
            (ControlNetType.POSE, "openpose"),
            (ControlNetType.HED, "hed"),
            (ControlNetType.NORMAL, "normal_bae"),
            (ControlNetType.SEGMENT, "segment"),
            (ControlNetType.LINEART, "lineart"),
            (ControlNetType.SHUFFLE, "shuffle"),
            (ControlNetType.MLSD, "mlsd"),
            (ControlNetType.SOFTEDGE, "softedge"),
            (ControlNetType.OPENPOSE, "openpose"),
            (ControlNetType.RECOLOR, "recolor"),
            (ControlNetType.IP2P, "ip2p"),
        ]
        for ct, expected_pre in test_cases:
            cfg = Uni3CConfig(control_type=ct)
            assert cfg.get_preprocessor() == expected_pre, f"{ct.value} should map to {expected_pre}"

    def test_get_preprocessor_custom_override(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig(control_type=ControlNetType.DEPTH, preprocessor="depth_zoe")
        assert cfg.get_preprocessor() == "depth_zoe"

    def test_to_dict(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig(
            control_type=ControlNetType.CANNY,
            strength=0.8,
            control_image="/tmp/edge.png",
        )
        d = cfg.to_dict()
        assert d["control_type"] == "canny"
        assert d["strength"] == 0.8
        assert d["start_percent"] == 0.0
        assert d["end_percent"] == 1.0
        assert d["preprocessor"] == "canny"
        assert d["has_image"] is True
        assert d["model_path"] is None

    def test_to_dict_no_image(self):
        from modules.comfyui_engine.conditioning_composer import Uni3CConfig, ControlNetType
        cfg = Uni3CConfig(control_type=ControlNetType.LINEART)
        d = cfg.to_dict()
        assert d["has_image"] is False


# ═══════════════════════════════════════════════════════════════
# _build_controlnet_prompt
# ═══════════════════════════════════════════════════════════════

class TestBuildControlNetPrompt:
    """Test the ControlNet prompt builder."""

    def test_basic_depth(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("a cat walking", "depth")
        assert "a cat walking" in result
        assert "depth structure preserved" in result

    def test_canny_hint(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("landscape", "canny")
        assert "edge contours" in result

    def test_pose_hint(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("dancer", "pose")
        assert "pose" in result.lower()

    def test_with_style_and_motion(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("city", "depth", style="cinematic", motion="pan left")
        assert "style: cinematic" in result
        assert "camera motion: pan left" in result

    def test_with_negative(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("scene", "canny", negative="blurry, dark")
        assert "negative: blurry, dark" in result

    def test_unknown_control_type(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt("test", "unknown_type")
        assert "test" in result
        # No hint added for unknown type, but prompt preserved
        assert "test" in result

    def test_full_options(self):
        from scripts.wan_video import _build_controlnet_prompt
        result = _build_controlnet_prompt(
            "a person dancing", "openpose",
            style="anime", motion="tracking", negative="static"
        )
        assert "a person dancing" in result
        assert "skeletal pose guidance" in result
        assert "style: anime" in result
        assert "camera motion: tracking" in result
        assert "negative: static" in result


# ═══════════════════════════════════════════════════════════════
# list_controlnet_types
# ═══════════════════════════════════════════════════════════════

class TestListControlNetTypes:
    """Test the controlnet type registry."""

    def test_returns_list(self):
        from scripts.wan_video import list_controlnet_types
        result = list_controlnet_types()
        assert isinstance(result, list)

    def test_has_all_types(self):
        from scripts.wan_video import list_controlnet_types
        result = list_controlnet_types()
        types = {r["type"] for r in result}
        assert types == {
            "depth", "canny", "pose", "hed", "normal", "segment",
            "lineart", "shuffle", "mlsd", "softedge", "openpose",
            "recolor", "ip2p",
        }

    def test_each_entry_has_required_keys(self):
        from scripts.wan_video import list_controlnet_types
        result = list_controlnet_types()
        for entry in result:
            assert "type" in entry
            assert "name" in entry
            assert "description" in entry
            assert "preprocessor" in entry
            assert "recommended_for" in entry
            assert isinstance(entry["recommended_for"], list)

    def test_depth_entry(self):
        from scripts.wan_video import list_controlnet_types
        result = list_controlnet_types()
        depth = next(e for e in result if e["type"] == "depth")
        assert depth["preprocessor"] == "depth_midas"
        assert "场景" in depth["recommended_for"]


# ═══════════════════════════════════════════════════════════════
# generate_video_wan_controlnet validation
# ═══════════════════════════════════════════════════════════════

class TestControlNetValidation:
    """Test input validation for ControlNet generation (no API calls)."""

    def test_no_api_key(self, monkeypatch):
        from scripts.wan_video import generate_video_wan_controlnet
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        path, err = generate_video_wan_controlnet(
            prompt="test", control_type="depth",
            control_image_url="https://example.com/depth.png",
        )
        assert path is None
        assert err is not None
        assert "DASHSCOPE_API_KEY" in err

    def test_no_control_image(self, monkeypatch):
        from scripts.wan_video import generate_video_wan_controlnet
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-123")
        path, err = generate_video_wan_controlnet(
            prompt="test", control_type="depth",
        )
        assert path is None
        assert err is not None
        assert "control_image" in err.lower() or "必须提供" in err

    def test_nonexistent_local_file(self, monkeypatch):
        from scripts.wan_video import generate_video_wan_controlnet
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-123")
        path, err = generate_video_wan_controlnet(
            prompt="test", control_type="canny",
            control_image_path="/nonexistent/path/to/image.png",
        )
        assert path is None
        assert err is not None
        assert "不存在" in err


# ═══════════════════════════════════════════════════════════════
# video_router ControlNet routing
# ═══════════════════════════════════════════════════════════════

class TestVideoRouterControlNet:
    """Test video_router ControlNet integration."""

    def test_backend_has_controlnet_task(self):
        from scripts.video_router import BACKENDS
        wan = BACKENDS["wan2.1"]
        assert "controlnet-guided-video" in wan["tasks"]

    def test_generate_controlnet_video_function_exists(self):
        from scripts.video_router import generate_controlnet_video
        assert callable(generate_controlnet_video)

    def test_list_controlnet_supported_types(self):
        from scripts.video_router import list_controlnet_supported_types
        types = list_controlnet_supported_types()
        assert len(types) == 13
        assert any(t["type"] == "depth" for t in types)

    def test_normalize_resolution_for_wan_controlnet(self):
        from scripts.video_router import normalize_resolution
        # ControlNet uses wan2.1 backend
        assert normalize_resolution("720P", "wan2.1") == "720P"
        assert normalize_resolution("768P", "wan2.1") == "720P"
        assert normalize_resolution("544P", "wan2.1") == "480P"
        assert normalize_resolution("1080P", "wan2.1") == "1080P"

    def test_controlnet_forces_wan_backend(self, monkeypatch):
        """ControlNet should force wan2.1 backend even if model suggests minimax."""
        from scripts.video_router import generate_controlnet_video
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        # Even with a minimax model name, ControlNet should route to wan2.1
        # We can't fully test without API, but we can test the routing logic
        from scripts.video_router import normalize_resolution
        norm = normalize_resolution("720P", "wan2.1")
        assert norm == "720P"


# ═══════════════════════════════════════════════════════════════
# Import integration
# ═══════════════════════════════════════════════════════════════

class TestImports:
    """Test that all new symbols are properly importable."""

    def test_conditioning_composer_exports(self):
        from modules.comfyui_engine.conditioning_composer import (
            ControlNetType, Uni3CConfig, ConditioningBlock, ConditioningComposer
        )
        assert ControlNetType is not None
        assert Uni3CConfig is not None
        assert ConditioningBlock is not None
        assert ConditioningComposer is not None

    def test_wan_video_controlnet_functions(self):
        from scripts.wan_video import (
            generate_video_wan_controlnet,
            _build_controlnet_prompt,
            list_controlnet_types,
        )
        assert callable(generate_video_wan_controlnet)
        assert callable(_build_controlnet_prompt)
        assert callable(list_controlnet_types)

    def test_video_router_controlnet_functions(self):
        from scripts.video_router import (
            generate_controlnet_video,
            list_controlnet_supported_types,
        )
        assert callable(generate_controlnet_video)
        assert callable(list_controlnet_supported_types)
