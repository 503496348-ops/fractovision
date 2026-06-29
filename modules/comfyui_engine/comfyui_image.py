"""ComfyUI image generation via Fractovision engine.

Best for local GPU-accelerated image generation with ComfyUI workflows.
Supports multiple image backends through ComfyUI's node-based system.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

# Add Fractovision and OpenMontage to path
FILE_DIR = Path(__file__).resolve().parent
FRACTOVISION_ROOT = FILE_DIR.parent.parent  # fractovision/
OPENMONTAGE_ROOT = FRACTOVISION_ROOT.parent / "OpenMontage"
for p in [str(OPENMONTAGE_ROOT), str(FRACTOVISION_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from tools.base_tool import (
        BaseTool,
        Determinism,
        ExecutionMode,
        ResourceProfile,
        RetryPolicy,
        ToolResult,
        ToolRuntime,
        ToolStability,
        ToolStatus,
        ToolTier,
    )
except ImportError:
    # Fallback: minimal stubs if OpenMontage not available
    from dataclasses import dataclass, field
    from enum import Enum
    from typing import Any, Optional
    
    class ToolTier(str, Enum):
        CORE = "core"
        VOICE = "voice"
        ENHANCE = "enhance"
        GENERATE = "generate"
        SOURCE = "source"
        ANALYZE = "analyze"
        PUBLISH = "publish"
    
    class ToolStability(str, Enum):
        EXPERIMENTAL = "experimental"
        BETA = "beta"
        PRODUCTION = "production"
    
    class ToolStatus(str, Enum):
        AVAILABLE = "available"
        UNAVAILABLE = "unavailable"
        DEGRADED = "degraded"
    
    class ToolRuntime(str, Enum):
        LOCAL = "local"
        LOCAL_GPU = "local_gpu"
        API = "api"
        HYBRID = "hybrid"
    
    class ExecutionMode(str, Enum):
        SYNC = "sync"
        ASYNC = "async"
    
    class Determinism(str, Enum):
        DETERMINISTIC = "deterministic"
        SEEDED = "seeded"
        STOCHASTIC = "stochastic"
    
    class ResumeSupport(str, Enum):
        NONE = "none"
        FROM_START = "from_start"
        FROM_CHECKPOINT = "from_checkpoint"
    
    @dataclass
    class ResourceProfile:
        cpu_cores: int = 1
        ram_mb: int = 512
        vram_mb: int = 0
        disk_mb: int = 100
        network_required: bool = False
    
    @dataclass
    class RetryPolicy:
        max_retries: int = 0
        backoff_seconds: float = 1.0
        retryable_errors: list[str] = field(default_factory=list)
    
    @dataclass
    class ToolResult:
        success: bool
        data: dict[str, Any] = field(default_factory=dict)
        artifacts: list[str] = field(default_factory=list)
        error: Optional[str] = None
        cost_usd: float = 0.0
        duration_seconds: float = 0.0
        seed: Optional[int] = None
        model: Optional[str] = None
    
    class BaseTool:
        name: str = ""
        version: str = "0.1.0"
        tier: ToolTier = ToolTier.CORE
        stability: ToolStability = ToolStability.EXPERIMENTAL
        execution_mode: ExecutionMode = ExecutionMode.SYNC
        determinism: Determinism = Determinism.DETERMINISTIC
        runtime: ToolRuntime = ToolRuntime.LOCAL
        dependencies: list[str] = []
        install_instructions: str = ""
        capability: str = "generic"
        provider: str = "openmontage"
        capabilities: list[str] = []
        input_schema: dict = {}
        output_schema: dict = {}
        artifact_schema: dict = {}
        supports: dict[str, Any] = {}
        best_for: list[str] = []
        not_good_for: list[str] = []
        resource_profile: ResourceProfile = ResourceProfile()
        retry_policy: RetryPolicy = RetryPolicy()
        idempotency_key_fields: list[str] = []
        side_effects: list[str] = []
        user_visible_verification: list[str] = []
        
        def get_status(self) -> ToolStatus:
            return ToolStatus.AVAILABLE
        
        def estimate_cost(self, inputs: dict[str, Any]) -> float:
            return 0.0
        
        def estimate_runtime(self, inputs: dict[str, Any]) -> float:
            return 0.0
        
        def execute(self, inputs: dict[str, Any]) -> ToolResult:
            raise NotImplementedError


class ComfyUIImage(BaseTool):
    """ComfyUI-based image generation tool for OpenMontage."""
    
    name = "comfyui_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:torch", "python:PIL"]
    install_instructions = (
        "Install ComfyUI and required custom nodes.\n"
        "  pip install torch torchvision Pillow\n"
        "  git clone https://github.com/comfyanonymous/ComfyUI.git\n"
        "  cd ComfyUI && pip install -r requirements.txt"
    )
    agent_skills = ["comfyui", "fractovision"]

    capabilities = ["text_to_image", "image_to_image", "inpainting", "workflow_image"]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        "inpainting": True,
        "workflow_image": True,
        "custom_nodes": True,
        "local_gpu": True,
        "no_api_key": True,
        "batch_generation": True,
    }
    best_for = [
        "local GPU-accelerated image generation",
        "custom ComfyUI workflows",
        "privacy-sensitive content (no cloud API)",
        "iterative workflow refinement",
        "batch image generation",
    ]
    not_good_for = [
        "cloud-only environments",
        "instant generation (requires GPU setup)",
        "budget-constrained (needs local GPU)",
    ]
    fallback_tools = ["minimax_image", "dalle_image", "sdxl_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt for image generation",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_image", "image_to_image", "inpainting", "workflow_image"],
                "default": "text_to_image",
            },
            "workflow_path": {
                "type": "string",
                "description": "Path to ComfyUI workflow JSON (for workflow_image)",
            },
            "image_path": {
                "type": "string",
                "description": "Input image path (for image_to_image/inpainting)",
            },
            "mask_path": {
                "type": "string",
                "description": "Mask image path (for inpainting)",
            },
            "width": {
                "type": "integer",
                "default": 512,
                "description": "Image width in pixels",
            },
            "height": {
                "type": "integer",
                "default": 512,
                "description": "Image height in pixels",
            },
            "batch_size": {
                "type": "integer",
                "default": 1,
                "description": "Number of images to generate",
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducibility",
            },
            "steps": {
                "type": "integer",
                "default": 20,
                "description": "Number of sampling steps",
            },
            "cfg_scale": {
                "type": "number",
                "default": 7.0,
                "description": "Classifier-free guidance scale",
            },
            "output_path": {
                "type": "string",
                "description": "Output image file path",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2,
        ram_mb=4096,
        vram_mb=4096,  # Minimum 4GB VRAM for image generation
        disk_mb=1024,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["oom", "cuda_error"])
    idempotency_key_fields = ["prompt", "operation", "width", "height", "seed", "steps"]
    side_effects = ["writes image file to output_path", "uses GPU memory"]
    user_visible_verification = ["View generated image for quality and prompt adherence"]

    def get_status(self) -> ToolStatus:
        """Check if ComfyUI and GPU are available."""
        try:
            import torch
            if not torch.cuda.is_available():
                return ToolStatus.UNAVAILABLE
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Local GPU generation is free (excluding electricity)."""
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate runtime based on resolution and steps."""
        width = inputs.get("width", 512)
        height = inputs.get("height", 512)
        steps = inputs.get("steps", 20)
        batch_size = inputs.get("batch_size", 1)
        # Rough estimate: 0.5-2 seconds per step at 512x512
        pixels = width * height * steps * batch_size
        return pixels / (512 * 512 * 20) * 1.5

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute ComfyUI image generation."""
        start_time = time.time()
        
        try:
            # Import Fractovision modules
            from modules.comfyui_engine.dag_executor import DAGExecutor
            from modules.comfyui_engine.node_registry import NodeRegistry
            
            prompt = inputs.get("prompt", "")
            operation = inputs.get("operation", "text_to_image")
            width = inputs.get("width", 512)
            height = inputs.get("height", 512)
            batch_size = inputs.get("batch_size", 1)
            seed = inputs.get("seed")
            steps = inputs.get("steps", 20)
            cfg_scale = inputs.get("cfg_scale", 7.0)
            output_path = inputs.get("output_path", "output_image.png")
            
            # Build workflow based on operation
            if operation == "workflow_image":
                workflow_path = inputs.get("workflow_path")
                if not workflow_path:
                    return ToolResult(
                        success=False,
                        error="workflow_path required for workflow_image operation",
                    )
                workflow = self._load_workflow(workflow_path)
            elif operation == "inpainting":
                image_path = inputs.get("image_path")
                mask_path = inputs.get("mask_path")
                if not image_path or not mask_path:
                    return ToolResult(
                        success=False,
                        error="image_path and mask_path required for inpainting",
                    )
                workflow = self._build_inpainting_workflow(
                    prompt=prompt,
                    image_path=image_path,
                    mask_path=mask_path,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                )
            elif operation == "image_to_image":
                image_path = inputs.get("image_path")
                if not image_path:
                    return ToolResult(
                        success=False,
                        error="image_path required for image_to_image",
                    )
                workflow = self._build_img2img_workflow(
                    prompt=prompt,
                    image_path=image_path,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                )
            else:
                workflow = self._build_txt2img_workflow(
                    prompt=prompt,
                    width=width,
                    height=height,
                    batch_size=batch_size,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                )
            
            # Execute via Fractovision DAG executor
            executor = DAGExecutor()
            result = executor.execute(workflow)
            
            if result.get("success"):
                artifacts = result.get("output_files", [output_path])
                return ToolResult(
                    success=True,
                    data={
                        "prompt": prompt,
                        "operation": operation,
                        "width": width,
                        "height": height,
                        "batch_size": batch_size,
                        "steps": steps,
                        "cfg_scale": cfg_scale,
                        "seed": seed,
                    },
                    artifacts=artifacts,
                    cost_usd=0.0,
                    duration_seconds=time.time() - start_time,
                    seed=seed,
                    model="comfyui",
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                    duration_seconds=time.time() - start_time,
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _load_workflow(self, workflow_path: str) -> dict:
        """Load a ComfyUI workflow from JSON file."""
        import json
        with open(workflow_path, "r") as f:
            return json.load(f)

    def _build_txt2img_workflow(
        self,
        prompt: str,
        width: int,
        height: int,
        batch_size: int,
        steps: int,
        cfg_scale: float,
        seed: int | None = None,
    ) -> dict:
        """Build a ComfyUI workflow for text-to-image generation."""
        import random
        
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        
        # Basic text-to-image workflow structure
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg_scale,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1.0,
                    },
                },
                {
                    "id": 2,
                    "type": "EmptyLatentImage",
                    "inputs": {
                        "width": width,
                        "height": height,
                        "batch_size": batch_size,
                    },
                },
                {
                    "id": 3,
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": prompt,
                    },
                },
                {
                    "id": 4,
                    "type": "VAEDecode",
                    "inputs": {},
                },
                {
                    "id": 5,
                    "type": "SaveImage",
                    "inputs": {
                        "filename_prefix": "comfyui_output",
                    },
                },
            ],
            "connections": [
                {"from": [2, 0], "to": [1, 0]},
                {"from": [3, 0], "to": [1, 1]},
                {"from": [1, 0], "to": [4, 0]},
                {"from": [4, 0], "to": [5, 0]},
            ],
        }
        
        return workflow

    def _build_img2img_workflow(
        self,
        prompt: str,
        image_path: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int | None = None,
    ) -> dict:
        """Build a ComfyUI workflow for image-to-image generation."""
        import random
        
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg_scale,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 0.7,
                    },
                },
                {
                    "id": 2,
                    "type": "LoadImage",
                    "inputs": {
                        "image": image_path,
                    },
                },
                {
                    "id": 3,
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": prompt,
                    },
                },
                {
                    "id": 4,
                    "type": "VAEEncode",
                    "inputs": {},
                },
                {
                    "id": 5,
                    "type": "VAEDecode",
                    "inputs": {},
                },
                {
                    "id": 6,
                    "type": "SaveImage",
                    "inputs": {
                        "filename_prefix": "comfyui_img2img",
                    },
                },
            ],
            "connections": [
                {"from": [2, 0], "to": [4, 0]},
                {"from": [4, 0], "to": [1, 0]},
                {"from": [3, 0], "to": [1, 1]},
                {"from": [1, 0], "to": [5, 0]},
                {"from": [5, 0], "to": [6, 0]},
            ],
        }
        
        return workflow

    def _build_inpainting_workflow(
        self,
        prompt: str,
        image_path: str,
        mask_path: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int | None = None,
    ) -> dict:
        """Build a ComfyUI workflow for inpainting."""
        import random
        
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg_scale,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1.0,
                    },
                },
                {
                    "id": 2,
                    "type": "LoadImage",
                    "inputs": {
                        "image": image_path,
                    },
                },
                {
                    "id": 3,
                    "type": "LoadImage",
                    "inputs": {
                        "image": mask_path,
                    },
                },
                {
                    "id": 4,
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": prompt,
                    },
                },
                {
                    "id": 5,
                    "type": "VAEEncodeForInpaint",
                    "inputs": {},
                },
                {
                    "id": 6,
                    "type": "VAEDecode",
                    "inputs": {},
                },
                {
                    "id": 7,
                    "type": "SaveImage",
                    "inputs": {
                        "filename_prefix": "comfyui_inpaint",
                    },
                },
            ],
            "connections": [
                {"from": [2, 0], "to": [5, 0]},
                {"from": [3, 0], "to": [5, 1]},
                {"from": [5, 0], "to": [1, 0]},
                {"from": [4, 0], "to": [1, 1]},
                {"from": [1, 0], "to": [6, 0]},
                {"from": [6, 0], "to": [7, 0]},
            ],
        }
        
        return workflow
