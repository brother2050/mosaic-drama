"""Mosaic 视频生成后端 — 使用 Mosaic 框架的离线视频生成

替代 ComfyUI 视频后端（AnimateDiff/CogVideoX/CosmosVideo），
使用 Mosaic 的 ImageToVideo 节点进行本地视频生成。
"""
from __future__ import annotations

import logging
from pathlib import Path

from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicVideo"]


class MosaicVideo:
    """基于 Mosaic ImageToVideo 节点的视频生成后端。

    接口与 ComfyUI 视频后端完全兼容。
    """

    def __init__(self, config: dict):
        self._model = config.get("model", "stabilityai/stable-video-diffusion-img2vid-xt")
        self._dtype = config.get("dtype", "float16")
        self._i2v_node = None
        self._uploaded: dict[str, str] = {}  # filename → local path

    @property
    def name(self):
        return "mosaic"

    @property
    def url(self) -> str:
        return ""

    def generate(self, workflow: dict, output_dir: str) -> list[str]:
        """解析工作流，使用 Mosaic 从首帧生成视频"""
        # 从工作流中提取首帧图片
        image_path = self._find_input_image(workflow)

        self._ensure_loaded()

        from mosaic import MosaicData
        from PIL import Image

        if image_path and Path(image_path).exists():
            input_image = Image.open(image_path)
        else:
            raise RuntimeError("MosaicVideo 找不到首帧图片")

        logger.info(f"MosaicVideo 从首帧生成视频: {image_path}")
        result = self._i2v_node.run(MosaicData(image=input_image))

        video = result.get("video")
        if video is None:
            raise RuntimeError("Mosaic ImageToVideo 未返回视频")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir) / "mosaic_video.mp4"

        # 将 VideoData（frames + fps）保存为 MP4
        self._save_video(video, str(output_path))
        logger.info(f"MosaicVideo 完成: {output_path}")
        return [str(output_path)]

    def upload_image(self, filepath: str, overwrite: bool = True, filename: str | None = None) -> dict:
        upload_name = filename or Path(filepath).name
        self._uploaded[upload_name] = filepath
        return {"name": upload_name, "subfolder": ""}

    def check_image_exists(self, filename: str, subfolder: str = "", asset_type: str = "output") -> bool:
        if filename in self._uploaded:
            return Path(self._uploaded[filename]).exists()
        return False

    def get_available_node_types(self) -> set[str]:
        return set()

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic video backend ready (model={self._model})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self):
        if self._i2v_node is not None:
            try:
                self._i2v_node.unload()
            except Exception:
                pass
            self._i2v_node = None

    # ── 内部方法 ──

    def _ensure_loaded(self):
        if self._i2v_node is None:
            from mosaic.nodes.video import ImageToVideo
            logger.info(f"MosaicVideo 加载模型: {self._model}")
            self._i2v_node = ImageToVideo(model=self._model, dtype=self._dtype)
            self._i2v_node.load()

    def _find_input_image(self, workflow: dict) -> str | None:
        """从工作流中找到 LoadImage 节点引用的本地图片路径"""
        load_types = ("LoadImage", "LoadImageFromPath", "ImageLoad")
        for nid, node in workflow.items():
            if isinstance(node, dict) and node.get("class_type") in load_types:
                filename = node.get("inputs", {}).get("image", "")
                if filename in self._uploaded:
                    return self._uploaded[filename]
                # 尝试直接作为文件路径
                if filename and Path(filename).exists():
                    return filename
        return None

    @staticmethod
    def _save_video(video, output_path: str):
        """将 Mosaic VideoData 保存为 MP4 文件"""
        import subprocess
        import tempfile

        frames = getattr(video, "frames", None) or video.get("frames") if isinstance(video, dict) else None
        fps = getattr(video, "fps", None) or (video.get("fps", 25) if isinstance(video, dict) else 25)

        if not frames:
            raise RuntimeError("VideoData 无帧数据")

        # 使用 ffmpeg 将帧序列编码为 MP4
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
                raise RuntimeError(
                    f"ffmpeg 编码失败: {result.stderr.decode()[:500]}"
                )


def _f(config): return MosaicVideo(config)

# 注册多个后端名称（兼容原有配置）
_VIDEO_NAMES = ["mosaic", "animatediff", "cosmos-video", "cogvideox"]
for _name in _VIDEO_NAMES:
    registry.register(BackendMeta(
        name=_name, service_type="video", factory=_f,
        description=f"Mosaic 离线视频生成 ({_name})",
        priority=10, tags=["offline"], deployment="local"))
