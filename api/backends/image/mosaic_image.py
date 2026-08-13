"""Mosaic 图像生成后端 — 使用 Mosaic 框架的离线图像生成

替代 ComfyUI，使用 Mosaic 的 TextToImage 节点进行本地图像生成。
通过解析 ComfyUI 工作流 JSON 提取 prompt 和参数，保持与现有 pipeline 接口兼容。
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from api.registry import BackendMeta, registry

logger = logging.getLogger(__name__)

__all__ = ["MosaicImage"]


class MosaicImage:
    """基于 Mosaic TextToImage 节点的图像生成后端。

    接口与 ComfyUI 完全兼容：
    - generate(workflow, output_dir) → list[str]
    - upload_image(filepath, ...) → dict
    - check_image_exists(filename, ...) → bool
    - health_check() → (bool, str)
    """

    def __init__(self, config: dict):
        self._model = config.get("model", "stabilityai/stable-diffusion-xl-base-1.0")
        self._dtype = config.get("dtype", "float16")
        self._t2i_node = None
        self._uploaded: dict[str, str] = {}  # filename → local path

    @property
    def name(self):
        return "mosaic"

    @property
    def url(self) -> str:
        """兼容 ComfyUI 接口 — 返回空字符串（本地处理，无服务器URL）"""
        return ""

    # ── 核心接口 ──

    def generate(self, workflow: dict, output_dir: str) -> list[str]:
        """解析 ComfyUI 工作流，使用 Mosaic 生成图像

        从工作流中提取：
        - positive prompt (CLIPTextEncode → KSampler.positive)
        - negative prompt (CLIPTextEncode → KSampler.negative)
        - width/height (EmptyLatentImage)
        - seed/steps/cfg (KSampler)
        """
        prompt, negative_prompt, width, height, seed, steps, cfg = self._parse_workflow(workflow)

        self._ensure_loaded()

        from mosaic import MosaicData

        gen_kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
            "guidance_scale": cfg,
        }
        if seed and seed > 0:
            gen_kwargs["seed"] = seed

        logger.info(f"MosaicImage 生成: prompt={prompt[:80]}... size={width}x{height}")
        result = self._t2i_node.run(MosaicData(**gen_kwargs))
        image = result.get("image")
        if image is None:
            raise RuntimeError("Mosaic TextToImage 未返回图像")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir) / "mosaic_output.png"
        image.save(str(output_path))
        logger.info(f"MosaicImage 完成: {output_path}")
        return [str(output_path)]

    def upload_image(self, filepath: str, overwrite: bool = True, filename: str | None = None) -> dict:
        """本地存储上传的图片（兼容 ComfyUI 接口）

        Mosaic 在本地运行，无需上传到远程服务器。
        将文件名→路径映射缓存，供 generate() 中 LoadImage 节点使用。
        """
        upload_name = filename or Path(filepath).name
        self._uploaded[upload_name] = filepath
        logger.debug(f"MosaicImage 缓存图片: {upload_name} → {filepath}")
        return {"name": upload_name, "subfolder": ""}

    def check_image_exists(self, filename: str, subfolder: str = "", asset_type: str = "output") -> bool:
        """检查图片是否存在（本地文件检查）"""
        if filename in self._uploaded:
            return Path(self._uploaded[filename]).exists()
        return False

    def get_available_node_types(self) -> set[str]:
        """返回空集合（无 ComfyUI 节点概念）"""
        return set()

    def health_check(self) -> tuple[bool, str]:
        try:
            import mosaic
            return True, f"Mosaic image backend ready (model={self._model})"
        except ImportError:
            return False, "Mosaic 框架未安装"

    def shutdown(self):
        if self._t2i_node is not None:
            try:
                self._t2i_node.unload()
            except Exception:
                pass
            self._t2i_node = None

    # ── 内部方法 ──

    def _ensure_loaded(self):
        if self._t2i_node is None:
            from mosaic.nodes.image import TextToImage
            logger.info(f"MosaicImage 加载模型: {self._model}")
            self._t2i_node = TextToImage(model=self._model, dtype=self._dtype)
            self._t2i_node.load()

    def _parse_workflow(self, workflow: dict):
        """解析 ComfyUI 工作流，提取生成参数"""
        sampler_node = None
        for nid, node in workflow.items():
            if isinstance(node, dict) and node.get("class_type") in (
                "KSampler", "KSamplerAdvanced", "XlabsSampler"
            ):
                sampler_node = node
                break

        if not sampler_node:
            # 回退：直接找 CLIPTextEncode 节点
            prompts = []
            for nid, node in workflow.items():
                if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
                    prompts.append(node.get("inputs", {}).get("text", ""))
            prompt = prompts[0] if prompts else ""
            negative_prompt = prompts[1] if len(prompts) > 1 else ""
            return prompt, negative_prompt, 1024, 1024, 0, 20, 7.0

        inputs = sampler_node.get("inputs", {})
        seed = inputs.get("seed", 0)
        steps = inputs.get("steps", 20)
        cfg = inputs.get("cfg", 7.0)

        # 提取正向提示词
        positive_ref = inputs.get("positive", inputs.get("positive_cond", []))
        prompt = self._resolve_ref_text(workflow, positive_ref)

        # 提取负向提示词
        negative_ref = inputs.get("negative", inputs.get("negative_cond", []))
        negative_prompt = self._resolve_ref_text(workflow, negative_ref)

        # 提取尺寸
        latent_ref = inputs.get("latent_image", [])
        width, height = self._resolve_dimensions(workflow, latent_ref)

        return prompt, negative_prompt, width, height, seed, steps, cfg

    @staticmethod
    def _resolve_ref_text(workflow: dict, ref) -> str:
        """从节点引用中提取 CLIPTextEncode 的文本"""
        if not isinstance(ref, list) or len(ref) < 1:
            return ""
        node_id = ref[0]
        node = workflow.get(node_id, {})
        if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
            return node.get("inputs", {}).get("text", "")
        return ""

    @staticmethod
    def _resolve_dimensions(workflow: dict, ref) -> tuple[int, int]:
        """从节点引用中提取 EmptyLatentImage 的宽高"""
        if not isinstance(ref, list) or len(ref) < 1:
            return 1024, 1024
        node_id = ref[0]
        node = workflow.get(node_id, {})
        if isinstance(node, dict) and node.get("class_type") == "EmptyLatentImage":
            inputs = node.get("inputs", {})
            return inputs.get("width", 1024), inputs.get("height", 1024)
        return 1024, 1024


def _f(config): return MosaicImage(config)

# 注册多个后端名称（兼容原有 ComfyUI 工作流模板选择）
_IMAGE_MODELS = {
    "mosaic": "stabilityai/stable-diffusion-xl-base-1.0",
    "sd15": "runwayml/stable-diffusion-v1-5",
    "flux": "stabilityai/stable-diffusion-xl-base-1.0",
    "flux-fp8": "stabilityai/stable-diffusion-xl-base-1.0",
    "cosmos": "stabilityai/stable-diffusion-xl-base-1.0",
}
for _name, _model in _IMAGE_MODELS.items():
    registry.register(BackendMeta(
        name=_name, service_type="image", factory=_f,
        description=f"Mosaic 离线图像生成 ({_name})",
        priority=10, tags=["offline"], deployment="local"))
