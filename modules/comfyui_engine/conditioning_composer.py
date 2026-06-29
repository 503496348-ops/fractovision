"""
Conditioning Composer — 多模态条件组合引擎
融合自 ComfyUI 的 ConditioningCombine/Concat/Area/Mask/TimestepRange 节点系列。
支持多提示词混合、区域控制、时间步调度、空间遮罩。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class BlendMode(Enum):
    """条件混合模式"""
    REPLACE = "replace"       # 替换
    ADD = "add"               # 叠加
    AVERAGE = "average"       # 加权平均
    CONCAT = "concat"         # 拼接
    MASKED = "masked"         # 遮罩混合


@dataclass
class Area:
    """空间区域定义"""
    x: int
    y: int
    width: int
    height: int
    strength: float = 1.0


@dataclass
class TimestepRange:
    """时间步范围（用于分阶段条件控制）"""
    start: float = 0.0  # 0.0 = 去噪开始
    end: float = 1.0    # 1.0 = 去噪结束
    strength: float = 1.0


@dataclass
class ConditioningBlock:
    """条件块"""
    embedding: Any  # CLIP 文本嵌入向量
    pooled_output: Optional[Any] = None
    area: Optional[Area] = None
    timestep_range: Optional[TimestepRange] = None
    mask: Optional[Any] = None  # 空间遮罩 (H, W) float32
    weight: float = 1.0


@dataclass
class ControlNetConfig:
    """ControlNet 配置"""
    control_net: Any  # ControlNet 模型对象
    image: Any        # 控制图像 (H, W, C) 或 (B, H, W, C)
    strength: float = 1.0
    start_percent: float = 0.0
    end_percent: float = 1.0


@dataclass
class LoRAConfig:
    """LoRA 配置"""
    lora_obj: Any       # LoRA 模型对象
    strength: float = 1.0


class ConditioningComposer:
    """
    多模态条件组合器。

    能力：
    1. Combine：多个条件加权混合
    2. Concat：条件序列拼接
    3. Area：将条件绑定到图像特定区域
    4. Mask：用空间遮罩控制条件作用区域
    5. TimestepRange：在去噪的不同阶段使用不同条件
    6. Set：将条件与特定模型/CLIP绑定

    典型用法：
        composer = ConditioningComposer()
        result = composer.combine(
            composer.set_area(cond_a, Area(0, 0, 512, 512)),
            composer.set_area(cond_b, Area(512, 0, 512, 512)),
        )
    """

    def combine(
        self,
        *blocks: ConditioningBlock,
        mode: BlendMode = BlendMode.AVERAGE,
        weights: Optional[List[float]] = None,
    ) -> ConditioningBlock:
        """
        组合多个条件块。

        Args:
            blocks: 条件块列表
            mode: 混合模式
            weights: 加权混合时的权重列表（默认均等）

        Returns:
            组合后的条件块
        """
        if not blocks:
            raise ValueError("At least one conditioning block required")

        if len(blocks) == 1:
            return blocks[0]

        if mode == BlendMode.REPLACE:
            return blocks[-1]

        if mode == BlendMode.CONCAT:
            return self._concat(blocks)

        if mode == BlendMode.AVERAGE:
            return self._weighted_average(blocks, weights)

        if mode == BlendMode.ADD:
            return self._add(blocks, weights)

        if mode == BlendMode.MASKED:
            return self._masked_blend(blocks, weights)

        raise ValueError(f"Unknown blend mode: {mode}")

    def set_area(self, block: ConditioningBlock, area: Area) -> ConditioningBlock:
        """将条件绑定到指定区域"""
        return ConditioningBlock(
            embedding=block.embedding,
            pooled_output=block.pooled_output,
            area=area,
            timestep_range=block.timestep_range,
            mask=block.mask,
            weight=block.weight,
        )

    def set_timestep_range(
        self, block: ConditioningBlock, start: float, end: float, strength: float = 1.0
    ) -> ConditioningBlock:
        """设置时间步范围"""
        return ConditioningBlock(
            embedding=block.embedding,
            pooled_output=block.pooled_output,
            area=block.area,
            timestep_range=TimestepRange(start=start, end=end, strength=strength),
            mask=block.mask,
            weight=block.weight,
        )

    def set_mask(self, block: ConditioningBlock, mask: Any) -> ConditioningBlock:
        """设置空间遮罩"""
        return ConditioningBlock(
            embedding=block.embedding,
            pooled_output=block.pooled_output,
            area=block.area,
            timestep_range=block.timestep_range,
            mask=mask,
            weight=block.weight,
        )

    def set_weight(self, block: ConditioningBlock, weight: float) -> ConditioningBlock:
        """设置权重"""
        return ConditioningBlock(
            embedding=block.embedding,
            pooled_output=block.pooled_output,
            area=block.area,
            timestep_range=block.timestep_range,
            mask=block.mask,
            weight=weight,
        )

    def _concat(self, blocks: Tuple[ConditioningBlock, ...]) -> ConditioningBlock:
        """拼接条件（用于多区域/多阶段）"""
        # 收集所有区域和遮罩
        areas = [b.area for b in blocks if b.area is not None]
        masks = [b.mask for b in blocks if b.mask is not None]
        ranges = [b.timestep_range for b in blocks if b.timestep_range is not None]

        logger.debug(f"[Composer] Concat: {len(blocks)} blocks, {len(areas)} areas, {len(ranges)} ranges")

        # 返回第一个块作为基础，附加元数据
        return ConditioningBlock(
            embedding=blocks[0].embedding,
            pooled_output=blocks[0].pooled_output,
            area=areas[0] if areas else None,
            timestep_range=ranges[0] if ranges else None,
            mask=masks[0] if masks else None,
            weight=1.0,
        )

    def _weighted_average(
        self, blocks: Tuple[ConditioningBlock, ...], weights: Optional[List[float]]
    ) -> ConditioningBlock:
        """加权平均混合"""
        if weights is None:
            weights = [1.0 / len(blocks)] * len(blocks)

        if len(weights) != len(blocks):
            raise ValueError(f"Weight count ({len(weights)}) != block count ({len(blocks)})")

        total_weight = sum(weights)
        normalized = [w / total_weight for w in weights]

        try:
            import torch
            # 加权平均嵌入向量
            weighted = sum(b.embedding * w for b, w in zip(blocks, normalized))
            pooled = None
            if blocks[0].pooled_output is not None:
                pooled = sum(b.pooled_output * w for b, w in zip(blocks, normalized))

            return ConditioningBlock(
                embedding=weighted,
                pooled_output=pooled,
                weight=1.0,
            )
        except ImportError:
            # 非PyTorch环境，返回权重最大的
            max_idx = normalized.index(max(normalized))
            return blocks[max_idx]

    def _add(
        self, blocks: Tuple[ConditioningBlock, ...], weights: Optional[List[float]]
    ) -> ConditioningBlock:
        """叠加混合"""
        if weights is None:
            weights = [1.0] * len(blocks)

        try:
            import torch
            weighted = sum(b.embedding * w for b, w in zip(blocks, weights))
            pooled = None
            if blocks[0].pooled_output is not None:
                pooled = sum(b.pooled_output * w for b, w in zip(blocks, weights))
            return ConditioningBlock(embedding=weighted, pooled_output=pooled, weight=1.0)
        except ImportError:
            max_idx = weights.index(max(weights))
            return blocks[max_idx]

    def _masked_blend(
        self, blocks: Tuple[ConditioningBlock, ...], weights: Optional[List[float]]
    ) -> ConditioningBlock:
        """遮罩混合"""
        if len(blocks) < 2:
            raise ValueError("Masked blend requires at least 2 blocks")
        if any(b.mask is None for b in blocks[:2]):
            logger.warning("[Composer] Masked blend but blocks lack masks, falling back to average")
            return self._weighted_average(blocks, weights)

        # 用第一个块的遮罩作为混合因子
        mask = blocks[0].mask

        try:
            import torch
            inv_mask = 1.0 - mask
            blended = blocks[0].embedding * mask + blocks[1].embedding * inv_mask
            pooled = None
            if blocks[0].pooled_output is not None:
                pooled = blocks[0].pooled_output * mask + blocks[1].pooled_output * inv_mask
            return ConditioningBlock(embedding=blended, pooled_output=pooled, weight=1.0)
        except ImportError:
            return blocks[0]

    def apply_controlnet(
        self,
        conditioning: ConditioningBlock,
        controlnet_config: ControlNetConfig,
    ) -> ConditioningBlock:
        """
        注入 ControlNet 条件。
        将控制图像经 ControlNet 编码后叠加到 conditioning 的 embedding 上。
        """
        try:
            import torch
            cn = controlnet_config.control_net
            img = controlnet_config.image

            if hasattr(cn, 'get_control'):
                control_cond = cn.get_control(
                    img, controlnet_config.strength,
                    controlnet_config.start_percent,
                    controlnet_config.end_percent,
                )
            elif callable(cn):
                control_cond = cn(img, strength=controlnet_config.strength)
            else:
                logger.warning("[Composer] ControlNet model not callable, skipping")
                return conditioning

            new_embedding = conditioning.embedding
            if control_cond is not None:
                if isinstance(control_cond, torch.Tensor):
                    new_embedding = conditioning.embedding + control_cond * controlnet_config.strength
                elif isinstance(control_cond, (list, tuple)):
                    for ctrl in control_cond:
                        if isinstance(ctrl, torch.Tensor):
                            new_embedding = new_embedding + ctrl * controlnet_config.strength

            return ConditioningBlock(
                embedding=new_embedding,
                pooled_output=conditioning.pooled_output,
                area=conditioning.area,
                timestep_range=conditioning.timestep_range,
                mask=conditioning.mask,
                weight=conditioning.weight,
            )
        except ImportError:
            logger.warning("[Composer] torch not available, ControlNet skipped")
            return conditioning
        except Exception as e:
            logger.error(f"[Composer] ControlNet apply failed: {e}")
            return conditioning

    def stack_lora(
        self,
        model: Any,
        clip: Any,
        lora_configs: List[LoRAConfig],
    ) -> Tuple[Any, Any]:
        """
        堆叠多个 LoRA 权重到模型和 CLIP 上。
        按顺序应用，后应用的覆盖前面的同名参数。

        Args:
            model: 扩散模型对象
            clip: CLIP 文本编码器对象
            lora_configs: LoRA 配置列表（按应用顺序）

        Returns:
            (patched_model, patched_clip) 元组
        """
        current_model = model
        current_clip = clip

        for cfg in lora_configs:
            try:
                if hasattr(cfg.lora_obj, 'apply'):
                    current_model, current_clip = cfg.lora_obj.apply(
                        current_model, current_clip, cfg.strength
                    )
                elif callable(cfg.lora_obj):
                    result = cfg.lora_obj(current_model, current_clip, cfg.strength)
                    if isinstance(result, tuple) and len(result) == 2:
                        current_model, current_clip = result
                else:
                    logger.warning(f"[Composer] LoRA object not callable: {type(cfg.lora_obj)}")
                logger.debug(f"[Composer] Applied LoRA (strength={cfg.strength})")
            except Exception as e:
                logger.error(f"[Composer] LoRA apply failed: {e}")
                continue

        return current_model, current_clip

    def apply_multiple_controlnets(
        self,
        conditioning: ConditioningBlock,
        controlnet_configs: List[ControlNetConfig],
    ) -> ConditioningBlock:
        """依次应用多个 ControlNet（叠加效果）"""
        result = conditioning
        for cfg in controlnet_configs:
            result = self.apply_controlnet(result, cfg)
        return result

    def serialize(self, block: ConditioningBlock) -> Dict[str, Any]:
        """序列化条件块（用于保存工作流）"""
        return {
            "weight": block.weight,
            "has_area": block.area is not None,
            "has_mask": block.mask is not None,
            "has_timestep_range": block.timestep_range is not None,
            "area": {
                "x": block.area.x, "y": block.area.y,
                "w": block.area.width, "h": block.area.height,
                "strength": block.area.strength,
            } if block.area else None,
            "timestep_range": {
                "start": block.timestep_range.start,
                "end": block.timestep_range.end,
                "strength": block.timestep_range.strength,
            } if block.timestep_range else None,
        }
