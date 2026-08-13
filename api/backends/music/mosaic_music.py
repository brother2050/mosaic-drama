"""Mosaic 音乐生成后端 — 使用 Mosaic 框架的离线音乐生成

替代 MusicGen HTTP API 和 Template 音乐后端，
使用 Mosaic 的 MusicGenerator 节点进行本地音乐生成。
"""
from __future__ import annotations

import logging
from pathlib import Path

from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicMusic"]

# 情绪→音乐描述映射（保持与原 musicgen._MOOD_PROMPTS 兼容）
_MOOD_PROMPTS: dict[str, str] = {
    "happy": "happy upbeat cheerful background music",
    "sad": "sad melancholic emotional background music",
    "worried": "tense suspenseful anxious background music",
    "surprised": "surprising dramatic sudden background music",
    "angry": "intense aggressive dark background music",
    "calm": "calm peaceful serene background music",
    "neutral": "neutral ambient background music",
}


class MosaicMusic:
    """基于 Mosaic MusicGenerator 节点的音乐生成后端"""

    def __init__(self, config: dict):
        self._model = config.get("model", "facebook/musicgen-small")
        self._music_node = None

    @property
    def name(self) -> str:
        return "mosaic"

    def generate(self, prompt: str, duration: int = 30, output_path: str | None = None) -> str:
        """生成音乐片段"""
        from mosaic import MosaicData

        self._ensure_loaded()

        # 支持情绪关键词
        mood_prompt = _MOOD_PROMPTS.get(prompt.lower(), prompt)

        result = self._music_node.run(MosaicData(
            text=mood_prompt,
            duration=float(duration),
        ))

        audio = result.get("audio")
        if audio is None:
            raise RuntimeError("Mosaic MusicGenerator 未返回音频")

        if not output_path:
            output_path = str(Path.cwd() / "music_output.wav")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._save_audio(audio, output_path)
        logger.info(f"MosaicMusic 完成: {output_path}")
        return output_path

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic Music ready (model={self._model})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self):
        if self._music_node is not None:
            try:
                self._music_node.unload()
            except Exception:
                pass
            self._music_node = None

    # ── 内部方法 ──

    def _ensure_loaded(self):
        if self._music_node is None:
            from mosaic.nodes.audio import MusicGenerator
            logger.info(f"MosaicMusic 加载: model={self._model}")
            self._music_node = MusicGenerator(model=self._model)
            self._music_node.load()

    @staticmethod
    def _save_audio(audio, output: str):
        """将 Mosaic AudioData 保存为 WAV 文件"""
        import numpy as np
        import wave

        waveform = getattr(audio, "waveform", None)
        sample_rate = getattr(audio, "sample_rate", 32000)

        if waveform is None:
            raise RuntimeError("AudioData 无波形数据")

        if not isinstance(waveform, np.ndarray):
            waveform = np.array(waveform)

        if waveform.dtype != np.int16:
            waveform = (waveform * 32767).clip(-32768, 32767).astype(np.int16)

        with wave.open(output, "w") as wf:
            n_channels = 1 if len(waveform.shape) == 1 else waveform.shape[1]
            wf.setnchannels(n_channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(waveform.tobytes())


def _f(config): return MosaicMusic(config)
registry.register(BackendMeta(
    name="mosaic", service_type="music", factory=_f,
    description="Mosaic 离线音乐生成（MusicGen）",
    priority=10, tags=["offline"], deployment="local"))
