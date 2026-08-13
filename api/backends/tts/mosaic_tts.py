"""Mosaic TTS 后端 — 使用 Mosaic 框架的离线语音合成

替代所有在线 TTS 后端（MiMo VoiceDesign/VoiceClone、GPT-SoVITS、CosyVoice、
FishSpeech、ChatTTS），使用 Mosaic 的 TTS 节点进行本地语音合成。
默认使用 edge-tts（免费、无需GPU），也支持 transformers 本地模型。
"""
from __future__ import annotations

import logging
from pathlib import Path

from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicTTS"]


class MosaicTTS:
    """基于 Mosaic TTS 节点的语音合成后端。

    接口与 CosyVoice/GPT-SoVITS 等 TTS 后端完全兼容：
    - synthesize(text, output, voice_config, emotion, language) → str
    """

    def __init__(self, config: dict):
        self._model = config.get("model", "edge-tts")
        self._language = config.get("language", "zh")
        self._tts_node = None

    @property
    def name(self) -> str:
        return "mosaic"

    def synthesize(self, text: str, output: str, *,
                   voice_config: dict | None = None,
                   emotion: str = "neutral",
                   language: str = "zh") -> str:
        """文本转语音，输出 WAV 文件"""
        from mosaic import MosaicData

        self._ensure_loaded()

        voice = None
        if voice_config:
            voice = voice_config.get("voice") or voice_config.get("reference_audio")

        result = self._tts_node.run(MosaicData(
            text=text,
            emotion=emotion,
            language=language or self._language,
            voice=voice,
        ))

        audio = result.get("audio")
        if audio is None:
            raise RuntimeError("Mosaic TTS 未返回音频")

        Path(output).parent.mkdir(parents=True, exist_ok=True)
        self._save_audio(audio, output)
        logger.info(f"MosaicTTS 完成: {output}")
        return output

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic TTS ready (model={self._model})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self):
        if self._tts_node is not None:
            try:
                self._tts_node.unload()
            except Exception:
                pass
            self._tts_node = None

    # ── 内部方法 ──

    def _ensure_loaded(self):
        if self._tts_node is None:
            from mosaic.nodes.audio import TTS
            logger.info(f"MosaicTTS 加载: model={self._model}, language={self._language}")
            self._tts_node = TTS(model=self._model, language=self._language)
            self._tts_node.load()

    @staticmethod
    def _save_audio(audio, output: str):
        """将 Mosaic AudioData 保存为 WAV 文件"""
        waveform = getattr(audio, "waveform", None)
        sample_rate = getattr(audio, "sample_rate", 22050)

        if waveform is None and isinstance(audio, dict):
            waveform = audio.get("waveform")
            sample_rate = audio.get("sample_rate", 22050)

        if waveform is None:
            raise RuntimeError("AudioData 无波形数据")

        import numpy as np
        import wave
        import struct

        # 确保 waveform 是 numpy array
        if not isinstance(waveform, np.ndarray):
            waveform = np.array(waveform)

        # 转换为 int16
        if waveform.dtype != np.int16:
            waveform = (waveform * 32767).clip(-32768, 32767).astype(np.int16)

        # 写入 WAV 文件
        with wave.open(output, "w") as wf:
            n_channels = 1 if len(waveform.shape) == 1 else waveform.shape[1]
            wf.setnchannels(n_channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(waveform.tobytes())


def _f(config): return MosaicTTS(config)
registry.register(BackendMeta(
    name="mosaic", service_type="tts", factory=_f,
    description="Mosaic 离线 TTS（edge-tts / transformers）",
    priority=10, tags=["offline"], deployment="local"))
