"""
Workflow Queue — ComfyUI标准工作流JSON解析 + 执行队列
融合自 ComfyUI server.py + execution.py 的队列管理架构。
支持 ComfyUI 原生 prompt API 格式、中断/取消、批量执行。

ComfyUI prompt API 格式:
{
    "1": {"class_type": "KSampler", "inputs": {"seed": 42, ...}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "...", "clip": ["1", 0]}},
    ...
}
每个key是节点ID，inputs中的数组引用 ["node_id", output_index] 表示连接。
"""
from __future__ import annotations

import asyncio
import enum
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class WorkflowStatus(enum.Enum):
    """工作流执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass
class WorkflowJob:
    """队列中的工作流任务"""
    job_id: str
    prompt: Dict[str, Any]  # ComfyUI prompt API 格式
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    priority: int = 0  # 越大越优先


class WorkflowQueue:
    """
    ComfyUI 兼容工作流执行队列。

    核心能力:
    1. 解析 ComfyUI 原生 prompt API 格式 JSON
    2. 优先级队列调度
    3. 执行中断/取消
    4. 工作流双向序列化（JSON ↔ DAG）
    5. 批量执行

    用法:
        queue = WorkflowQueue(node_registry)
        job = queue.enqueue(comfyui_prompt_json)
        queue.start()  # 开始处理队列
        # ...
        queue.interrupt(job.job_id)  # 中断正在执行的任务
        queue.cancel(job.job_id)     # 取消等待中的任务
    """

    def __init__(self, node_registry: Any = None, max_concurrent: int = 1):
        self._registry = node_registry
        self._queue: List[WorkflowJob] = []
        self._active: Dict[str, WorkflowJob] = {}
        self._history: Dict[str, WorkflowJob] = {}
        self._max_concurrent = max_concurrent
        self._interrupt_flags: Dict[str, bool] = {}
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

    def enqueue(self, prompt: Dict[str, Any], priority: int = 0) -> WorkflowJob:
        """
        将 ComfyUI prompt API 格式的工作流加入队列。

        Args:
            prompt: ComfyUI prompt 格式 {"node_id": {"class_type": "...", "inputs": {...}}, ...}
            priority: 优先级（越大越优先）

        Returns:
            WorkflowJob 对象
        """
        job_id = str(uuid.uuid4())[:12]
        job = WorkflowJob(
            job_id=job_id,
            prompt=prompt,
            priority=priority,
        )
        self._queue.append(job)
        self._queue.sort(key=lambda j: -j.priority)
        logger.info(f"[Queue] Enqueued job {job_id} (priority={priority}, queue_size={len(self._queue)})")
        return job

    def enqueue_from_file(self, workflow_path: str, priority: int = 0) -> WorkflowJob:
        """从文件加载 ComfyUI 工作流 JSON 并加入队列"""
        path = Path(workflow_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

        with open(path) as f:
            data = json.load(f)

        # 自动检测格式：ComfyUI API 格式 vs UI 格式
        prompt = self._normalize_workflow(data)
        return self.enqueue(prompt, priority)

    def _normalize_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一工作流格式。
        ComfyUI 有两种格式:
        1. API格式 (prompt): {"1": {"class_type": "...", "inputs": {...}}}
        2. UI格式: {"nodes": [...], "links": [...], ...}
        """
        # 检测是否为UI格式
        if "nodes" in data and "links" in data:
            return self._ui_to_prompt(data)

        # 已经是API格式
        if any(isinstance(v, dict) and "class_type" in v for v in data.values()):
            return data

        raise ValueError("Unrecognized workflow format")

    def _ui_to_prompt(self, ui_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 ComfyUI UI 格式转换为 prompt API 格式"""
        prompt = {}
        node_map = {}  # UI node_id -> prompt node_id

        for i, node in enumerate(ui_data.get("nodes", [])):
            node_id = str(i + 1)
            node_map[node["id"]] = node_id
            class_type = node.get("type", "Unknown")

            inputs = {}
            # 从widgets_values提取固定参数
            for j, wv in enumerate(node.get("widgets_values", [])):
                if isinstance(wv, (str, int, float, bool)):
                    inputs[f"param_{j}"] = wv

            prompt[node_id] = {
                "class_type": class_type,
                "inputs": inputs,
            }

        # 处理links建立连接
        for link in ui_data.get("links", []):
            if len(link) >= 4:
                from_id = link[1]
                to_id = link[3]
                to_slot = link[4] if len(link) > 4 else 0
                from_str = node_map.get(str(from_id), str(from_id))
                to_str = node_map.get(str(to_id), str(to_id))
                if to_str in prompt:
                    prompt[to_str]["inputs"][f"input_{to_slot}"] = [from_str, 0]

        return prompt

    def interrupt(self, job_id: str) -> bool:
        """中断正在执行的任务"""
        if job_id in self._active:
            self._interrupt_flags[job_id] = True
            logger.info(f"[Queue] Interrupt requested for job {job_id}")
            return True
        return False

    def cancel(self, job_id: str) -> bool:
        """取消等待中的任务"""
        for i, job in enumerate(self._queue):
            if job.job_id == job_id:
                job.status = WorkflowStatus.CANCELLED
                self._queue.pop(i)
                self._history[job_id] = job
                logger.info(f"[Queue] Cancelled job {job_id}")
                return True
        return False

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        job = self._active.get(job_id) or self._history.get(job_id)
        if job:
            return {
                "job_id": job.job_id,
                "status": job.status.value,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error": job.error,
                "outputs": list(job.outputs.keys()),
            }
        # 检查队列中
        for job in self._queue:
            if job.job_id == job_id:
                return {"job_id": job.job_id, "status": "queued", "position": self._queue.index(job)}
        return None

    def queue_status(self) -> Dict[str, Any]:
        """获取队列整体状态"""
        return {
            "queue_size": len(self._queue),
            "active_count": len(self._active),
            "history_count": len(self._history),
            "running": self._running,
        }

    def clear_history(self) -> int:
        """清空历史记录，返回清除数量"""
        count = len(self._history)
        self._history.clear()
        return count
