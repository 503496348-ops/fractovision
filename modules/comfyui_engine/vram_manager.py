"""
VRAM Manager — 5态显存管理 + 滞后淘汰策略
融合自 ComfyUI model_management.py 的显存管理架构。
支持 CUDA/MPS/CPU 多后端，自动适配消费级GPU到服务器级配置。
"""

from __future__ import annotations

import enum
import logging
import os
import platform
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VRAMState(enum.Enum):
    """显存使用策略（5态）"""
    DISABLED = 0     # 不使用GPU
    NO_VRAM = 1      # 使用GPU但不驻留显存（适合1GB以下GPU）
    LOW_VRAM = 2     # 最小显存占用（2-4GB GPU）
    NORMAL_VRAM = 3  # 默认平衡模式（6-12GB GPU）
    HIGH_VRAM = 4    # 激进缓存（16GB+ GPU）


@dataclass
class ModelSlot:
    """已加载模型的元数据"""
    model_id: str
    device: str
    memory_bytes: int
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    pinned: bool = False  # 钉住的模型不会被淘汰
    dtype: str = "float16"


class VRAMManager:
    """
    5态显存管理器。

    核心策略：
    1. 自动检测GPU显存容量，选择合适的VRAMState
    2. 滞后淘汰：显存压力变化超过阈值才触发淘汰，防止抖动
    3. 平台差异化：Windows比Linux多预留200MB（驱动开销）
    4. LRU+压力双维度：优先淘汰最久未用的，但压力大时强制淘汰
    5. OOM恢复：检测OOM后自动卸载所有模型，降级到NO_VRAM

    用法：
        mgr = VRAMManager()
        mgr.load_model("unet", model_obj, device="cuda:0")
        # ... 使用模型 ...
        mgr.free_memory(target_bytes=2 * 1024**3)  # 释放2GB
    """

    # 滞后阈值（防抖动）
    PIN_PRESSURE_HYSTERESIS = 256 * 1024 * 1024      # 256MB
    REGISTERABLE_HYSTERESIS = 2048 * 1024 * 1024      # 2GB

    # 平台预留
    EXTRA_RESERVED_VRAM = 400 * 1024 * 1024  # 400MB base
    if platform.system() == "Windows":
        EXTRA_RESERVED_VRAM = 600 * 1024 * 1024  # Windows多200MB

    # 最小可用显存阈值
    MIN_FREE_VRAM = 256 * 1024 * 1024  # 256MB

    def __init__(
        self,
        state: Optional[VRAMState] = None,
        device: str = "cuda:0",
        total_vram_bytes: Optional[int] = None,
        smart_memory: bool = True,
    ):
        self._device = device
        self._smart_memory = smart_memory
        self._slots: Dict[str, ModelSlot] = {}
        self._last_pressure: float = 0.0
        self._oom_count: int = 0

        # 检测显存
        if total_vram_bytes is not None:
            self._total_vram = total_vram_bytes
        else:
            self._total_vram = self._detect_vram()

        # 自动选择VRAMState
        if state is None:
            self._state = self._auto_select_state()
        else:
            self._state = state

        logger.info(
            f"[VRAM] Initialized: state={self._state.name}, "
            f"total={self._total_vram / 1024**3:.1f}GB, device={device}"
        )

    def _detect_vram(self) -> int:
        """检测GPU显存容量"""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.get_device_properties(self._device).total_mem
        except ImportError:
            pass

        # 尝试 nvidia-smi
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,nounits,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                mb = int(result.stdout.strip().split("\n")[0])
                return mb * 1024 * 1024
        except Exception:
            pass

        logger.warning("[VRAM] Cannot detect GPU memory, assuming 8GB")
        return 8 * 1024 ** 3

    def _auto_select_state(self) -> VRAMState:
        """根据显存容量自动选择策略"""
        gb = self._total_vram / (1024 ** 3)
        if gb < 1:
            return VRAMState.NO_VRAM
        elif gb < 4:
            return VRAMState.LOW_VRAM
        elif gb < 16:
            return VRAMState.NORMAL_VRAM
        else:
            return VRAMState.HIGH_VRAM

    @property
    def state(self) -> VRAMState:
        return self._state

    @property
    def total_vram(self) -> int:
        return self._total_vram

    @property
    def used_vram(self) -> int:
        """当前已用显存（模型占用估算）"""
        return sum(s.memory_bytes for s in self._slots.values())

    @property
    def free_vram(self) -> int:
        """可用显存"""
        return max(0, self._total_vram - self.used_vram - self.EXTRA_RESERVED_VRAM)

    def load_model(
        self,
        model_id: str,
        model_obj: Any,
        device: Optional[str] = None,
        memory_bytes: Optional[int] = None,
        pinned: bool = False,
        dtype: str = "float16",
    ) -> None:
        """
        加载模型到显存。

        Args:
            model_id: 模型唯一标识
            model_obj: 模型对象（需要有 .to(device) 方法）
            device: 目标设备，默认使用初始化时的设备
            memory_bytes: 预估显存占用。为 None 时尝试自动估算
            pinned: 是否钉住（不被淘汰）
            dtype: 数据类型
        """
        target_device = device or self._device

        if memory_bytes is None:
            memory_bytes = self._estimate_model_memory(model_obj)

        # 检查是否需要先释放显存
        if self._state != VRAMState.HIGH_VRAM:
            needed_free = memory_bytes - self.free_vram
            if needed_free > 0:
                self.free_memory(target_bytes=needed_free)

        # 加载
        if hasattr(model_obj, "to"):
            model_obj.to(target_device)

        self._slots[model_id] = ModelSlot(
            model_id=model_id,
            device=target_device,
            memory_bytes=memory_bytes,
            pinned=pinned,
            dtype=dtype,
        )
        logger.info(f"[VRAM] Loaded '{model_id}': {memory_bytes / 1024**2:.0f}MB on {target_device}")

    def unload_model(self, model_id: str) -> Optional[Any]:
        """卸载模型，释放显存"""
        slot = self._slots.pop(model_id, None)
        if slot:
            logger.info(f"[VRAM] Unloaded '{model_id}': freed {slot.memory_bytes / 1024**2:.0f}MB")
        return slot

    def free_memory(self, target_bytes: int = 0) -> int:
        """
        释放显存，淘汰最久未用的非钉住模型。

        Args:
            target_bytes: 目标释放量。0 = 释放所有非钉住模型。

        Returns:
            实际释放的字节数
        """
        freed = 0
        # 按 last_used 排序，优先淘汰最久未用的
        candidates = sorted(
            [s for s in self._slots.values() if not s.pinned],
            key=lambda s: s.last_used,
        )

        for slot in candidates:
            if target_bytes > 0 and freed >= target_bytes:
                break
            self._slots.pop(slot.model_id)
            freed += slot.memory_bytes
            logger.debug(f"[VRAM] Evicted '{slot.model_id}': {slot.memory_bytes / 1024**2:.0f}MB")

        # CUDA 同步释放
        if freed > 0:
            self._sync_cuda()

        return freed

    def touch(self, model_id: str) -> None:
        """更新模型的最后使用时间"""
        if model_id in self._slots:
            self._slots[model_id].last_used = time.time()

    def handle_oom(self) -> None:
        """OOM 恢复：卸载所有模型，降级状态"""
        self._oom_count += 1
        logger.warning(f"[VRAM] OOM detected (count={self._oom_count}), unloading all models")
        self.free_memory(target_bytes=0)

        if self._oom_count >= 3 and self._state != VRAMState.NO_VRAM:
            old_state = self._state
            self._state = VRAMState(max(0, self._state.value - 1))
            logger.warning(f"[VRAM] Degrading state: {old_state.name} → {self._state.name}")

    def get_pressure(self) -> float:
        """返回当前显存压力 (0.0 - 1.0)"""
        if self._total_vram == 0:
            return 1.0
        return self.used_vram / self._total_vram

    def should_evict(self) -> bool:
        """基于滞后阈值判断是否需要淘汰"""
        pressure = self.get_pressure()
        delta = abs(pressure - self._last_pressure)
        if delta < self.PIN_PRESSURE_HYSTERESIS / self._total_vram:
            return False
        if pressure > 0.85:  # 85%以上强制淘汰
            self._last_pressure = pressure
            return True
        return False

    def _estimate_model_memory(self, model_obj: Any) -> int:
        """估算模型显存占用"""
        try:
            import torch
            if isinstance(model_obj, torch.nn.Module):
                total = sum(p.numel() * p.element_size() for p in model_obj.parameters())
                total += sum(b.numel() * b.element_size() for b in model_obj.buffers())
                return int(total * 1.1)  # +10% overhead
        except (ImportError, AttributeError):
            pass
        return 512 * 1024 * 1024  # 默认512MB

    def _sync_cuda(self) -> None:
        """同步CUDA释放"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass

    def summary(self) -> Dict[str, Any]:
        """返回管理器状态摘要"""
        return {
            "state": self._state.name,
            "total_vram_gb": round(self._total_vram / 1024**3, 1),
            "used_vram_gb": round(self.used_vram / 1024**3, 1),
            "free_vram_gb": round(self.free_vram / 1024**3, 1),
            "pressure": f"{self.get_pressure():.1%}",
            "loaded_models": len(self._slots),
            "oom_count": self._oom_count,
            "models": {mid: {"size_mb": round(s.memory_bytes / 1024**2), "pinned": s.pinned}
                       for mid, s in self._slots.items()},
        }
