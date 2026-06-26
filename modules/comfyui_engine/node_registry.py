"""
Node Registry — 类型化节点注册与I/O系统
融合自 ComfyUI nodes.py 的节点定义模式。
支持自动UI生成、输入验证、序列化/反序列化。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


@dataclass
class InputSpec:
    """输入规格定义"""
    name: str
    type: str  # "INT", "FLOAT", "STRING", "BOOLEAN", "IMAGE", "MODEL", "CONDITIONING", "LATENT", "VAE", "CLIP", "ANY"
    default: Any = None
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    multiline: bool = False
    options: Optional[List[str]] = None  # 下拉选项
    tooltip: str = ""
    force_input: bool = False  # 强制作为输入端口（非UI参数）


@dataclass
class OutputSpec:
    """输出规格定义"""
    name: str
    type: str
    tooltip: str = ""


@dataclass
class NodeDefinition:
    """完整的节点定义"""
    node_id: str
    display_name: str
    category: str
    func_name: str
    inputs: List[InputSpec]
    outputs: List[OutputSpec]
    description: str = ""
    is_output_node: bool = False  # 是否为终端节点（如保存图片）
    deprecated: bool = False
    experimental: bool = False


# 多媒体类型常量
MEDIA_TYPES = {
    "IMAGE": "图像张量 (B, H, W, C) float32 [0,1]",
    "LATENT": "潜在空间张量",
    "CONDITIONING": "文本条件嵌入",
    "MODEL": "扩散模型",
    "CLIP": "CLIP 文本编码器",
    "VAE": "变分自编码器",
    "AUDIO": "音频张量 (C, T) float32",
    "VIDEO": "视频张量 (B, T, H, W, C)",
    "MASK": "遮罩张量 (B, H, W) float32 [0,1]",
    "STRING": "文本字符串",
    "INT": "整数",
    "FLOAT": "浮点数",
    "BOOLEAN": "布尔值",
    "ANY": "任意类型",
}


class NodeRegistry:
    """
    节点注册中心。

    职责：
    1. 注册/查询节点定义
    2. 输入验证（类型检查 + 范围检查）
    3. 输出格式化
    4. 生成 UI 元数据（给前端渲染用）
    5. 序列化/反序列化节点配置

    用法：
        registry = NodeRegistry()

        @registry.register(
            display_name="加载检查点",
            category="loaders",
            inputs=[
                InputSpec("ckpt_name", "STRING", options=["sd_v1.5.safetensors", "sdxl.safetensors"]),
            ],
            outputs=[
                OutputSpec("model", "MODEL"),
                OutputSpec("clip", "CLIP"),
                OutputSpec("vae", "VAE"),
            ],
        )
        def load_checkpoint(ckpt_name: str):
            ...
    """

    def __init__(self):
        self._nodes: Dict[str, NodeDefinition] = {}
        self._implementations: Dict[str, Callable] = {}

    def register(
        self,
        display_name: str,
        category: str,
        inputs: List[InputSpec],
        outputs: List[OutputSpec],
        description: str = "",
        is_output_node: bool = False,
        deprecated: bool = False,
        experimental: bool = False,
    ) -> Callable:
        """装饰器：注册节点"""
        def decorator(func: Callable) -> Callable:
            node_id = func.__name__
            self._nodes[node_id] = NodeDefinition(
                node_id=node_id,
                display_name=display_name,
                category=category,
                func_name=node_id,
                inputs=inputs,
                outputs=outputs,
                description=description,
                is_output_node=is_output_node,
                deprecated=deprecated,
                experimental=experimental,
            )
            self._implementations[node_id] = func
            logger.debug(f"[Registry] Registered node: {node_id} ({display_name})")
            return func
        return decorator

    def register_manual(self, definition: NodeDefinition, func: Callable) -> None:
        """手动注册节点（不用装饰器时）"""
        self._nodes[definition.node_id] = definition
        self._implementations[definition.node_id] = func

    def get_definition(self, node_id: str) -> Optional[NodeDefinition]:
        """获取节点定义"""
        return self._nodes.get(node_id)

    def get_implementation(self, node_id: str) -> Optional[Callable]:
        """获取节点实现"""
        return self._implementations.get(node_id)

    def list_nodes(self, category: Optional[str] = None) -> List[NodeDefinition]:
        """列出所有节点（可按分类过滤）"""
        nodes = list(self._nodes.values())
        if category:
            nodes = [n for n in nodes if n.category == category]
        return nodes

    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return sorted(set(n.category for n in self._nodes.values()))

    def validate_input(self, node_id: str, input_name: str, value: Any) -> Tuple[bool, str]:
        """
        验证输入值。

        Returns:
            (is_valid, error_message)
        """
        node = self._nodes.get(node_id)
        if node is None:
            return False, f"Unknown node: {node_id}"

        spec = None
        for inp in node.inputs:
            if inp.name == input_name:
                spec = inp
                break

        if spec is None:
            return False, f"Unknown input '{input_name}' for node '{node_id}'"

        # 类型检查
        type_validators = {
            "INT": lambda v: isinstance(v, int) or (isinstance(v, float) and v == int(v)),
            "FLOAT": lambda v: isinstance(v, (int, float)),
            "STRING": lambda v: isinstance(v, str),
            "BOOLEAN": lambda v: isinstance(v, bool),
        }

        validator = type_validators.get(spec.type)
        if validator and not validator(value):
            return False, f"Input '{input_name}' expects {spec.type}, got {type(value).__name__}"

        # 范围检查
        if spec.type in ("INT", "FLOAT") and isinstance(value, (int, float)):
            if spec.min is not None and value < spec.min:
                return False, f"Input '{input_name}' value {value} < min {spec.min}"
            if spec.max is not None and value > spec.max:
                return False, f"Input '{input_name}' value {value} > max {spec.max}"

        # 选项检查
        if spec.options and value not in spec.options:
            return False, f"Input '{input_name}' value '{value}' not in options {spec.options}"

        return True, ""

    def validate_all_inputs(self, node_id: str, values: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证节点的所有输入"""
        errors = []
        for name, value in values.items():
            ok, err = self.validate_input(node_id, name, value)
            if not ok:
                errors.append(err)
        return len(errors) == 0, errors

    def generate_ui_schema(self) -> Dict[str, Any]:
        """
        生成 UI Schema（给前端渲染节点编辑器用）。

        返回格式与 ComfyUI 的 /object_info 兼容。
        """
        schema = {}
        for node_id, node in self._nodes.items():
            if node.deprecated:
                continue
            input_types = {}
            for inp in node.inputs:
                input_types[inp.name] = {
                    "type": inp.type,
                    "default": inp.default,
                    "min": inp.min,
                    "max": inp.max,
                    "step": inp.step,
                    "multiline": inp.multiline,
                    "options": inp.options,
                    "tooltip": inp.tooltip,
                    "forceInput": inp.force_input,
                }
            output_types = [[out.type, out.tooltip] for out in node.outputs]
            schema[node_id] = {
                "display_name": node.display_name,
                "category": node.category,
                "input": input_types,
                "output": output_types,
                "output_node": node.is_output_node,
                "description": node.description,
                "experimental": node.experimental,
            }
        return schema

    def serialize_config(self, node_id: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """序列化节点配置（用于保存工作流）"""
        node = self._nodes.get(node_id)
        if node is None:
            return {}
        return {
            "node_id": node_id,
            "class_type": node_id,
            "inputs": {k: v for k, v in values.items()},
        }

    def stats(self) -> Dict[str, Any]:
        """注册统计"""
        categories = {}
        for node in self._nodes.values():
            categories.setdefault(node.category, 0)
            categories[node.category] += 1
        return {
            "total_nodes": len(self._nodes),
            "categories": categories,
            "deprecated": sum(1 for n in self._nodes.values() if n.deprecated),
            "experimental": sum(1 for n in self._nodes.values() if n.experimental),
        }
