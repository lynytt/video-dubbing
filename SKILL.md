---
name: video-dubbing
description: >
  将英文视频自动转写（Whisper）、角色识别、翻译为中文口语、生成多角色 TTS 配音
  （Microsoft Edge TTS 免费）、最终合入原视频输出成品。
  使用场景：(1) 将英文教学/故事/访谈视频转成中文版；
  (2) 需要按角色分配不同音色的配音需求；
  (3) 希望零成本在本地完成整个配音流程。
---

# 视频配音工具 (Video Dubbing)

## 前置依赖

- **Python 3.8+**
- **FFmpeg**（在 PATH 中）
- **Whisper**: `pip install openai-whisper`
- **edge-tts**: `pip install edge-tts`

## 快速开始

```powershell
# 克隆项目
git clone https://github.com/lynytt/video-dubbing.git
cd video-dubbing

# 安装依赖
pip install -r requirements.txt

# 一键配音
python scripts/dub_video.py <英文视频.mp4>
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--whisper-model` | `tiny` | tiny/base/small/medium/large |
| `--tts-speed` | `+0%` | 语速: `+10%` 加速, `-5%` 减速 |
| `--voice-list` | 内置 | 自定义角色音色 JSON |
| `--subtitle-only` | 否 | 仅生成字幕 |
| `--no-video` | 否 | 仅生成配音音频 |
| `--keep-temp` | 否 | 保留临时文件 |

## 音色映射

| 角色 | 音色 | 说明 |
|------|------|------|
| Girl | zh-CN-XiaoyiNeural (+10%) | 可爱女童声 |
| Boy | zh-CN-YunxiNeural (+5%) | 阳光男童声 |
| Mom | zh-CN-XiaoxiaoNeural | 温暖女声 |
| Dad | zh-CN-YunyangNeural | 稳重男声 |
| Rabbit | zh-CN-YunxiNeural (-5%) | 神秘沉稳 |
| Narrator | zh-CN-XiaoxiaoNeural | 旁白 |

> 详细说明见 [README.md](README.md) 和 [scripts/dub_video.py](scripts/dub_video.py)
