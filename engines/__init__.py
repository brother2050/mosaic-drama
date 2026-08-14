"""引擎层 — 核心功能模块

模块结构:
- engines/prompt/: Prompt 工程
- engines/content/: 内容生成（定妆照、LLM、分镜）
- engines/consistency/: 角色一致性（检查、圣经）
- engines/utils/: 共享工具（镜头、实体、多角色）
"""
from engines.prompt import (
    PromptBuildParams, batch_generate_appearance_prompts, build_prompt,
    translate_to_english, batch_translate_to_english,
    get_view_appearance, build_view_prompt,
)
from engines.content import (
    ensure_portrait, ViewGenParams,
    StoryboardGenParams, generate_storyboard,
)
from engines.consistency import (
    ConsistencyChecker, check_consistency,
    CharacterBible,
)
from engines.utils import (
    parse_char_names, strip_dialogue, postprocess_shots,
    generate_and_save, save_entities, build_entity_descriptions,
    MultiCharacterHandler,
)

__all__ = [
    # prompt
    "PromptBuildParams", "batch_generate_appearance_prompts", "build_prompt",
    "translate_to_english", "batch_translate_to_english",
    "get_view_appearance", "build_view_prompt",
    # content
    "ensure_portrait", "ViewGenParams",
    "StoryboardGenParams", "generate_storyboard",
    # consistency
    "ConsistencyChecker", "check_consistency",
    "CharacterBible",
    # utils
    "parse_char_names", "strip_dialogue", "postprocess_shots",
    "generate_and_save", "save_entities", "build_entity_descriptions",
    "MultiCharacterHandler",
]
