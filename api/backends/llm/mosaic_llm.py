"""Mosaic LLM 后端 — 使用 Mosaic 框架的离线 LLM 推理

替代 OpenAI SDK / Ollama，使用 Mosaic 的 Chat 节点进行本地模型推理。
"""
from __future__ import annotations

import logging

from api.backends.llm.base import BaseLLM
from api.backends.llm.mixins import ConfigMixin
from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicLLM"]


class MosaicLLM(ConfigMixin, BaseLLM):
    """基于 Mosaic Chat 节点的 LLM 后端。

    使用 HuggingFace 本地模型（如 Qwen2.5-7B-Instruct）进行推理，
    无需任何在线 API 调用。
    """

    def __init__(self, config: dict):
        self._init_llm_config(config)
        if not self._model:
            self._model = config.get("model", "Qwen/Qwen2.5-7B-Instruct")
        if not self._ctx:
            self._ctx = config.get("context_length", 32768)
        self._chat_node = None
        self._config = config

    @property
    def name(self) -> str:
        return "mosaic"

    @property
    def context_length(self) -> int:
        return self._ctx or 32768

    def _ensure_loaded(self):
        if self._chat_node is None:
            from mosaic.nodes.text import Chat
            logger.info(f"MosaicLLM 加载模型: {self._model}")
            self._chat_node = Chat(model=self._model)
            self._chat_node.load()

    def chat(self, prompt: str, system: str = "", **kwargs) -> str:
        from mosaic import MosaicData

        self._ensure_loaded()

        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature", self._temperature)
        if temperature is None:
            temperature = 0.7
        top_p = kwargs.get("top_p", self._top_p)
        if top_p is None:
            top_p = 0.9

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        gen_kwargs = {"temperature": temperature, "top_p": top_p}
        if max_tokens:
            gen_kwargs["max_new_tokens"] = max_tokens

        result = self._chat_node.run(MosaicData(
            messages=messages,
            system_prompt=system if system else None,
            **gen_kwargs,
        ))

        reply = result.get("reply") or result.get("text") or ""
        if not reply:
            raise ValueError("MosaicLLM 返回空回复")
        return reply

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic LLM ready (model={self._model})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self) -> None:
        if self._chat_node is not None:
            try:
                self._chat_node.unload()
            except Exception:
                pass
            self._chat_node = None


def _f(config): return MosaicLLM(config)
registry.register(BackendMeta(
    name="mosaic", service_type="llm", factory=_f,
    description="Mosaic 离线 LLM 推理（HuggingFace 本地模型）",
    priority=10, tags=["offline"], deployment="local"))
