"""配乐生成 — 通过 Container 获取音乐后端"""
from __future__ import annotations
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["MusicGenerator"]


class MusicGenerator:
    """配乐生成器 — 优先使用注册的音乐后端，回退到 ffmpeg 模板"""
    def __init__(self, config: dict | None = None, timeouts: dict | None = None,
                 container: object = None):
        self._config = config or {}
        self._timeouts = timeouts or {}
        self._container = container

    def generate(self, duration: float, output: str, *, mood: str = "neutral") -> str:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        # 尝试通过 Container 获取注册的音乐后端
        try:
            if self._container is None:
                from api.registry import Container
                self._container = Container(self._config)
            music_backend = self._container.get("music")
            return music_backend.generate(duration, output, mood=mood)
        except Exception as e:
            logger.warning(f"音乐后端不可用 ({e})，回退到 ffmpeg 模板（建议安装 MusicGen 获得更好音质）")
            return self._template(duration, output, mood)

    def _template(self, duration: float, output: str, mood: str) -> str:
        """ffmpeg 模板配乐（最终回退）— 使用本地 ffmpeg 生成简单背景音"""
        import subprocess
        import tempfile
        # 情绪→频率映射
        mood_freq = {
            "happy": "440:880", "sad": "220:330", "worried": "330:440",
            "surprised": "550:1100", "angry": "110:220", "calm": "330:440",
            "neutral": "440:550",
        }
        freq_range = mood_freq.get(mood.lower(), mood_freq["neutral"])
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i",
                 f"sine=frequency={freq_range.split(':')[0]}:duration={duration}",
                 "-ac", "1", "-ar", "44100", str(output)],
                capture_output=True, timeout=30)
            if Path(output).exists():
                return output
        except Exception as e:
            logger.warning(f"ffmpeg 模板配乐失败: {e}")
        # 最终回退：生成空音频文件
        import wave
        with wave.open(output, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * int(44100 * duration))
        return output
