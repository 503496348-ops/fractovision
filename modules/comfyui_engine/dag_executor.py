"""
DAG Executor — 懒求值 + 增量重执行引擎
融合自 ComfyUI execution.py 的核心架构模式。
适用于多媒体生成管道（图→视频→音频）的有向无环图编排。
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class NodeStatus(enum.Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    CACHED = "cached"


class ExecutionResult(enum.Enum):
    """执行结果"""
    SUCCESS = 0
    FAILURE = 1
    PARTIAL = 2  # 部分节点失败但可降级


@dataclass
class NodeOutput:
    """节点输出包装"""
    data: Any
    node_id: str
    output_index: int = 0
    timestamp: float = field(default_factory=time.time)
    cached: bool = False


@dataclass
class DAGNode:
    """DAG 节点定义"""
    node_id: str
    func: Callable
    inputs: Dict[str, str] = field(default_factory=dict)  # input_name -> "node_id.output_idx"
    config: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    output: Optional[NodeOutput] = None
    error: Optional[str] = None
    fingerprint: Optional[str] = None
    is_async: bool = False
    category: str = "general"
    lazy: bool = False  # 是否支持懒求值


class DAGExecutor:
    """
    懒求值 DAG 执行引擎。

    核心特性：
    1. 增量重执行：只重新执行变更节点及其下游依赖
    2. 懒求值：节点可在所有输入满足后仍延迟执行，直到真正需要
    3. 异步支持：节点函数可以是 async def
    4. 缓存感知：基于 fingerprint 跳过未变更计算
    5. 子图展开：运行时动态创建新节点

    用法：
        executor = DAGExecutor()
        executor.add_node("load_model", load_checkpoint, config={"path": "model.safetensors"})
        executor.add_node("encode", encode_text, inputs={"model": "load_model.0"})
        executor.add_node("generate", generate_image, inputs={"model": "load_model.0", "cond": "encode.0"})
        results = executor.execute()
    """

    def __init__(self, max_concurrency: int = 4, cache_enabled: bool = True):
        self._nodes: Dict[str, DAGNode] = {}
        self._execution_order: List[str] = []
        self._changed_nodes: Set[str] = set()
        self._max_concurrency = max_concurrency
        self._cache_enabled = cache_enabled
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._results: Dict[str, NodeOutput] = {}
        self._expanded_nodes: List[str] = []  # 子图展开产生的节点

    def add_node(
        self,
        node_id: str,
        func: Callable,
        inputs: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None,
        category: str = "general",
        lazy: bool = False,
    ) -> None:
        """注册一个 DAG 节点"""
        is_async = asyncio.iscoroutinefunction(func)
        self._nodes[node_id] = DAGNode(
            node_id=node_id,
            func=func,
            inputs=inputs or {},
            config=config or {},
            is_async=is_async,
            category=category,
            lazy=lazy,
        )
        self._changed_nodes.add(node_id)
        self._invalidate_dependents(node_id)

    def remove_node(self, node_id: str) -> None:
        """移除节点及其所有下游引用"""
        if node_id in self._nodes:
            self._invalidate_dependents(node_id)
            del self._nodes[node_id]
            self._changed_nodes.discard(node_id)

    def mark_changed(self, node_id: str) -> None:
        """标记节点已变更，触发增量重执行"""
        self._changed_nodes.add(node_id)
        self._invalidate_dependents(node_id)

    def _invalidate_dependents(self, node_id: str) -> None:
        """递归失效所有依赖该节点的下游节点"""
        for nid, node in self._nodes.items():
            for inp_spec in node.inputs.values():
                source_id = inp_spec.split(".")[0]
                if source_id == node_id:
                    self._changed_nodes.add(nid)
                    self._invalidate_dependents(nid)

    def _resolve_execution_order(self) -> List[str]:
        """拓扑排序（带循环检测），只包含需要执行的节点"""
        visited: Set[str] = set()
        in_stack: Set[str] = set()  # 当前DFS路径，用于检测循环
        order: List[str] = []

        def dfs(nid: str) -> None:
            if nid in visited:
                return
            if nid in in_stack:
                # 检测到循环！
                cycle_path = [nid]
                raise RuntimeError(
                    f"[DAG] Cycle detected involving node '{nid}'. "
                    f"This would cause infinite recursion. "
                    f"Check node inputs for circular dependencies."
                )
            in_stack.add(nid)
            node = self._nodes.get(nid)
            if node is None:
                in_stack.discard(nid)
                return
            for inp_spec in node.inputs.values():
                source_id = inp_spec.split(".")[0]
                dfs(source_id)
            in_stack.discard(nid)
            visited.add(nid)
            order.append(nid)

        for nid in self._nodes:
            try:
                dfs(nid)
            except RuntimeError as e:
                if "Cycle detected" in str(e):
                    raise
                continue
        return order

    def detect_cycles(self) -> List[List[str]]:
        """
        检测图中所有循环，返回循环路径列表。
        用于诊断和报告，不会中断执行。
        """
        cycles = []
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        path: List[str] = []

        def dfs(nid: str) -> None:
            if nid in visited:
                return
            if nid in in_stack:
                # 找到循环
                cycle_start = path.index(nid)
                cycles.append(path[cycle_start:] + [nid])
                return
            in_stack.add(nid)
            path.append(nid)
            node = self._nodes.get(nid)
            if node:
                for inp_spec in node.inputs.values():
                    source_id = inp_spec.split(".")[0]
                    dfs(source_id)
            path.pop()
            in_stack.discard(nid)
            visited.add(nid)

        for nid in self._nodes:
            dfs(nid)
        return cycles

    def _gather_inputs(self, node: DAGNode) -> Tuple[List[Any], Dict[str, Any]]:
        """收集节点的输入参数"""
        args = []
        kwargs = {}
        for input_name, inp_spec in node.inputs.items():
            parts = inp_spec.split(".")
            source_id = parts[0]
            output_idx = int(parts[1]) if len(parts) > 1 else 0
            source_output = self._results.get(source_id)
            if source_output is None:
                raise ValueError(f"Node '{node.node_id}': missing input from '{source_id}'")
            data = source_output.data
            if isinstance(data, (list, tuple)) and output_idx < len(data):
                data = data[output_idx]
            kwargs[input_name] = data
        return args, kwargs

    def _compute_fingerprint(self, node: DAGNode) -> str:
        """计算节点 fingerprint（输入内容+config 的哈希，而非仅时间戳）"""
        import hashlib
        parts = [node.node_id]
        for inp_spec in sorted(node.inputs.values()):
            source_id = inp_spec.split(".")[0]
            if source_id in self._results:
                out = self._results[source_id]
                # 用内容哈希代替时间戳，避免相同内容重复计算
                try:
                    import json as _json
                    content_str = _json.dumps(out.data, sort_keys=True, default=str)[:4096]
                    content_hash = hashlib.md5(content_str.encode()).hexdigest()[:12]
                    parts.append(f"{source_id}:{content_hash}")
                except Exception:
                    parts.append(f"{source_id}:{out.timestamp}")
        for k, v in sorted(node.config.items()):
            parts.append(f"{k}={v}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    async def _execute_node(self, node: DAGNode) -> NodeOutput:
        """执行单个节点"""
        # 懒求值检查
        if node.lazy and node.node_id not in self._changed_nodes and node.output is not None:
            logger.debug(f"[DAG] Lazy skip: {node.node_id}")
            return node.output

        # 缓存检查
        if self._cache_enabled and node.node_id not in self._changed_nodes and node.output is not None:
            fp = self._compute_fingerprint(node)
            if fp == node.fingerprint:
                logger.debug(f"[DAG] Cache hit: {node.node_id}")
                node.output.cached = True
                return node.output

        node.status = NodeStatus.RUNNING
        args, kwargs = self._gather_inputs(node)
        kwargs.update(node.config)

        try:
            async with self._semaphore:
                if node.is_async:
                    result = await node.func(*args, **kwargs)
                else:
                    result = node.func(*args, **kwargs)

            output = NodeOutput(data=result, node_id=node.node_id)
            node.output = output
            node.fingerprint = self._compute_fingerprint(node)
            node.status = NodeStatus.SUCCESS
            self._results[node.node_id] = output
            logger.debug(f"[DAG] Completed: {node.node_id}")
            return output

        except Exception as e:
            node.status = NodeStatus.FAILURE
            node.error = str(e)
            logger.error(f"[DAG] Failed: {node.node_id} — {e}")
            raise

    async def execute_async(self, target_nodes: Optional[List[str]] = None) -> Dict[str, NodeOutput]:
        """
        异步执行 DAG。

        Args:
            target_nodes: 指定目标节点。为 None 时执行所有叶子节点。

        Returns:
            所有已执行节点的输出字典。
        """
        order = self._resolve_execution_order()
        if target_nodes:
            needed = set()
            for tn in target_nodes:
                self._collect_ancestors(tn, needed)
            order = [n for n in order if n in needed]

        for node_id in order:
            node = self._nodes[node_id]
            if node_id not in self._changed_nodes and node.output is not None and self._cache_enabled:
                fp = self._compute_fingerprint(node)
                if fp == node.fingerprint:
                    node.status = NodeStatus.CACHED
                    self._results[node_id] = node.output
                    continue
            try:
                await self._execute_node(node)
            except Exception:
                if target_nodes:
                    raise  # 目标节点失败则终止
                # 非关键节点失败，标记为 SKIPPED 后续节点
                for downstream in self._get_downstream(node_id):
                    self._nodes[downstream].status = NodeStatus.SKIPPED

        self._changed_nodes.clear()
        return dict(self._results)

    def execute(self, target_nodes: Optional[List[str]] = None) -> Dict[str, NodeOutput]:
        """同步执行入口"""
        return asyncio.run(self.execute_async(target_nodes))

    def _collect_ancestors(self, node_id: str, ancestors: Set[str]) -> None:
        """收集节点的所有祖先"""
        ancestors.add(node_id)
        node = self._nodes.get(node_id)
        if node:
            for inp_spec in node.inputs.values():
                source_id = inp_spec.split(".")[0]
                self._collect_ancestors(source_id, ancestors)

    def _get_downstream(self, node_id: str) -> Set[str]:
        """获取直接下游节点"""
        downstream = set()
        for nid, node in self._nodes.items():
            for inp_spec in node.inputs.values():
                if inp_spec.split(".")[0] == node_id:
                    downstream.add(nid)
        return downstream

    def expand_subgraph(self, parent_node_id: str, new_nodes: List[Dict[str, Any]]) -> None:
        """
        子图展开：运行时动态添加新节点。

        Args:
            parent_node_id: 父节点 ID
            new_nodes: 新节点定义列表，每个包含 node_id, func, inputs, config
        """
        for spec in new_nodes:
            nid = spec["node_id"]
            self.add_node(
                node_id=nid,
                func=spec["func"],
                inputs=spec.get("inputs", {}),
                config=spec.get("config", {}),
                category=spec.get("category", "expanded"),
            )
            self._expanded_nodes.append(nid)
        logger.info(f"[DAG] Expanded subgraph from '{parent_node_id}': {len(new_nodes)} new nodes")

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有节点状态"""
        return {
            nid: {
                "status": node.status.value,
                "cached": node.output.cached if node.output else False,
                "error": node.error,
                "category": node.category,
            }
            for nid, node in self._nodes.items()
        }
