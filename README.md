# 🎬 AI 短剧全流程生产管线 v2

> 从剧本到成片，一键搞定 — 纯 Python，跨平台，零 Shell 脚本依赖

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **纯 Python** | 零 Shell 脚本，Windows/macOS/Linux 通用 |
| **Mosaic 离线** | 所有 AI 能力（图像/视频/LLM/TTS/口型同步）由 Mosaic 框架离线提供，无需在线 API 调用 |
| **Celery 异步** | Redis + Celery 任务队列，前端实时进度反馈 |
| **一键启动** | `drama serve` + `drama worker` |
| **注册表驱动** | `models_registry.yaml` 统一管理所有后端元数据，新增后端只改 YAML |
| **DI 容器** | 后端自注册 + 按需创建 + 热重载 + 懒加载 |
| **人性化工作台** | 内联编辑、撤销重做、批量执行、资源预览 |
| **多语言界面** | 中文/English 双语支持 |
| **Seko 策划案** | 集成影视策划案生成/修改（Mosaic 离线 LLM 驱动） |
| **Mosaic 内置一致性** | Mosaic 框架内置角色面部/身体一致性方案（IP-Adapter/PuLID 等），无需额外安装自定义节点 |
| **框架导入检测** | 启动时自动检测 Mosaic 框架已导入的能力，一致性方案按可用能力动态跳过 |
| **声线库** | 1000 种声线一键选用，搜索/试听/分配到角色 |
| **安全加固** | 输入校验、路径遍历防护、速率限制 |
| **防御式后端** | AIToolkitTrainer / Mosaic / VideoBase 全部标准化 health_check + shutdown |

---

## 🚀 快速开始

### 1. 克隆

```bash
git clone https://ghfast.top/https://github.com/brother2050/ai-drama-pipeline.git
cd ai-drama-pipeline
```

### 2. 安装依赖

```bash
# 基础安装（Web + Celery + Mosaic 离线 TTS）
pip install -e .

# 含横转竖人脸追踪
pip install -e ".[vertical]"

# 全量安装
pip install -e ".[all]"
```

<details>
<summary>可选依赖详情</summary>

| 安装方式 | 包 | 用途 | 不装影响 |
|---------|---|------|---------|
| `.[vertical]` | face_recognition | 横转竖人脸追踪定位 | 回退到模糊背景 |
| `.[vertical]` | opencv-python-headless | 视频帧读取 | 回退到模糊背景 |

不装可选包时，各功能自动降级，不会崩溃。

</details>

### 3. 安装 Mosaic 框架（图像/视频/LLM 后端）

> 项目已从在线 API（ComfyUI/OpenAI/MuseTalk 等）迁移到 **Mosaic 框架的离线方法**。Mosaic 统一管理图像生成、视频生成、LLM、TTS、口型同步等所有后端，无需单独部署 ComfyUI 或申请任何在线 API Key。
>
> 生成参数由 `engines.generation` 直接构建，不再使用 ComfyUI 工作流 JSON 模板。

#### 3.1 安装 Mosaic

Mosaic 框架不作为 pip 包安装，通过 PYTHONPATH 使用：

```bash
# 将 Mosaic 源码目录加入 PYTHONPATH（替换为实际路径）
export PYTHONPATH=/path/to/mosaic:$PYTHONPATH
```

#### 3.2 模型管理

Mosaic 框架在首次运行时自动下载并缓存所需模型（Flux / Cosmos / SD1.5 / CogVideoX / HiDream 等），模型统一存放在 Mosaic 自己的模型目录中，**无需手动下载到 `ComfyUI/models/`**。

| 后端 | 推荐显存 | 说明 |
|------|---------|------|
| **Flux（默认）** | ≥32GB | 顶级画质（fp16） |
| **Cosmos** | ~12GB | 文本到图像，性价比最高 |
| **SD1.5** | ~6GB | 入门级，显存友好 |
| **CogVideoX（可选）** | ≥24GB | 高质量视频生成 |
| **HiDream（可选）** | ≥24GB | 高质量图像重绘 |

> **GPU 兼容性速查**：
>
> | GPU | 显存 | 推荐后端 | 说明 |
> |-----|------|---------|------|
> | T4 | 16GB | Cosmos / SD1.5 | Flux fp16 不行 |
> | A10 | 24GB | Cosmos / SD1.5 | Flux fp16 不行 |
> | V100-32G | 32GB | Flux / Cosmos | Flux fp16 可用 |
> | A100-40G | 40GB | Flux fp16 / Cosmos | 全部后端可用 |
> | A100-80G | 80GB | 全部 | 无限制 |

#### 3.3 切换后端

在 `config/system.yaml` 中切换图像/视频后端，Mosaic 会自动加载对应模型：

```yaml
models:
  image_backend: "flux"        # flux / cosmos / sd15 / hidream
  video_backend: "cosmos-video" # cosmos-video / animatediff / cogvideox
```

### 4. 启动 Redis + PostgreSQL（必选）

```bash
# Ubuntu
sudo apt install redis-server && sudo systemctl start redis
sudo apt install postgresql && sudo systemctl start postgresql

# macOS
brew install redis && brew services start redis
brew install postgresql@16 && brew services start postgresql@16

# Docker
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=drama123 -e POSTGRES_USER=drama -e POSTGRES_DB=ai_drama postgres:16-alpine
```

#### 初始化数据库（Ubuntu / macOS 手动安装）

安装完成后，创建用户和数据库:

```bash
# 1. 创建 drama 用户（若尚不存在）
sudo -u postgres psql -c "CREATE USER drama WITH PASSWORD 'drama123';"

# 2. 创建 ai_drama 数据库（属主为 drama）
sudo -u postgres psql -c "CREATE DATABASE ai_drama OWNER drama;"

# 3. 授予 drama 用户建表权限
sudo -u postgres psql -c "GRANT ALL ON DATABASE ai_drama TO drama;"
```

> **macOS 注意**：Homebrew 安装后默认用户为系统用户名。若 `sudo -u postgres` 无效，可先用系统用户连接创建：
> ```bash
> psql -h 127.0.0.1 -U $(whoami) -d postgres -c "CREATE USER drama WITH PASSWORD 'drama123' SUPERUSER;"
> psql -h 127.0.0.1 -U $(whoami) -d postgres -c "CREATE DATABASE ai_drama OWNER drama;"
> ```

> **PostgreSQL 启动失败？（macOS 僵尸锁文件）**
>
> 若 `brew services` 显示 `error`，日志提示 `lock file "postmaster.pid" already exists`：
> ```bash
> # 检查是否有残留 postgres 进程
> ps aux | grep postgres | grep -v grep
> # 无运行进程则可安全删除锁文件
> rm /usr/local/var/postgresql@16/postmaster.pid
> # Apple Silicon 路径可能是 /opt/homebrew/var/postgresql@16/postmaster.pid
> # 重启服务
> brew services restart postgresql@16
> ```

### 5. 配置

```bash
cp .env.example .env
# 编辑 .env，必填:
#   AI_DRAMA_DB_DSN=postgresql://drama:drama123@127.0.0.1:5432/ai_drama
# TTS / LLM / 图像 / 视频均使用 Mosaic 离线后端，无需任何 API Key
```

### 6. 启动

> ⚠ **需要打开两个终端窗口**，分别运行 Worker 和 Web 工作台。它们是独立进程，不能在同一终端同时运行。

```bash
# 终端 1: 启动 Celery Worker（处理异步任务）
drama worker

# 终端 2: 启动 Web 工作台
drama serve

# 浏览器打开 http://localhost:8888
```

> **并发数说明**：默认 concurrency=2，个人使用推荐 2-4。
>
> 主生产流程（镜头生产）内部是逐镜头串行执行的，concurrency 设置不影响主流程速度。并发数主要影响 Web 工作台中多个操作同时提交时的响应（如同时生成定妆照和场景图）。Mosaic 离线后端（图像/TTS）通常是单实例单任务，设置过高的并发不会加速反而浪费内存。
>
> ```bash
> drama worker -c 2   # 默认，省资源
> drama worker -c 4   # Web 操作较多时推荐
> ```

### 7. Mosaic 内置一致性方案（角色面部/身体一致性）

> 项目已移除 ComfyUI 自定义节点（IPAdapter/PuLID/ControlNet 等）的安装说明。Mosaic 框架内置角色面部与身体一致性方案，无需单独下载 IP-Adapter / PuLID / InsightFace / ControlNet 模型，也无需克隆任何 ComfyUI 自定义节点仓库。
>
> 定妆照的面部特征会通过一致性方案注入到每个镜头的首帧生成中，大幅提升同一角色在不同镜头间的辨识度。一致性方案与图像后端**独立配置**，通过 `consistency_method` 字段选择：

```yaml
# config/system.yaml
consistency_method: auto   # auto / pulid_flux / ip_adapter / none
#   auto:        根据 image_backend 自动选择（flux→pulid_flux + flux_ip_adapter 管道, sd15→ip_adapter, cosmos→none）
#   pulid_flux:  强制使用 PuLID-Flux（需 Flux 后端）
#   ip_adapter:  强制使用 IP-Adapter Plus（需 SD1.5/SDXL 后端）
#   none:        不使用一致性方案（仅靠 LoRA + seed）
```

#### 7.1 后端兼容性

| 图像后端 | 架构 | 可用一致性方案 | 说明 |
|---------|------|:-------------:|------|
| `flux` | DiT | **PuLID-Flux + Flux IP-Adapter FaceID** | **推荐**，双层管道：PuLID 做主锚定 + FaceID IP-Adapter 加固 |
| `sd15` | UNet | IP-Adapter Plus | 成熟稳定，面部一致性好 |
| `cosmos` | DiT | 无 | 仅 LoRA 训练 |

> Flux 后端默认启用 `flux_identity` **一致性管道**：PuLID-Flux（Layer 1）→ Flux IP-Adapter FaceID（Layer 2），两层叠加实现最强的身份保持。若 Mosaic 未提供 FaceID 能力，自动降级为纯 PuLID。

#### 7.2 框架导入检测

> **启动时自动检测**：管线启动时会检测 Mosaic 框架已导入的能力，与 YAML 中每个一致性方案的工作流节点需求（定义在 `models_registry.yaml`）比对。若所需能力未导入，对应方案自动跳过（带 Warning 日志），不会报错中断。检查统一在 `inject_from_registry()` 入口执行，覆盖泛型 `NodeGraphInjector` 和 `inject_method` 覆盖（如 ControlNet Depth）两条路径。

#### 7.3 配置示例

```yaml
# PuLID-Flux（Flux 后端）
pulid_flux:
  enabled: true
  model: "pulid_flux_v0.9.0.safetensors"
  weight: 0.9              # 推荐 0.8-0.95（1.0 过拟合）
  fusion: "mean"           # 多图融合方法: mean / concat / max / train_weight
  use_gray: true           # 灰度优化（边缘轮廓更自然）

# IP-Adapter Plus（SD1.5/SDXL 后端）
ip_adapter:
  enabled: true
  model: "ip-adapter-plus-face_sd15.safetensors"
  clip_vision: "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
  weight: 0.75              # 参考图权重（官方建议 ≤0.8）
  secondary_weight: 0.45    # 多角色时次要角色权重
  embeds_scaling: "V only"  # 面部特征保持最佳的缩放模式

# Flux IP-Adapter FaceID（管道 Layer 2）
ip_adapter_flux_shakker:
  enabled: true
  model: "ip-adapter.bin"                            # InstantX IP-Adapter 权重
  weight: 0.7              # 管道 Layer 2 权重（Layer 1 PuLID 为主锚，此层为加固）

# ControlNet Depth（全身结构一致性，可选，默认禁用）
controlnet_depth:
  enabled: false               # 默认禁用
  model: "flux-depth-controlnet-v3.safetensors"
  strength: 0.8                # ControlNet 强度（0.5-1.0，越高结构越严格）
  start_percent: 0.0           # 生效起始步（0.0 = 从头开始）
  end_percent: 1.0             # 生效结束步（1.0 = 全程生效）
```

> 上述模型文件由 Mosaic 框架统一管理，无需手动下载到 `ComfyUI/models/` 目录。

#### 7.4 管道联动

Flux 后端默认启用 `flux_identity` 一致性管道，PuLID-Flux 作为 Layer 1（人脸锚定），自动叠加 Layer 2 的 Flux IP-Adapter FaceID 做身份加固。管道各层独立可用性检测，Mosaic 缺少某层能力时自动降级。

```
UNETLoader
    │
    ▼ (model)
ApplyPulidFlux          ← Layer 1, PuLID-Flux, weight=0.85（主锚定）
    │
    ▼ (model)
ApplyIPAdapterFlux      ← Layer 2, FaceID IP-Adapter, weight=0.7（加固）
    │
    ▼ (model)
KSampler
```

> 降级行为：若 Mosaic 缺少 Flux IP-Adapter 能力 → 自动回退为纯 PuLID-Flux（单层）。不会报错中断。

#### 7.5 技巧

- **参考图质量很重要**：使用清晰、正面、光线均匀的定妆照
- **weight 推荐 0.8-0.95**：1.0 容易过拟合，面部僵硬
- **多角色同框**：自动链式注入，主角色 weight=0.9，次要角色自动降权
- **ControlNet Depth**：与 IP-Adapter/PuLID 并行工作，前者控制身体结构，后者控制面部，可同时接入 KSampler

#### 7.6 验证

启动后在 Web 工作台仪表盘查看一致性方案状态，或 CLI：

```bash
drama status   # 应显示一致性方案 ✅
```

### 8. TTS 后端（语音合成）

> 项目使用 **Mosaic 离线语音合成**作为唯一 TTS 后端。已移除 mimo-voicedesign、mimo-voiceclone、gpt-sovits、cosyvoice、fish-speech、chattts 等在线/云 TTS 后端，统一为离线 Mosaic 实现，无需任何 API Key。

#### Mosaic 离线 TTS（默认，零配置）

Mosaic 为离线语音合成后端，开箱即用，无需部署额外服务或申请 API Key。

```yaml
# config/system.yaml
models:
  tts_backend: mosaic
```

**参考音频配置**（每个角色独立）：

```yaml
# projects/<项目>/config/characters/林夏.yaml
character:
  voice:
    # ── Mosaic 离线参数 ──
    voice_description: "清脆甜美的少女音"          # 声音描述
    core_traits: "温柔但坚强"                     # 核心特质
    reference_audio: "/path/to/linxia_ref.wav"   # 参考音频（离线声音克隆，可选）
```

**预设音色**（Web 工作台角色编辑页面下拉选择）：

| 音色 | 语言 | 特征 |
|------|------|------|
| 冰糖 | 中文女声 | 清脆甜美 |
| 茉莉 | 中文女声 | 温柔自然 |
| 苏打 | 中文男声 | 沉稳浑厚 |
| 白桦 | 中文男声 | 低沉磁性 |
| Mia | English Female | Clear & sweet |
| Chloe | English Female | Warm & soft |
| Milo | English Male | Steady & deep |
| Dean | English Male | Rich & resonant |

### 9. 声线库（1000 种声线）

> 内置 1000 种声线 WAV 参考音频，一键选用到角色。

```bash
# 同步声线库（克隆仓库 + 生成索引）
drama voices

# 已有 WAV 文件？直接生成索引（不联网）
drama voices --index-only
```

**Web 工作台使用**：

1. 左侧导航 → 🎤 声线库
2. 搜索/筛选（性别、场景、风格）
3. ▶ 试听 → 选择合适的声线
4. 点击「选用」→ 选择角色 → 自动复制音频 + 更新角色 YAML

**存储**：

```
shared_assets/voices/          # 声线库（.gitignore 已屏蔽）
├── voices.json                # 索引（自动生成）
├── 001_汽车品牌广告_沉稳男声.wav
├── ...
└── 1000_第一千种声音_你的声音.wav
```

### 五阶段架构（推荐工作流）

> 以下所有操作均通过 Web 工作台完成（http://localhost:8888）

```
阶段1: AI 分镜（LLM，运行一次）
  └─ 从大纲生成分镜表 → DB

阶段2: AI 实体（LLM，运行一次）
  └─ 从分镜提取引用 → 批量生成缺失的角色/场景 → YAML

阶段3: 准备（LLM 密集，运行一次）
  ├─ 批量翻译 outfits/场景/分镜 → 写入 YAML *_en 字段
  └─ 视角 prompt 生成：appearance → appearance_prompt_en（AI 绘图格式）

阶段4: 生产（纯 GPU/本地，零 LLM 调用，全速）
  ├─ 定妆照 / 场景图（Web 工作台按需执行，或一键全流程自动执行）
  └─ TTS → 首帧 → 视频 → 口型同步

阶段5: 后期（纯本地）
  └─ 拼接 → 字幕 → 配乐 → 横转竖
```

**阶段职责分离**：每个阶段做一件事，失败时只需重试当前阶段。GPU 用户可灵活组合（如手动创建角色后跳过阶段 2）。

**收益**: 准备跑完后，生产完全不依赖 LLM，10 个镜头从 30-40 次 LLM 调用降为 0 次。

---

## 📖 CLI 命令

```bash
# 服务管理
drama serve                            # 启动 Web 工作台
drama worker                           # 启动 Celery Worker
drama worker -c 4                      # Worker 并发数 4
drama status                           # 服务状态（Redis + Celery + Mosaic + TTS）
drama env                              # 环境信息（OS / Python / GPU / Redis）

# 数据导入导出
drama import plan.json                 # 从 JSON 导入剧本项目
drama import batch2.json --append      # 追加导入（解决 LLM 截断）
drama export 1                         # 导出分镜到 CSV
drama export 1 -o output.csv           # 指定输出路径

# 清理
drama clean --logs                     # 清理日志
drama clean --cache                    # 清理缓存

# 角色管理
drama outfit-regenerate <project> <char_id>   # 重新生成角色服装参考图
                                             # 用于调试服装图面部一致性（提高一致性方案权重）

# 声线库
drama voices                           # 同步声线库
drama voices --index-only              # 已有 WAV 直接生成索引

# 环境预配置
drama setup --insightface              # 预下载 InsightFace buffalo_l 人脸检测模型
                                       # Mosaic 一致性方案使用，避免首次运行触发慢速下载（~275MB）
```

> 所有生产操作（AI 生成、翻译、生产、后期、项目管理）均通过 Web 工作台完成。

---

## 🌐 Web 工作台

启动 `drama serve` 后访问 http://localhost:8888

| 页面 | 功能 |
|------|------|
| 📊 仪表盘 | 系统状态总览（Redis / Celery / Mosaic / TTS / LipSync / LLM） |
| 👤 角色管理 | 创建/编辑/删除角色 + 🤖 AI 从描述生成 |
| 🏔️ 场景管理 | 创建/编辑/删除场景 + 🤖 AI 从描述生成 |
| 📝 分镜表 | 内联编辑表格 + 🤖 AI 从大纲一键生成 |
| 🎬 生产管线 | 五阶段执行：AI 分镜 → AI 实体 → 准备 → 生产 → 后期 |
| 📂 项目管理 | 多项目切换 |
| 🎤 声线库 | 搜索/试听/选用声线到角色 |
| ⚙️ 系统设置 | TTS/Mosaic/LipSync/**LLM** 配置、语言切换 |

### 工作台快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Z` | 撤销 |
| `Ctrl+Shift+Z` / `Ctrl+Y` | 重做 |
| `ESC` | 关闭弹窗/预览 |

---

## 📚 API 文档

启动 Web 工作台后访问：
- **Swagger UI**: http://localhost:8888/docs
- **ReDoc**: http://localhost:8888/redoc

---

## 🏗️ 架构

```
┌─────────────┐     POST /api/pipeline/run     ┌──────────────┐
│   Web 前端   │ ──────────────────────────────→ │   FastAPI    │
│  (内联编辑)   │ ←────────────────────────────── │   (提交任务)  │
│  撤销/重做    │     { task_id, poll_url }        └──────┬───────┘
│  批量执行     │                                         │
│  资源预览     │     GET /api/tasks/{id}                 │ .delay()
│             │ ──────────────────────→                 ▼
│             │ ←──────────────┐              ┌──────────────────┐
└─────────────┘   { progress } │              │  Celery + Redis  │
                               │              │  (任务队列)       │
                               │              └────────┬─────────┘
                               │                       │
                               │              ┌────────▼─────────┐
                               └──────────────│  Celery Worker   │
                                              │  TTS / Mosaic    │
                                              │  LipSync / FFmpeg│
                                              └──────────────────┘
```

**流程**: Web 提交 → Redis 队列 → Worker 执行 → 实时更新进度 → 前端轮询展示

### 后端懒加载

后端模块按需加载，缺依赖自动跳过不崩溃：

```
api/__init__.py (懒加载)
  ├─ tts/mosaic            → Mosaic 离线 TTS（无需 API Key）
  ├─ lipsync/mosaic        → Mosaic 离线口型同步（无需 API Key）
  ├─ image/mosaic          → Mosaic 离线图像生成（无需 API Key）
  ├─ video/mosaic          → Mosaic 离线视频生成（无需 API Key）
  ├─ llm/mosaic            → Mosaic 离线 LLM（无需 API Key）
  ├─ music/mosaic          → Mosaic 离线配乐（无需 API Key）
  └─ music/template        → 仅需 ffmpeg（无额外依赖）
```

### 注册表驱动

所有后端元数据集中在 `config/models_registry.yaml`，代码中零硬编码后端名：

```yaml
# 新增后端只需在注册表中声明，不改代码
image_backends:
  sd15:
    prompt_style: "tag"              # prompt 风格
    consistency_default: "ip_adapter" # 默认一致性方案
  flux:
    prompt_style: "natural"
    consistency_default: "pulid_flux"

video_backends:
  animatediff:
    frame_params:                    # 帧数注入规则
      node_class: "ADE_StandardStaticContextOptions"
      input_name: "context_length"

consistency_methods:                 # 一致性方案元数据
  ip_adapter:
    compatible_backends: ["sd15", "sdxl"]
    inject_method: "_inject_ip_adapter_plus"
    required_node: "IPAdapterAdvanced"   # 工作流节点需求（Mosaic 框架导入检测）

services:                            # 辅助服务健康检查
  mosaic:
    health_check:
      type: "import"
      module: "mosaic"
```

注册表覆盖范围：
- **TTS / LipSync / LLM / Music / Image / Video** — 所有后端的健康检查、默认值
- **prompt 风格** — `tag`（SD1.5 CLIP）或 `natural`（Flux/Cosmos T5）
- **一致性方案** — 与图像后端的兼容关系、注入方法、所需 Mosaic 能力
- **帧数参数** — 视频后端的节点类型 + 参数名映射
- **生产步骤** — shot_task 的步骤编排
- **工具检测** — 健康检查类型驱动，零 if-elif

---

## ⚙️ 配置

编辑 `projects/<项目名>/config/project.yaml`：

```yaml
project:
  name: "我的短剧"
  episodes: 1
  fps: 24
  resolution: [1280, 720]
  style: "cinematic"
  genre: "urban"

models:
  tts_backend: "mosaic"                # Mosaic 离线语音合成（开箱即用，无需 API Key）
  lip_sync_backend: "mosaic"           # Mosaic 离线口型同步
  music_backend: "mosaic"              # Mosaic 离线配乐
  image_backend: "flux"                # Mosaic 离线图像生成
  video_backend: "cosmos-video"        # Mosaic 离线视频生成

llm:
  enabled: true
  backend: "mosaic"                    # Mosaic 离线 LLM（无需 API Key）
  model: "Qwen/Qwen2.5-7B-Instruct"
  max_output: 8192
  batch_translate: true                # 批量翻译（多条合并一次 LLM 调用，false 则逐条翻译）

portraits:
  auto_outfit: true                    # 管线中自动生成 outfit 参考图（默认 true）

timeouts:
  image: 300                           # 图像生成超时
  video: 600                           # 视频生成超时
  tts: 60
  lipsync: 120
  llm: 120
  music: 300
```

### LLM 配置示例

```yaml
# Mosaic 离线 LLM（默认，零配置）
llm:
  enabled: true
  backend: "mosaic"
  model: "Qwen/Qwen2.5-7B-Instruct"
  max_output: 8192

# 切换其他 Mosaic 本地模型
llm:
  enabled: true
  backend: "mosaic"
  model: "Qwen/Qwen2.5-14B-Instruct"
  max_output: 8192
```

配置加载支持：
- 默认值自动合并
- mtime 缓存（修改后自动重载）
- 必填字段校验
- 数值范围校验

---

## 🧪 测试

```bash
# 运行全部测试（348 项）
pytest tests/ -v

# 分类运行
pytest tests/test_all.py -v           # 基础功能
pytest tests/test_api.py -v           # API 集成测试
pytest tests/test_celery.py -v        # Celery 任务测试
pytest tests/test_e2e.py -v           # 前端 E2E 测试
pytest tests/test_core.py -v          # 核心引擎测试
pytest tests/test_dialogue.py -v      # 对话解析测试
pytest tests/test_post.py -v          # 后期处理测试
pytest tests/test_session_changes.py -v  # 会话变更回归测试
pytest tests/test_append.py -v        # 追加导入测试
pytest tests/test_full_coverage.py -v # 覆盖率补充测试
```

---

## 📁 项目结构

```
ai-drama-pipeline/
├── cli/                          # CLI 入口（Click + Rich）
│   ├── __init__.py               #   主命令组 + 共享工具（Celery 轮询/环境检测）
│   ├── __main__.py               #   python -m cli 支持
│   ├── io.py                     #   import / export 命令
│   └── system.py                 #   serve / worker / status / env / clean 命令
├── pyproject.toml                # 依赖与构建配置
├── .env.example                  # 环境变量模板
│
├── api/                          # 后端层（懒加载 + DI 容器）
│   ├── __init__.py               # 懒加载注册（按 models_registry.yaml 动态导入）
│   ├── registry.py               # 服务注册表 + Container（DI 容器）
│   └── backends/                 # 后端实现
│       ├── tts/                  #   TTS: mosaic（离线语音合成）
│       ├── lipsync/              #   口型同步: mosaic（离线 Wav2Lip/SadTalker）
│       ├── image/                #   图像生成: mosaic（离线 SD1.5/Flux/Cosmos/HiDream）
│       ├── video/                #   视频生成: mosaic（离线 AnimateDiff/CogVideoX/Cosmos-Video）
│       ├── llm/                  #   LLM: mosaic（离线 HuggingFace 本地模型）
│       ├── music/                #   配乐: mosaic（离线 MusicGen）、template（FFmpeg）
│       ├── seko/                 #   Seko 影视策划案（Mosaic 离线 LLM 驱动）
│       └── training/             #   LoRA 训练: mosaic（离线 diffusers + peft）
│
├── engines/                      # 引擎层（核心业务逻辑）
│   ├── dialogue.py               #   对话解析
│   ├── quality_gate.py           #   质量门禁系统（管线各阶段自动检查）
│   ├── generation.py             #   生成参数直接构建（首帧/视频，替代 ComfyUI 工作流 JSON）
│   ├── content/                  #   内容生成子包
│   │   ├── storyboard.py         #     分镜表加载/验证/保存（DB 为唯一数据源）
│   │   ├── llm.py                #     LLM 内容生成编排
│   │   ├── generator.py          #     LLM 内容生成器（分镜/角色/场景）
│   │   ├── portrait.py           #     定妆照生成（五视图 + 服装图）
│   │   ├── episode.py            #     集级状态管理
│   │   └── validator.py          #     实体校验
│   ├── prompt/                   #   Prompt 子包
│   │   ├── builder.py            #     Prompt 构建
│   │   ├── compiler.py           #     Mustache 风格模板编译器（从 prompt_templates.yaml 加载）
│   │   ├── translate.py          #     LLM 翻译（批量/单条）
│   │   └── view.py               #     Prompt 视图
│   ├── workflow/                 #   工作流子包
│   │   ├── builder.py            #     工作流构建（首帧/视频，含 mtime 缓存）
│   │   ├── node_graph.py         #     工作流节点图
│   │   ├── utils.py              #     工作流工具
│   │   ├── inject.py             #     一致性方案注入（IP-Adapter/PuLID/LoRA）
│   │   ├── upload.py             #     资产上传
│   │   └── video.py              #     视频生成工作流
│   ├── consistency/              #   一致性子包
│   │   ├── bible.py              #     角色圣经系统（跨镜头一致性）
│   │   └── checker.py            #     分镜一致性校验（服装/角色/场景/情绪）
│   └── utils/                    #   工具子包
│       ├── entity.py             #     实体生成公共工具（统一角色/场景的生成+保存逻辑）
│       ├── multi_char.py         #     多人同框 prompt 处理
│       └── shot.py               #     镜头工具（后处理、文本清理、角色 ID 解析）
│
├── pipeline/                     # Celery 异步任务
│   ├── app.py                    #   Celery 配置 + 统一错误格式 + Worker 启动钩子
│   ├── portraits.py              #   定妆照批量生成
│   ├── scene_images.py           #   场景图批量生成
│   └── tasks/                    #   任务定义（按职责拆分）
│       ├── pipeline.py           #     管线编排（shot_task / produce / post / run_all）
│       ├── steps/                #     单镜头步骤模块
│       │   ├── tts.py            #       TTS 语音合成
│       │   ├── frame.py          #       首帧生成
│       │   ├── video.py          #       视频生成
│       │   └── lipsync.py        #       口型同步
│       ├── ai.py                 #     AI 生成（分镜/实体/准备/对话编辑）
│       ├── portrait.py           #     定妆照 / 场景图生成任务
│       ├── media.py              #     后期 / TTS / 配乐 / 字幕任务
│       ├── training.py           #     LoRA 训练 / JSON 导入任务
│       ├── preflight.py          #     预检任务
│       ├── prepare.py            #     准备阶段任务
│       ├── seko.py               #     Seko 策划案导入任务
│       └── helpers.py            #     共享工具（加载/校验/DB 记录/上下文缓存）
│
├── post/                         # 后期处理
│   ├── production.py             #   后期合成流水线（拼接→字幕→配乐→横转竖）
│   ├── subtitle.py               #   SRT 字幕生成
│   ├── music.py                  #   配乐生成（FFmpeg 模板）
│   └── vertical.py               #   横转竖（含人脸检测定位）
│
├── infra/                        # 基础设施
│   ├── constants.py              #   共享常量（情绪/景别/运镜/状态码/步骤名）
│   ├── globals.py                #   全局基础设施实例（看门狗/健康缓存/并发组）
│   ├── hooks.py                  #   后端钩子系统（init/cleanup/health_check/cache_invalidate）
│   ├── http_pool.py              #   HTTP 连接池（httpx，按 base_url+timeout 缓存）
│   ├── json_parse.py             #   LLM JSON 解析（容错：截断修复/代码块提取/单引号兼容）
│   ├── models.py                 #   共享数据模型（ImportPlan/ImportValidator/normalize_character）
│   ├── network.py                #   网络工具（端口检测）
│   ├── normalize.py              #   数据规范化
│   ├── toolcheck.py              #   工具可用性检测（注册表驱动，零 if-elif）
│   ├── transitions.py            #   转场拼接（xfade offset 精确计算）
│   ├── validation.py             #   输入校验
│   ├── compute/                  #   计算子包
│   │   ├── ffmpeg.py             #     FFmpeg 封装（链式 API）
│   │   └── gpu.py                #     GPU / 生成参数配置
│   ├── concurrency/              #   并发控制子包
│   │   ├── batch.py              #     自适应批处理器（三重约束分批 + 错误驱动学习）
│   │   ├── executor.py           #     安全执行器（任务级错误边界 + 超时 + 降级）
│   │   ├── groups.py             #     并发组（互斥锁按资源组管理）
│   │   └── monitor.py            #     任务监控（超时检测 + 空闲淘汰 + 健康检查缓存）
│   ├── config/                   #   配置子包
│   │   ├── core.py               #     配置管理核心（mtime 缓存 + 热重载 + 注册表默认值合并）
│   │   ├── cache.py              #     配置缓存
│   │   ├── loader.py             #     配置加载器
│   │   ├── paths.py              #     路径管理
│   │   ├── registry.py           #     模型注册表
│   │   ├── registry_llm.py       #     LLM 注册表
│   │   ├── registry_media.py     #     媒体注册表
│   │   └── resolver.py           #     配置解析器
│   ├── storage/                  #   存储子包
│   │   ├── asset_tracker.py      #     Mosaic 资产跟踪（PostgreSQL 持久化）
│   │   └── file_watcher.py       #     文件系统监控（YAML 变化自动失效缓存）
│   └── database/                 #   PostgreSQL（分镜表/生成状态/资产跟踪）
│       ├── schema.py             #     表结构定义（CREATE IF NOT EXISTS）
│       ├── pool.py               #     连接池（ThreadedConnectionPool）
│       ├── _db.py                #     共享工具（项目自动解析 + query 上下文管理器）
│       ├── storyboard_db.py      #     分镜 CRUD + CSV 导出
│       ├── generation.py         #     生成状态 CRUD
│       └── comfyui_assets.py     #     资产跟踪表（Mosaic 资源上传记录）
│
├── web/                          # FastAPI Web 工作台
│   ├── app.py                    #   应用工厂 + 日志配置 + lifespan
│   ├── services/__init__.py      #   日志配置服务
│   ├── schemas/__init__.py       #   Pydantic 请求/响应模型（25+ 个 Schema）
│   ├── routers/                  #   API 路由（按领域拆分）
│   │   ├── api.py                #     路由聚合入口
│   │   ├── system_tools.py       #     系统状态 / 工具管理 / 配置 / 单步执行（26 路由）
│   │   ├── characters.py         #     角色 CRUD + 定妆照生成（7 路由）
│   │   ├── scenes.py             #     场景 CRUD + 场景图生成（5 路由）
│   │   ├── storyboard.py         #     分镜表 / 集数 / 管线 / LLM 生成（18 路由）
│   │   ├── assets.py             #     资产上传/下载/共享库（7 路由）
│   │   ├── imports.py            #     项目管理 / 导入 / Seko / 训练（14 路由）
│   │   ├── voices.py             #     声线库（列表/试听/分配，3 路由）
│   │   └── deps.py               #     共享依赖（配置访问/校验/任务提交/YAML CRUD）
│   └── static/                   #   前端 SPA
│       ├── index.html            #     单页应用（9 个页面：仪表盘/角色/场景/分镜/管线/项目/资产/Seko/设置）
│       ├── css/style.css         #     样式
│       ├── js/                   #     JS 模块（15 个：core/app/i18n/dashboard/characters/scenes/storyboard/pipeline/projects/tasks/settings/ai-gen/seko/extras/voices）
│       └── favicon.svg
│
├── scripts/                      # 工具脚本
│   ├── project_mgr.py            #   项目管理（新建/切换/删除/预设列表）
│   ├── project_builder.py        #   项目构建器（JSON 导入时原子性创建项目）
│   ├── ai_toolkit_api.py         #   AI Toolkit 训练 API 客户端
│   ├── musicgen_server.py        #   MusicGen API 服务器
│   └── voice_sync.py             #   声线库同步（克隆仓库 + 生成索引）
│
├── tests/                        # 测试（15 个测试文件）
│   ├── conftest.py               #   共享 fixtures + 环境检测
│   ├── test_all.py               #   基础功能测试
│   ├── test_api.py               #   API 集成测试
│   ├── test_append.py            #   追加导入测试
│   ├── test_celery.py            #   Celery 任务测试
│   ├── test_core.py              #   核心引擎测试
│   ├── test_dialogue.py          #   对话解析测试
│   ├── test_e2e.py               #   前端 E2E 测试
│   ├── test_full_coverage.py     #   覆盖率补充测试
│   ├── test_import_e2e_standalone.py  # 导入 E2E 测试
│   ├── test_import_standalone.py #   导入测试
│   ├── test_node_graph.py        #   节点图测试
│   ├── test_p2_review.py         #   P2 审查测试
│   ├── test_post.py              #   后期处理测试
│   └── test_session_changes.py   #   会话变更回归测试
│
├── config/                       # 全局配置
│   ├── system.yaml               #   系统全局配置（Mosaic 离线后端/LLM/TTS/一致性方案/预设）
│   ├── models_registry.yaml      #   模型注册表（所有后端元数据的唯一真相来源）
│   ├── prompt_templates.yaml     #   Prompt 模板（翻译/分镜/角色/场景/圣经生成）
│   └── default_storyboard.py     #   默认分镜种子数据
│
├── shared_assets/                # 全局共享资产（.gitignore 屏蔽）
│   └── voices/                   #   声线库（drama voices 同步）
│
├── projects/                     # 项目目录（每个短剧独立）
│   ├── .active                   #   当前活动项目指针
│   ├── default/                  #   默认项目模板
│   │   ├── config/
│   │   │   ├── project.yaml      #     项目配置
│   │   │   ├── characters/       #     角色配置
│   │   │   └── scenes/           #     场景配置
│   │   ├── assets/               #     资产（定妆照/场景图/LoRA）
│   │   └── output/               #     生成产物
│   └── <你的项目名>/             #   新建项目（结构同上）
│
└── docs/                         # 文档
    ├── pipeline.md               #   管线全流程架构详解
    ├── PROJECT_FLOWCHART.md      #   项目流程总览
    ├── musicgen-deploy.md        #   MusicGen 部署指南
    └── internal/
        └── script-import-design.md   # 剧本导入功能设计文档
```

---

## 🔧 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Redis 未运行` | Redis 服务未启动 | `redis-server --daemonize yes` 或 `brew services start redis` |
| `AI_DRAMA_DB_DSN 未配置` | 缺少 `.env` 文件 | `cp .env.example .env` 并填写 PostgreSQL 连接信息 |
| `PostgreSQL 连接被拒绝` | PostgreSQL 未启动 | 见下方「PostgreSQL 启动方式」 |
| `PostgreSQL 认证失败` | 用户名/密码不匹配 | 检查 `.env` 中的 `AI_DRAMA_DB_DSN`，确认用户和密码 |
| `数据库不存在` | 未创建 ai_drama 数据库 | `sudo -u postgres psql -c "CREATE DATABASE ai_drama OWNER drama;"` |
| `Celery Worker 未启动` | Worker 进程未运行 | 在另一个终端运行 `drama worker` |
| `Mosaic 不可达` | Mosaic 框架未正确导入 | 确认 Mosaic 已通过 PYTHONPATH 导入：`echo $PYTHONPATH`。Mosaic 离线运行，无需启动独立服务 |
| `TTS 不可用` | Mosaic 离线 TTS 服务异常 | 检查 Mosaic TTS 服务状态（离线模式，无需 API Key） |
| `LLM 未启用` | LLM 配置未开启 | 在项目配置中设置 `llm.enabled: true`，或在 Web 设置页开启 |
| `角色缺定妆照` | 未生成角色形象图 | Web 工作台「👤 角色」→「🎨 AI 生成定妆照」 |
| `请先执行准备阶段` | 生产前未翻译 | Web 工作台「🎬 生产管线」→「🔧 准备阶段」 |

#### PostgreSQL 启动方式

不同环境下 PostgreSQL 启动命令不同，按顺序尝试：

**方式一：pg_ctlcluster（Debian/Ubuntu）**

```bash
# 查看已安装的 PostgreSQL 版本
ls /etc/postgresql/

# 启动对应版本（替换 <version> 为实际版本号，如 16）
sudo pg_ctlcluster <version> main start

# 例如 PostgreSQL 16：
sudo pg_ctlcluster 16 main start
```

**方式二：systemctl（大多数 Linux 发行版）**

```bash
sudo systemctl start postgresql
```

**方式三：macOS（Homebrew）**

```bash
brew services start postgresql@16
```

**方式四：Docker**

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=drama123 -e POSTGRES_USER=drama -e POSTGRES_DB=ai_drama postgres:16-alpine
```

> **启动后验证**：`sudo -u postgres psql -c "SELECT 1;"` 返回 `1` 表示 PostgreSQL 正常运行。

---

## 🔒 安全

本项目面向**个人本地使用**，安全措施以实用为主，不做过度防护。

已有的安全机制：
- **输入校验**: Pydantic 模型校验 API 请求（ID 格式、数值范围、文本长度）
- **路径遍历防护**: `_safe_path()` 阻断 `../` 攻击
- **任务 ID 校验**: UUID 格式验证

> 个人部署场景下，速率限制（60s/300 次）等功能不构成实际需求。如需暴露到公网，请自行在前端加 Nginx 反向代理并配置认证。

---

## 📝 License

MIT
