# 🎬 Video Dubbing Tool / 视频配音工具

> **将英文视频自动转写、角色识别、翻译为中文口语、生成多角色 TTS 配音并合入视频。**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Whisper](https://img.shields.io/badge/Whisper-OpenAI-green.svg)](https://github.com/openai/whisper)
[![Edge TTS](https://img.shields.io/badge/TTS-Microsoft%20Edge-orange.svg)](https://github.com/rany2/edge-tts)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## ✨ 功能亮点

| 特性 | 说明 |
|------|------|
| 🎤 **自动语音识别** | 基于 OpenAI Whisper，支持 tiny ~ large 多种模型 |
| 👥 **多角色区分** | 自动识别不同说话人（女孩/兔子/妈妈等），分配专属音色 |
| 🌏 **中英翻译** | 内置词典将英文翻译为自然中文口语 |
| 🔊 **多角色 TTS** | 用 Microsoft Edge TTS 为每个角色分配不同音色（免费） |
| 🎯 **时间轴对齐** | 自动调整每段音频长度，精准匹配字幕时间 |
| 🎬 **视频合成** | 将配音合入原视频，保留画质，零损失 |
| 💰 **完全免费** | 全程本地运行，无需 API Key，无需 GPU |

## 🖼️ 工作流程

```
输入视频.mp4
     │
     ├─ Step 1: FFmpeg 提取音频 ───────────► audio.wav
     │
     ├─ Step 2: Whisper 语音转写 ───────────► transcript.json
     │
     ├─ Step 3: 角色识别 + 中文翻译 ────────► script.json
     │                                         subtitles.srt
     │
     ├─ Step 4: Edge TTS 多角色配音 ────────► 34段 mp3
     │
     ├─ Step 5: 时间对齐 + 音频拼接 ────────► dubbing_full.wav
     │
     └─ Step 6: 合入视频 ──────────────────► 最终视频_dubbed.mp4
```

## 🚀 快速开始

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/lynytt/video-dubbing.git
cd video-dubbing

# 2. 安装依赖
pip install -r requirements.txt

# 3. 确保 FFmpeg 已安装
ffmpeg -version   # 检查
```

### 一键配音

```bash
# 最简单的用法
python scripts/dub_video.py 你的视频.mp4

# 用更准的模型
python scripts/dub_video.py 你的视频.mp4 --whisper-model small

# 只生成字幕，不配音
python scripts/dub_video.py 你的视频.mp4 --subtitle-only

# 自定义输出目录 + 语速
python scripts/dub_video.py 你的视频.mp4 --output-dir ./my_dub --tts-speed +10%
```

### 查看可用音色

```bash
python scripts/dub_video.py --list-voices
```

## ⚙️ 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `video` | **(必填)** | 输入英文视频文件路径 |
| `--output-dir` | 视频同目录 | 输出目录 |
| `--whisper-model` | `tiny` | 模型: `tiny`/`base`/`small`/`medium`/`large` |
| `--language` | `en` | 源语言代码 (`en`=英语, `zh`=中文等) |
| `--tts-speed` | `+0%` | 语速调整 (`+10%` 加速, `-5%` 减速) |
| `--voice-list` | 内置 | 自定义角色音色 JSON 配置 |
| `--subtitle-only` | 否 | 仅生成 SRT 字幕 |
| `--no-video` | 否 | 仅生成配音音频，不合成视频 |
| `--keep-temp` | 否 | 保留临时文件 |
| `--batch-size` | `5` | TTS 并行生成批大小 |
| `--list-voices` | 否 | 列出可用音色 |

## 🎭 角色音色映射

### 默认配置

| 角色 | Edge TTS 音色 | 语速 | 说明 |
|------|--------------|------|------|
| 👧 **Girl** | `zh-CN-XiaoyiNeural` | +10% | 可爱女童声，活泼生动 |
| 👦 **Boy** | `zh-CN-YunxiNeural` | +5% | 阳光男童声 |
| 👩 **Mom** | `zh-CN-XiaoxiaoNeural` | +0% | 温暖女声，亲切柔和 |
| 👨 **Dad** | `zh-CN-YunyangNeural` | +0% | 稳重男声，专业可靠 |
| 🐰 **Rabbit** | `zh-CN-YunxiNeural` | -5% | 阳光男声慢速，神秘沉稳 |
| 📖 **Narrator** | `zh-CN-XiaoxiaoNeural` | +0% | 温暖女声，适合旁白 |

### 自定义音色

创建 JSON 文件覆盖默认配置：

```json
{
  "Girl": {
    "voice": "zh-CN-XiaoyiNeural",
    "rate": "+15%",
    "note": "更快的语速，更活泼"
  },
  "Narrator": {
    "voice": "zh-TW-HsiaoChenNeural",
    "rate": "+0%",
    "note": "台湾普通话旁白"
  }
}
```

使用方式：
```bash
python scripts/dub_video.py video.mp4 --voice-list my_voices.json
```

## 📂 输出结构

```
输出目录/
├── subtitles.srt              # 带角色标注的中文字幕
├── dubbing_full.wav           # 完整配音音频
├── 视频名_dubbed.mp4          # 最终配音视频
└── _temp/                     # 临时文件（自动清理）
    ├── audio.wav              # 提取的音频
    ├── transcript.json        # Whisper 转写结果
    ├── script.json            # 角色标注+翻译
    ├── mp3/                   # 各段 TTS
    ├── wav/                   # 转换后 WAV
    └── aligned/               # 时间对齐后片段
```

## 📦 依赖

- **Python 3.8+**
- **FFmpeg** (需在 PATH 中)
- [openai-whisper](https://github.com/openai/whisper) — 语音识别
- [edge-tts](https://github.com/rany2/edge-tts) — 微软 TTS

## 🤝 参与贡献

欢迎 PR！请参考 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 License

[MIT](LICENSE)

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) — 强大的语音识别
- [edge-tts](https://github.com/rany2/edge-tts) — 微软 TTS Python 接口
- [fr0stb1rd/Edge-TTS-Subtitle-Dubbing](https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing) — 时间轴对齐方案参考
- [Daniel-McLarty/Python-Autodub](https://github.com/Daniel-McLarty/Python-Autodub) — 项目结构参考
