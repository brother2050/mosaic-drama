"""Mosaic 口型同步后端 — 使用 Mosaic 框架的离线口型同步

替代 MuseTalk/Wav2Lip HTTP API，使用 Mosaic 的 LipSyncer 节点进行本地口型同步。
"""
from __future__ import annotations

import logging
from pathlib import Path

from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicLipSync"]


class MosaicLipSync:
    """基于 Mosaic LipSyncer 节点的口型同步后端。

    接口与 MuseTalk/Wav2Lip 完全兼容：
    - sync(video_path, audio_path, output_path) → str
    """

    def __init__(self, config: dict):
        self._model = config.get("model", "numz/wav2lip-uhq")
        self._method = config.get("method", "wav2lip")
        self._fps = config.get("fps", 25)
        self._lip_node = None

    @property
    def name(self) -> str:
        return "mosaic"

    def sync(self, video_path: str, audio_path: str, output_path: str) -> str:
        """视频 + 音频 → 口型同步视频"""
        from mosaic import MosaicData, AudioData, VideoData
        from PIL import Image

        self._ensure_loaded()

        # 从视频提取第一帧作为源图片
        source_image = self._extract_first_frame(video_path)

        # 加载音频
        audio_data = self._load_audio(audio_path)

        logger.info(f"MosaicLipSync 开始: video={video_path}, audio={audio_path}")
        result = self._lip_node.run(MosaicData(
            image=source_image,
            audio=audio_data,
        ))

        video = result.get("video")
        if video is None:
            raise RuntimeError("Mosaic LipSyncer 未返回视频")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._save_video(video, output_path)
        logger.info(f"MosaicLipSync 完成: {output_path}")
        return output_path

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic LipSync ready (method={self._method})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self):
        if self._lip_node is not None:
            try:
                self._lip_node.unload()
            except Exception:
                pass
            self._lip_node = None

    # ── 内部方法 ──

    def _ensure_loaded(self):
        if self._lip_node is None:
            from mosaic.nodes.digital_human import LipSyncer
            logger.info(f"MosaicLipSync 加载: model={self._model}, method={self._method}")
            self._lip_node = LipSyncer(
                model=self._model,
                method=self._method,
                fps=self._fps,
            )
            self._lip_node.load()

    @staticmethod
    def _extract_first_frame(video_path: str):
        """从视频提取第一帧作为源图片"""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"提取视频首帧失败: {result.stderr.decode()[:500]}")

        from PIL import Image
        img = Image.open(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return img

    @staticmethod
    def _load_audio(audio_path: str):
        """加载音频文件为 Mosaic AudioData"""
        import wave
        import numpy as np
        from mosaic import AudioData

        with wave.open(audio_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        # 转换为 numpy array
        if sampwidth == 2:
            waveform = np.frombuffer(frames, dtype=np.int16)
        elif sampwidth == 4:
            waveform = np.frombuffer(frames, dtype=np.int32)
            waveform = (waveform / 65536).astype(np.int16)
        else:
            waveform = np.frombuffer(frames, dtype=np.uint8)
            waveform = ((waveform.astype(np.float32) - 128) * 256).astype(np.int16)

        if n_channels > 1:
            waveform = waveform[::n_channels]

        return AudioData(waveform=waveform.astype(np.float32) / 32768.0, sample_rate=framerate)

    @staticmethod
    def _save_video(video, output_path: str):
        """将 Mosaic VideoData 保存为 MP4"""
        import subprocess
        import tempfile

        frames = getattr(video, "frames", None)
        fps = getattr(video, "fps", 25) or 25

        if not frames:
            raise RuntimeError("VideoData 无帧数据")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, frame in enumerate(frames):
                frame.save(Path(tmp_dir) / f"frame_{i:06d}.png")

            cmd = [
                "ffmpeg", "-y", "-framerate", str(fps),
                "-i", str(Path(tmp_dir) / "frame_%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23", output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 编码失败: {result.stderr.decode()[:500]}")


def _f(config): return MosaicLipSync(config)
registry.register(BackendMeta(
    name="mosaic", service_type="lipsync", factory=_f,
    description="Mosaic 离线口型同步（Wav2Lip/SadTalker）",
    priority=10, tags=["offline"], deployment="local"))
