"""并发组 — 互斥锁按组名管理

解决的问题：
- 图像生成同一时间只能处理一张图/一个视频（GPU 密集）
- 同一 GPU 上的多个后端不能并行
- 不同类型的后端（TTS vs LLM）可以并行

用法:
    groups = ConcurrencyGroups({"image": 1, "tts": 2, "gpu": 1})

    # image 组同时只允许 1 个任务
    with groups.acquire("image"):
        do_image_work()
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

__all__ = ["ConcurrencyGroups"]


class ConcurrencyGroups:
    """并发组管理器 — 按组名维护互斥锁

    Args:
        limits: 组名 → 最大并发数，如 {"image": 1, "tts": 2}
    """

    def __init__(self, limits: dict[str, int] | None = None):
        self._limits = limits or {}
        self._locks: dict[str, threading.Semaphore] = {}

        for group, limit in self._limits.items():
            self._locks[group] = threading.Semaphore(limit)

    @contextmanager
    def acquire(self, group: str):
        """获取指定组的锁

        Args:
            group: 组名（如 "image"）
        """
        lock = self._locks.get(group)
        if lock is None:
            logger.debug(f"并发组 '{group}' 未注册，跳过限流")
            yield
            return

        lock.acquire()
        try:
            yield
        finally:
            lock.release()
