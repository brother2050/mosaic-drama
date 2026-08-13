"""LLM 后端包 — Mosaic 离线推理

MosaicLLM: Mosaic 框架离线 LLM 推理（HuggingFace 本地模型）
"""
from __future__ import annotations

from .base import BaseLLM
from .mixins import ConfigMixin, ErrorLearningMixin, HttpRetryMixin
from .mosaic_llm import MosaicLLM

__all__ = [
    "BaseLLM",
    "ConfigMixin",
    "ErrorLearningMixin",
    "HttpRetryMixin",
    "MosaicLLM",
]
