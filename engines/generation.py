"""简化生成参数构建器 — 替代 ComfyUI WorkflowBuilder

Mosaic 后端不需要 ComfyUI 工作流 JSON，只需 prompt 文本和生成参数。
本模块构建最小化的工作流字典，保持与 MosaicImage/MosaicVideo 后端接口兼容。

职责:
- 编译 prompt（复用 engines.prompt.builder）
- 从注册表读取默认参数（width/height/steps/cfg）
- 应用 GPU 配置（分辨率/步数覆盖）
- 构建最小工作流字典供 Mosaic 后端解析
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from engines.utils.shot import parse_char_names

logger = logging.getLogger(__name__)

__all__ = [
    "build_first_frame",
    "build_video",
    "build_portrait_workflow",
    "build_scene_workflow",
]


def _get_registry():
    from infra.config.registry import ModelRegistry
    return ModelRegistry()


def _get_gpu_config(config: dict) -> dict:
    from infra.compute.gpu import get_generation_config
    return get_generation_config(config=config)


def _build_prompt(shot: dict, character_desc: str, scene_desc: str,
                  multi_char_prompt: str, config: dict, models: dict,
                  project_dir: str, char_name_to_id: dict, registry=None) -> tuple[dict, str]:
    """编译首帧 prompt — 从 WorkflowBuilder._build_first_frame_prompt 提取"""
    from engines.prompt.builder import PromptBuildParams, build_prompt

    style = config.get("project", {}).get("style", "cinematic")
    genre = config.get("project", {}).get("genre", "urban")
    img_backend = models.get("image_backend", "flux")

    if registry is None:
        registry = _get_registry()

    # 角色圣经上下文
    character_bible = ""
    char_names = parse_char_names(shot)
    enriched_shot = dict(shot)
    if char_names:
        try:
            from engines.consistency.bible import CharacterBible
            bible = CharacterBible(project_dir)
            prompt_style = registry.get_prompt_style(img_backend) if img_backend else "tag"
            resolved_cid = char_name_to_id.get(char_names[0], char_names[0])
            character_bible = bible.get_tags(resolved_cid) if prompt_style == "tag" else bible.get_context(resolved_cid)
            char_bible_data = bible.load(resolved_cid)
            if char_bible_data:
                enriched_shot["_char_emotional_range"] = char_bible_data.get("emotional_range", {})
                enriched_shot["_char_body_language"] = char_bible_data.get("body_language", {})
        except Exception as e:
            logger.warning(f"角色圣经加载跳过: {e}")

    # 场景数据（含 lighting）
    scene_data = {}
    scene_name = shot.get("scene_name", "")
    if scene_name:
        try:
            from infra.config import load_scene, ProjectPaths
            scene_data = load_scene(ProjectPaths(project_dir), scene_name)
        except Exception as e:
            logger.debug(f"场景数据加载跳过: {e}")

    positive = build_prompt(PromptBuildParams(
        shot=enriched_shot, character_desc=character_desc,
        scene_desc=scene_desc, style=style, genre=genre,
        image_backend=img_backend, registry=registry,
        character_bible=character_bible, scene_data=scene_data))
    if multi_char_prompt:
        positive = f"{positive}, {multi_char_prompt}"

    # 从注册表读取 negative prompt
    backend_meta = registry.get_backend("image", img_backend) if img_backend else {}
    negative = (backend_meta or {}).get("negative_prompt",
        "bad quality, worst quality, ugly, deformed, blurry, "
        "text, watermark, logo, signature, subtitle, caption, text overlay")

    return {"positive": positive, "negative": negative}, img_backend


def _apply_params(workflow: dict, config: dict, models: dict, registry, stage: str = "first_frame") -> None:
    """应用 GPU 配置（分辨率/步数覆盖）"""
    gpu_cfg = _get_gpu_config(config)
    resolution = gpu_cfg.get("resolution")
    aspect_ratio = gpu_cfg.get("aspect_ratio")
    image_steps = gpu_cfg.get("image_steps")

    for _, node in workflow.items():
        ct = node.get("class_type", "")
        inp = node.get("inputs", {})

        # 分辨率
        if ct == "EmptyLatentImage":
            native_w = inp.get("width", 1024)
            native_h = inp.get("height", 576)
            if resolution and len(resolution) == 2:
                inp["width"] = resolution[0]
                inp["height"] = resolution[1]
            elif aspect_ratio:
                w, h = _calc_resolution(native_w, native_h, aspect_ratio)
                inp["width"] = w
                inp["height"] = h

        # 步数
        if ct in ("KSampler", "KSamplerAdvanced") and stage == "first_frame":
            if image_steps:
                inp["steps"] = image_steps


def _calc_resolution(native_w: int, native_h: int, aspect_ratio: str) -> tuple[int, int]:
    """根据目标比例计算分辨率"""
    try:
        parts = aspect_ratio.split(":")
        rw, rh = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return native_w, native_h
    if rw <= 0 or rh <= 0:
        return native_w, native_h
    long_side = max(native_w, native_h)
    if rw >= rh:
        w = long_side
        h = int(long_side * rh / rw)
    else:
        h = long_side
        w = int(long_side * rw / rh)
    w = max(64, (w // 8) * 8)
    h = max(64, (h // 8) * 8)
    return w, h


def _make_image_workflow(positive: str, negative: str, width: int = 1024,
                          height: int = 576, steps: int = 20, cfg: float = 7.0,
                          seed: int | None = None) -> dict:
    """构建最小化图像生成工作流字典（Mosaic 后端兼容格式）"""
    if seed is None:
        seed = random.randint(0, 2**63 - 1)
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg,
            "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0],
        }},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1,
        }},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positive}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative}},
    }


def _make_video_workflow(frame_path: str, video_frames: int = 24,
                          seed: int | None = None) -> dict:
    """构建最小化视频生成工作流字典（Mosaic 后端兼容格式）"""
    if seed is None:
        seed = random.randint(0, 2**63 - 1)
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": str(frame_path)}},
        "2": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 20, "cfg": 7.0,
            "video_frames": video_frames,
        }},
    }


# ══════════════════════════════════════════════════════════
#  公共接口
# ══════════════════════════════════════════════════════════


def build_first_frame(shot: dict, character_desc: str = "", scene_desc: str = "",
                      multi_char_prompt: str = "", *, config: dict, models: dict,
                      project_dir: str, char_name_to_id: dict | None = None,
                      seed: int | None = None, registry=None) -> tuple[dict, dict]:
    """构建首帧生成参数

    Returns:
        (prompt_dict, workflow_dict) — prompt_dict 含 positive/negative
    """
    char_name_to_id = char_name_to_id or {}
    prompt, img_backend = _build_prompt(
        shot, character_desc, scene_desc, multi_char_prompt,
        config, models, project_dir, char_name_to_id, registry)

    # 从注册表读取默认参数
    if registry is None:
        registry = _get_registry()
    backend_meta = registry.get_backend("image", img_backend) or {}
    params = backend_meta.get("default_params", {})
    width = params.get("width", 1024)
    height = params.get("height", 576)
    steps = params.get("steps", 20)
    cfg = params.get("cfg_scale", 7.0)

    wf = _make_image_workflow(prompt["positive"], prompt["negative"],
                               width, height, steps, cfg, seed)
    _apply_params(wf, config, models, registry, stage="first_frame")
    return prompt, wf


def build_video(frame_path: str, shot: dict | None = None, *,
                config: dict, models: dict) -> dict:
    """构建视频生成工作流

    Args:
        frame_path: 首帧图片路径
        shot: 镜头配置（含 duration）
        config: 项目配置
        models: 模型配置
    """
    duration = 5
    if shot:
        duration = shot.get("duration", 5)
    fps = config.get("project", {}).get("fps", 24)
    video_frames = max(1, int(duration * fps))
    return _make_video_workflow(frame_path, video_frames)


def build_portrait_workflow(positive: str, negative: str, *,
                            width: int = 1024, height: int = 1024,
                            steps: int = 20, cfg: float = 7.0,
                            seed: int | None = None) -> dict:
    """构建定妆照生成工作流"""
    return _make_image_workflow(positive, negative, width, height, steps, cfg, seed)


def build_scene_workflow(positive: str, negative: str, *,
                         width: int = 1024, height: int = 576,
                         steps: int = 20, cfg: float = 7.0,
                         seed: int | None = None) -> dict:
    """构建场景图生成工作流"""
    return _make_image_workflow(positive, negative, width, height, steps, cfg, seed)
