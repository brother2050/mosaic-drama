# 工作流模板

工作流 JSON 模板由 Mosaic 后端解析，用于提取 prompt 和参数。
这些 JSON 采用 ComfyUI API 格式编写，但不再由 ComfyUI 服务器直接执行，
而是由 Mosaic 离线后端解析并驱动本地推理。

## 需要的文件

| 文件名 | 用途 | 对应后端 |
|--------|------|---------|
| `01_first_frame_sd15.json` | SD1.5 首帧生成 | `image_backend: sd15` |
| `01_first_frame_flux.json` | Flux 首帧生成 | `image_backend: flux` |
| `02_img2video.json` | AnimateDiff 视频生成 | `video_backend: animatediff` |
| `03_img2video_cogvideo.json` | CogVideoX 视频生成 | `video_backend: cogvideox` |

## 如何获取

1. 在 ComfyUI 中搭建工作流（仅用于设计/调试）
2. 点击 **Save (API Format)** 导出 JSON
3. 重命名后放入此目录，Mosaic 后端会自动解析其中的节点和参数

## 节点命名约定

工作流中的节点会被 Mosaic 后端自动识别：
- `LoadImage` / `LoadImageFromPath` / `ImageLoad` → 角色参考图注入
- `CLIPTextEncode` → Prompt 自动注入
- `IPAdapterAdvanced` → IP-Adapter 角色一致性权重调整
- `PulidFluxModelLoader` / `ApplyPulidFlux` → PuLID-Flux 面部一致性（启动时通过 /object_info 自动检测）
- `LoadFluxControlNet` / `ApplyFluxControlNet` → ControlNet Depth 全身结构一致性
- `KSampler` → 采样参数调整
