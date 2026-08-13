"""Mosaic LLM 策划案生成 — 替代 Seko 在线 API

使用 Mosaic LLM 后端离线生成影视策划案（角色、场景、分镜）。
接口与原 seko.proposal 兼容，但所有处理在本地完成。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["generate_proposal", "check_proposal_status", "modify_proposal", "download_elements_images"]

# 本地缓存：task_id → proposal_data
_proposal_cache: dict[str, dict] = {}


def _get_llm(config: dict):
    """通过 Container 获取 Mosaic LLM 后端"""
    from api.registry import Container
    container = Container(config)
    return container.get("llm")


def _build_proposal_prompt(user_prompt: str) -> str:
    """构建策划案生成 prompt"""
    return f"""你是一位专业的影视策划人。请根据以下故事梗概，生成一份完整的影视策划案。

故事梗概：{user_prompt}

请以 JSON 格式输出，包含以下结构：
{{
  "title": "剧名",
  "synopsis": "故事简介（200字以内）",
  "characters": [
    {{"id": "char01", "name": "角色名", "description": "角色描述", "appearance": "外貌描述"}}
  ],
  "scenes": [
    {{"id": "scene01", "name": "场景名", "description": "场景描述", "lighting": "灯光描述"}}
  ],
  "storyboard": [
    {{"shot_id": "001", "scene": "scene01", "characters": "char01", "action": "动作描述", "dialogue": "对话内容", "camera": "固定", "shot_type": "中景", "duration": 4.0, "emotion": "neutral"}}
  ]
}}

注意：
- 角色ID格式为 char01, char02...
- 场景ID格式为 scene01, scene02...
- 镜头ID格式为 001, 002...
- duration 范围 2-10 秒
- emotion 可选: happy, sad, worried, surprised, angry, calm, neutral
- camera 可选: 固定, 缓慢推近, 跟随平移, 手持晃动, 环绕, 俯视, 仰视
- shot_type 可选: 特写, 近景, 中景, 过肩, 全身, 全景, 远景
"""


def generate_proposal(prompt: str, *, config: dict | None = None, **kwargs) -> dict[str, Any]:
    """使用 Mosaic LLM 生成策划案"""
    config = config or {}
    task_id = str(uuid.uuid4())[:8]

    try:
        llm = _get_llm(config)
        full_prompt = _build_proposal_prompt(prompt)
        result_text = llm.chat(full_prompt)

        # 尝试解析 JSON
        proposal_data = _parse_json_response(result_text)
        proposal_data["taskId"] = task_id
        proposal_data["taskStatus"] = "OK"

        _proposal_cache[task_id] = proposal_data

        return {"code": 200, "msg": "success", "data": proposal_data}
    except Exception as e:
        logger.error(f"策划案生成失败: {e}", exc_info=True)
        return {"code": 500, "msg": f"策划案生成失败: {e}", "data": {}}


def check_proposal_status(task_id: str, *, config: dict | None = None, **kwargs) -> dict[str, Any]:
    """查询策划案状态（Mosaic 离线模式 — 同步完成）"""
    config = config or {}
    data = _proposal_cache.get(task_id)

    if data is None:
        return {"code": 404, "msg": "策划案不存在", "data": {"taskStatus": "NOT_FOUND"}}

    return {"code": 200, "msg": "success", "data": data}


def modify_proposal(task_id: str, prompt: str, *, config: dict | None = None, **kwargs) -> dict[str, Any]:
    """使用 Mosaic LLM 修改策划案"""
    config = config or {}
    original = _proposal_cache.get(task_id)

    if original is None:
        return {"code": 404, "msg": "原策划案不存在", "data": {}}

    try:
        llm = _get_llm(config)
        modify_prompt = f"""请根据以下修改指令，调整策划案。

原策划案：
{json.dumps(original, ensure_ascii=False, indent=2)}

修改指令：{prompt}

请输出修改后的完整策划案 JSON。"""

        result_text = llm.chat(modify_prompt)
        new_data = _parse_json_response(result_text)
        new_data["taskId"] = task_id
        new_data["taskStatus"] = "OK"

        _proposal_cache[task_id] = new_data
        return {"code": 200, "msg": "success", "data": new_data}
    except Exception as e:
        logger.error(f"策划案修改失败: {e}", exc_info=True)
        return {"code": 500, "msg": f"策划案修改失败: {e}", "data": {}}


def download_elements_images(data: dict, download_dir: str) -> list[dict]:
    """下载策划案中的角色/场景图片（Mosaic 离线模式 — 暂不生成图片）"""
    # Mosaic 模式下，图片生成通过 pipeline 的图像生成步骤完成
    # 此函数仅返回空列表，保持接口兼容
    return []


def _parse_json_response(text: str) -> dict:
    """从 LLM 响应中解析 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    import re
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 回退：返回最小结构
    return {
        "title": "未命名",
        "synopsis": text[:200],
        "characters": [],
        "scenes": [],
        "storyboard": [],
    }
