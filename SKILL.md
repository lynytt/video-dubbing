---
name: video-dubbing
description: >
  将英文视频自动转写（Whisper）、角色识别、翻译为中文口语、生成多角色 TTS 配音
  （Microsoft Edge TTS 免费）、最终合入原视频输出成品。
  使用场景：(1) 将英文教学/故事/访谈视频转成中文版；
  (2) 需要按角色（儿童/成人/男女）分配不同音色的配音需求；
  (3) 希望零成本在本地完成整个配音流程。
---

# 视频配音工具 (Video Dubbing)

## 前置依赖

确保以下工具已安装：

- **Python 3.8+** 环境
- **FFmpeg**（在 PATH 中）
- **Whisper**: `pip install openai-whisper`
- **edge-tts**: `pip install edge-tts`

## 快速开始

```powershell
python scripts/dub_video.py <英文视频路径> [options]
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `video` | (必填) | 输入英文视频文件路径 |
| `--output-dir` | 视频同目录 | 输出目录（含音频+最终视频） |
| `--whisper-model` | `tiny` | Whisper 模型大小: tiny/base/small/medium/large |
| `--tts-speed` | `+0%` | TTS 语速: `+10%` 加速, `-5%` 减速 |
| `--keep-temp` | 否 | 保留转写+配音过程中的临时文件 |

### 示例

```powershell
# 基本用法
python scripts/dub_video.py D:\videos\lesson.mp4

# 使用更准确的 Whisper small 模型
python scripts/dub_video.py D:\videos\lesson.mp4 --whisper-model small

# 指定输出目录 + 加速语速
python scripts/dub_video.py lesson.mp4 --output-dir ./output --tts-speed +10%
```

## 工作流程

脚本自动执行以下 6 步：

1. **提取音频** — 从视频中提取 16kHz 单声道 WAV
2. **Whisper 转写** — 英文语音转文字
3. **角色分析 + 中文翻译** — 基于关键词启发式分配角色（Girl/Boy/Mom/Dad/Rabbit/Narrator），并翻译为口语中文
4. **多角色 TTS 生成** — 为每个角色分配不同的 Edge TTS 音色（儿童声/女声/男声），并行生成
5. **时间对齐 + 音频拼接** — 自动调整每段音频长度匹配字幕时间轴
6. **合入视频** — 用新配音替换原音频，输出最终 MP4

## 角色音色映射

| 角色 | Edge TTS 音色 | 说明 |
|------|--------------|------|
| Girl | `zh-CN-XiaoyiNeural` (+10%) | 可爱女童声，活泼动画风格 |
| Boy | `zh-CN-YunxiNeural` (+5%) | 阳光男童声 |
| Mom | `zh-CN-XiaoxiaoNeural` | 温暖女声，亲切柔和 |
| Dad | `zh-CN-YunyangNeural` | 稳重男声，专业可靠 |
| Rabbit | `zh-CN-YunxiNeural` (-5%) | 阳光男声慢速，神秘沉稳 |
| Narrator | `zh-CN-XiaoxiaoNeural` | 温暖女声，适合旁白 |

> 如需自定义音色，编辑 `scripts/dub_video.py` 中的 `VOICE_MAP` 字典。
> 可用音色列表: `edge-tts --list-voices`

## 角色分配规则

脚本通过关键词匹配自动分配角色，规则见 `assign_speaker()` 函数：

- **Mom**: 包含 debts/banana/helped us/we can
- **Rabbit**: 包含 I'll give/in return/follow me/remember/take only/nothing more
- **Girl**: 包含 golden apple/wow/rich/mine/thank/carrot/secret/heavy 等
- 未匹配的默认为 Girl

如需更精准的角色分配，在 AI 辅助下编辑 `scripts/dub_video.py` 中的 `assign_speaker()` 函数或直接手动标注。

## 输出文件

```
输出目录/
├── dubbed_full.wav               # 完整配音音频（WAV）
├── <视频名>_dubbed.mp4            # 最终配音视频（MP4）
└── _temp/                         # 临时文件（如未指定 --keep-temp 则自动清理）
    ├── audio.wav                  # 提取的音频
    ├── transcript.json            # Whisper 转写结果
    ├── script.json                # 角色标注+翻译结果
    ├── mp3/                       # 各段 TTS 音频
    ├── wav/                       # 转换后的 WAV
    └── aligned/                   # 时间对齐后的片段
```
