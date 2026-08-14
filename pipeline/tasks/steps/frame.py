"""首帧生成步骤 — 工作流构建 + 执行 → frame.png"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from engines.utils.shot import parse_char_names
from infra.constants import ERR_NOT_PREPARED, STATUS_DONE, STEP_FIRST_FRAME
from pipeline.tasks.helpers import _skip, _err

logger = logging.getLogger(__name__)


@dataclass
class FirstFrameParams:
    """首帧生成参数 — 消除 first_frame_core 的 8 个参数"""
    shot_id: str
    shot: dict
    cfg: object
    cont: object
    out_dir: Path
    force: bool = False
    characters: dict | None = None
    scenes: dict | None = None
    char_name_to_id: dict = field(default_factory=dict)


# ── 内部工具 ──


def _resolve_shot_context(shot: dict, cfg, characters: dict | None, scenes: dict | None):
    """解析镜头上下文：角色描述、场景描述、多人提示、服装"""
    from engines.prompt.view import get_view_appearance
    from engines.utils.multi_char import MultiCharacterHandler

    char_ids = parse_char_names(shot)
    characters, scenes = _ensure_char_scene_data(cfg, characters, scenes)

    # 服装匹配（先于角色描述构建，以便注入 outfit 描述到 prompt）
    shot = _auto_match_outfit(shot, char_ids, characters)

    # 角色描述（含 outfit 穿着描述）
    shot_type = shot.get("shot_type", "")
    outfit_key = shot.get("outfit", "")
    char_descs = []
    for cid in char_ids:
        char = characters.get(cid, {})
        if char:
            desc = get_view_appearance(char, shot_type)
            if not desc:
                return None, None, None, None, f"角色 {cid} 未生成 AI 绘图 prompt，{ERR_NOT_PREPARED}"
            # 注入服装穿着描述：让 ComfyUI 知道角色穿什么
            if outfit_key:
                outfit_desc = _get_outfit_desc(char, outfit_key)
                if outfit_desc:
                    desc = f"{desc}, wearing {outfit_desc}"
            char_descs.append(desc)

    # 场景描述
    scene = scenes.get(shot.get("scene_name", ""), {})
    scene_desc = ""
    if scene:
        scene_desc = scene.get("description_en", "")
        if not scene_desc and scene.get("description"):
            return None, None, None, None, f"场景 '{shot.get('scene_name', '')}' 尚未生成英文描述，{ERR_NOT_PREPARED}"
        # 校验：description_en 不应包含中文（翻译被污染）
        if scene_desc and not scene_desc.isascii():
            logger.warning("场景 description_en 仍含中文，回退到原始描述")
            scene_desc = scene.get("description", "")

    # 多人提示
    multi_char_prompt = ""
    if len(char_ids) > 1:
        multi_char_prompt = MultiCharacterHandler().generate_multi_char_prompt(
            [c for c in (characters.get(cid, {}) for cid in char_ids) if c])

    shot = _resolve_scene_ref(shot, scene, cfg)
    return shot, char_descs, scene_desc, multi_char_prompt, None


def _ensure_char_scene_data(cfg, characters, scenes):
    """确保角色/场景数据已加载（按需加载，不预加载分镜）"""
    if characters is not None and scenes is not None:
        return characters, scenes
    from infra.config import load_project_entities
    characters, scenes = load_project_entities(cfg.paths)
    return characters, scenes


def _get_outfit_desc(char: dict, outfit_key: str) -> str:
    """获取角色服装的英文穿着描述（用于 prompt 注入）

    优先级：description_en → description（中文，LLM 未翻译时降级）
    """
    outfits = char.get("outfits", {})
    if not isinstance(outfits, dict):
        return ""
    outfit = outfits.get(outfit_key)
    if not isinstance(outfit, dict):
        return ""
    return outfit.get("description_en", "") or outfit.get("description", "")


def _auto_match_outfit(shot, char_ids, characters):
    """服装自动匹配（outfit 为空时回退到 default 或第一个）"""
    if shot.get("outfit", "").strip() or not char_ids:
        return shot
    primary_char = characters.get(char_ids[0], {})
    if not primary_char:
        return shot
    char_outfits = primary_char.get("outfits", {})
    if not isinstance(char_outfits, dict) or not char_outfits:
        return shot
    outfit = "default" if "default" in char_outfits else next(iter(char_outfits))
    logger.info(f"outfit 为空，自动回退到 '{outfit}'")
    shot = dict(shot)
    shot["outfit"] = outfit
    return shot


def _resolve_scene_ref(shot, scene, cfg):
    """解析场景参考图路径"""
    if not scene:
        return shot
    scene_refs = scene.get("reference_images", [])
    if not scene_refs or shot.get("scene_ref"):
        return shot
    ref_url = scene_refs[0]
    if ref_url.startswith("/api/assets/"):
        local_path = cfg.paths.assets_dir / ref_url.removeprefix("/api/assets/")
        if local_path.exists():
            shot = dict(shot)
            shot["scene_ref"] = str(local_path)
    return shot


# ── 核心逻辑 ──


def _upload_reference_images(wf: dict, shot: dict, comfyui, paths) -> dict:
    """上传参考图到服务器并更新工作流节点引用

    Mosaic 后端使用最小化工作流（不含 LoadImage 节点），无需上传参考图。
    """
    return wf


def first_frame_core(p: FirstFrameParams) -> dict:
    """首帧生成核心逻辑 — ComfyUI 工作流构建 + 执行"""
    p.out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = p.out_dir / "frame.png"
    if not p.force and frame_path.exists():
        return _skip(p.shot_id, STEP_FIRST_FRAME, "首帧已存在")

    shot, char_descs, scene_desc, multi_char_prompt, err = _resolve_shot_context(
        p.shot, p.cfg, p.characters, p.scenes)
    if err:
        return _err(p.shot_id, STEP_FIRST_FRAME, err)

    # 确保 char_name_to_id 存在（Celery 独立步骤分派路径不会传入）
    if not p.char_name_to_id:
        from infra.config import load_char_name_to_id
        p.char_name_to_id = load_char_name_to_id(p.cfg.paths)

    from engines.generation import build_first_frame
    from pipeline.tasks.helpers import comfyui_generate

    paths = p.cfg.paths
    prompt, wf = build_first_frame(
        shot, character_desc=", ".join(char_descs), scene_desc=scene_desc,
        multi_char_prompt=multi_char_prompt,
        config=p.cfg.data, models=p.cfg.get("models", {}),
        project_dir=str(paths.root), char_name_to_id=p.char_name_to_id)
    if not wf:
        return _err(p.shot_id, STEP_FIRST_FRAME, "首帧工作流构建失败")

    comfyui = p.cont.get("image")
    result = comfyui_generate(p.shot_id, STEP_FIRST_FRAME, comfyui, wf, p.out_dir, "frame.png", min_size=500)
    if result.get("status") != STATUS_DONE:
        return result
    return {**result, "prompt": prompt.get("positive", "")}
