"""ComfyUI video generation via Fractovision engine.

Best for local GPU-accelerated video generation with ComfyUI workflows.
Supports multiple video backends through ComfyUI's node-based system.
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


class ComfyUIVideo(BaseTool):
    """ComfyUI-based video generation tool for OpenMontage."""
    
    name = "comfyui_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:torch", "python:comfy"]
    install_instructions = (
        "Install ComfyUI and required custom nodes.\n"
        "  pip install torch torchvision\n"
        "  git clone https://github.com/comfyanonymous/ComfyUI.git\n"
        "  cd ComfyUI && pip install -r requirements.txt"
    )
    agent_skills = ["comfyui", "fractovision"]

    capabilities = ["text_to_video", "image_to_video", "workflow_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "workflow_video": True,
        "custom_nodes": True,
        "local_gpu": True,
        "no_api_key": True,
    }
    best_for = [
        "local GPU-accelerated video generation",
        "custom ComfyUI workflows",
        "privacy-sensitive content (no cloud API)",
        "iterative workflow refinement",
    ]
    not_good_for = [
        "cloud-only environments",
        "instant generation (requires GPU setup)",
        "budget-constrained (needs local GPU)",
    ]
    fallback_tools = ["kling_video", "minimax_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt for video generation",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "workflow_video"],
                "default": "text_to_video",
            },
            "workflow_path": {
                "type": "string",
                "description": "Path to ComfyUI workflow JSON (for workflow_video)",
            },
            "image_path": {
                "type": "string",
                "description": "Input image path (for image_to_video)",
            },
            "width": {
                "type": "integer",
                "default": 512,
                "description": "Video width in pixels",
            },
            "height": {
                "type": "integer",
                "default": 512,
                "description": "Video height in pixels",
            },
            "num_frames": {
                "type": "integer",
                "default": 16,
                "description": "Number of frames to generate",
            },
            "fps": {
                "type": "integer",
                "default": 8,
                "description": "Frames per second",
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducibility",
            },
            "output_path": {
                "type": "string",
                "description": "Output video file path",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4,
        ram_mb=8192,
        vram_mb=6144,  # Minimum 6GB VRAM for video generation
        disk_mb=2048,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["oom", "cuda_error"])
    idempotency_key_fields = ["prompt", "operation", "width", "height", "num_frames", "seed"]
    side_effects = ["writes video file to output_path", "uses GPU memory"]
    user_visible_verification = ["Watch generated video for quality and prompt adherence"]

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
        """Estimate runtime based on resolution and frame count."""
        width = inputs.get("width", 512)
        height = inputs.get("height", 512)
        num_frames = inputs.get("num_frames", 16)
        # Rough estimate: 1-3 seconds per frame at 512x512
        pixels = width * height * num_frames
        return pixels / (512 * 512) * 2.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute ComfyUI video generation."""
        start_time = time.time()
        
        try:
            # Import Fractovision modules
            from modules.comfyui_engine.dag_executor import DAGExecutor
            from modules.comfyui_engine.node_registry import NodeRegistry
            
            prompt = inputs.get("prompt", "")
            operation = inputs.get("operation", "text_to_video")
            width = inputs.get("width", 512)
            height = inputs.get("height", 512)
            num_frames = inputs.get("num_frames", 16)
            fps = inputs.get("fps", 8)
            seed = inputs.get("seed")
            output_path = inputs.get("output_path", "output_video.mp4")
            
            # Build workflow based on operation
            if operation == "workflow_video":
                workflow_path = inputs.get("workflow_path")
                if not workflow_path:
                    return ToolResult(
                        success=False,
                        error="workflow_path required for workflow_video operation",
                    )
                workflow = self._load_workflow(workflow_path)
            else:
                workflow = self._build_video_workflow(
                    prompt=prompt,
                    operation=operation,
                    width=width,
                    height=height,
                    num_frames=num_frames,
                    image_path=inputs.get("image_path"),
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
                        "num_frames": num_frames,
                        "fps": fps,
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

    def _build_video_workflow(
        self,
        prompt: str,
        operation: str,
        width: int,
        height: int,
        num_frames: int,
        image_path: str | None = None,
        seed: int | None = None,
    ) -> dict:
        """Build a ComfyUI workflow for video generation."""
        import random
        
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        
        # Basic text-to-video workflow structure
        # This is a simplified example - real workflows would be more complex
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "inputs": {
                        "seed": seed,
                        "steps": 20,
                        "cfg": 7.0,
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
                        "batch_size": num_frames,
                    },
                },
                {
                    "id": 3,
                    "type": "CLIPTextEncode",
                    "inputs": {
                        "text": prompt,
                    },
                },
            ],
            "connections": [
                {"from": [2, 0], "to": [1, 0]},
                {"from": [3, 0], "to": [1, 1]},
            ],
        }
        
        return workflow
