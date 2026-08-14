"""视频生成步骤 — 首帧 → video.mp4"""
from __future__ import annotations

import logging
from pathlib import Path

from infra.constants import STEP_VIDEO
from pipeline.tasks.helpers import _skip, _err

logger = logging.getLogger(__name__)


def _upload_first_frame_if_needed(video_wf: dict, frame_path: Path, server_filename: str,
                                  paths, video_backend) -> dict:
    """检查并上传首帧到视频服务器，更新工作流节点引用

    Mosaic 后端在本地处理，无需上传。直接将 LoadImage 节点指向本地首帧路径。
    """
    load_nodes = []
    for nid, node in video_wf.items():
        if isinstance(node, dict) and node.get("class_type") in ("LoadImage", "LoadImageFromPath", "ImageLoad"):
            load_nodes.append(nid)
    if not load_nodes:
        return video_wf

    # Mosaic 后端本地处理，直接使用本地文件路径
    for nid in load_nodes:
        if nid in video_wf:
            video_wf[nid]["inputs"]["image"] = str(frame_path)
    return video_wf


def video_core(shot_id: str, cfg, cont, out_dir: Path, *,
               shot: dict | None = None, force: bool = False,
               characters: dict | None = None, scenes: dict | None = None,
               char_name_to_id: dict | None = None) -> dict:
    """视频生成核心逻辑 — 从首帧生成视频"""
    frame_path = out_dir / "frame.png"
    if not frame_path.exists():
        return _skip(shot_id, STEP_VIDEO, "首帧不存在，请先执行 Step 2")

    video_path = out_dir / "video.mp4"
    if not force and video_path.exists():
        return _skip(shot_id, STEP_VIDEO, "视频已存在")

    from engines.generation import build_video
    from pipeline.tasks.helpers import comfyui_generate

    video_wf = build_video(str(frame_path), shot=shot, config=cfg.data, models=cfg.get("models", {}))
    if not video_wf:
        return _err(shot_id, STEP_VIDEO, "视频工作流构建失败")

    return comfyui_generate(shot_id, STEP_VIDEO, cont.get("video"), video_wf, out_dir, "video.mp4", min_size=10000)
