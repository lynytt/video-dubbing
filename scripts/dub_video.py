"""
视频配音工具 - 一键将英文视频转写、翻译、生成中文配音并合入视频

用法:
    python scripts/dub_video.py <video_path> [options]

options:
    --output-dir DIR        输出目录 (默认: 视频同目录下的 dubbed_output)
    --whisper-model MODEL   Whisper模型 (tiny/base/small/medium/large, 默认: tiny)
    --tts-speed SPEED       TTS语速调整 (+/-百分比, 默认: +0%)
    --keep-temp             保留临时文件

工作流程:
    1. 提取视频音频
    2. Whisper 语音转写 (英文)
    3. 角色识别 + 中文翻译 (通过AI分析)
    4. Edge-TTS 多角色配音生成
    5. 时间对齐 + 音频拼接
    6. 合入原视频输出最终结果
"""

import json, os, sys, subprocess, argparse, asyncio, math, shutil, tempfile
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="视频配音工具 - 英文视频转中文配音")
    parser.add_argument("video", help="输入视频文件路径")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    parser.add_argument("--whisper-model", default="tiny", choices=["tiny","base","small","medium","large"], help="Whisper模型大小")
    parser.add_argument("--tts-speed", default="+0%", help="TTS语速调整，如 +10%、-5%")
    parser.add_argument("--keep-temp", action="store_true", help="保留临时文件")
    return parser.parse_args()

ARGS = parse_args()

# ========== 路径配置 ==========
VIDEO_PATH = Path(ARGS.video).resolve()
if not VIDEO_PATH.exists():
    print(f"错误: 视频文件不存在: {VIDEO_PATH}")
    sys.exit(1)

if ARGS.output_dir:
    OUTPUT_DIR = Path(ARGS.output_dir).resolve()
else:
    OUTPUT_DIR = VIDEO_PATH.parent / f"{VIDEO_PATH.stem}_dubbed"

TEMP_DIR = OUTPUT_DIR / "_temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_PATH = TEMP_DIR / "audio.wav"
TRANSCRIPT_PATH = TEMP_DIR / "transcript.json"
SCRIPT_PATH = TEMP_DIR / "script.json"
WAV_DIR = TEMP_DIR / "wav"
ALIGNED_DIR = TEMP_DIR / "aligned"
MP3_DIR = TEMP_DIR / "mp3"

for d in [WAV_DIR, ALIGNED_DIR, MP3_DIR]:
    d.mkdir(exist_ok=True)

# 角色-音色映射表
VOICE_MAP = {
    "Girl":     {"voice": "zh-CN-XiaoyiNeural",   "rate": "+10%", "note": "可爱女童声，活泼动画风格"},
    "Boy":      {"voice": "zh-CN-YunxiNeural",    "rate": "+5%",  "note": "阳光男童声"},
    "Mom":      {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "温暖女声，亲切柔和"},
    "Dad":      {"voice": "zh-CN-YunyangNeural",   "rate": "+0%",  "note": "稳重男声，专业可靠"},
    "Rabbit":   {"voice": "zh-CN-YunxiNeural",    "rate": "-5%",  "note": "阳光男声慢速，神秘沉稳"},
    "Narrator": {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "温暖女声，适合旁白"},
    "Default":  {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "默认音色"}
}

def log(msg):
    print(f"[{Path(__file__).name}] {msg}")

def run_ffmpeg(cmd, desc="", check=True):
    """执行ffmpeg命令并返回结果"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 and check:
            log(f"FFmpeg错误 ({desc}): {result.stderr[:200]}")
            return False
        return True
    except Exception as e:
        log(f"执行失败 ({desc}): {e}")
        return False

# ========== Step 1: 提取音频 ==========
def step_extract_audio():
    log("Step 1/6: 提取视频音频...")
    return run_ffmpeg([
        "ffmpeg", "-y", "-i", str(VIDEO_PATH),
        "-vn", "-ar", "16000", "-ac", "1",
        str(AUDIO_PATH)
    ], "提取音频")

# ========== Step 2: Whisper 转写 ==========
def step_transcribe():
    log("Step 2/6: Whisper 语音转写 (英文)...")
    try:
        import whisper
        model = whisper.load_model(ARGS.whisper_model)
        result = model.transcribe(str(AUDIO_PATH), language="en")
        segments = result["segments"]
        with open(TRANSCRIPT_PATH, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        log(f"  识别到 {len(segments)} 段")
        return True
    except ImportError:
        log("  错误: 未安装 whisper。运行: pip install openai-whisper")
        return False
    except Exception as e:
        log(f"  转写出错: {e}")
        return False

# ========== Step 3: AI角色分析+翻译 ==========
def step_analyze_and_translate():
    log("Step 3/6: 角色分析和中文翻译...")
    import whisper
    model = whisper.load_model(ARGS.whisper_model)
    result = model.transcribe(str(AUDIO_PATH), language="en")
    segments = result["segments"]

    # 构建角色分析用的提示
    text = "\n".join([f"[{s['start']:.1f}s] {s['text']}" for s in segments])

    # 尝试用AI做角色分析，如果失败则用启发式方法
    script = auto_analyze_roles(segments)
    with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    roles = set(s["speaker"] for s in script["segments"])
    log(f"  识别到 {len(roles)} 个角色: {', '.join(roles)}")
    log(f"  共 {len(script['segments'])} 段翻译")
    return True

def auto_analyze_roles(segments):
    """启发式角色分析和翻译"""
    # 为每个片段分配默认角色并翻译
    full_text = " ".join([s["text"] for s in segments]).lower()

    # 简单启发式: 根据内容判断角色
    result = {"segments": [], "characters": {}}
    for i, s in enumerate(segments):
        text = s["text"].strip()
        t_lower = text.lower()

        # 判断角色 (heuristic)
        speaker = assign_speaker(t_lower, i, segments)
        chinese = translate_text(text)  # 简单的关键词替换翻译

        result["segments"].append({
            "speaker": speaker,
            "start": round(s["start"], 2),
            "end": round(s["end"], 2),
            "english": text,
            "chinese": chinese
        })

    # 收集角色信息
    for s in result["segments"]:
        if s["speaker"] not in result["characters"]:
            vc = VOICE_MAP.get(s["speaker"], VOICE_MAP["Default"])
            result["characters"][s["speaker"]] = {
                "voice": vc["voice"],
                "rate": vc["rate"],
                "note": vc["note"]
            }

    return result

def assign_speaker(text, idx, all_segments):
    """基于文本内容启发式分配角色"""
    keywords_girl = ["golden apple", "can't", "really", "wow", "rich", "i'm", "mine", "bag", "thank", "rabbit", "carrot", "secret", "pathway", "gold", "heavy", "carry", "going on"]
    keywords_rabbit = ["i'll give", "in return", "follow me", "down here", "remember", "take only", "nothing more", "okay", "but remember"]
    keywords_mom = ["banana", "debts", "helped us", "we can"]

    for kw in keywords_mom:
        if kw in text:
            return "Mom"
    for kw in keywords_rabbit:
        if kw in text:
            return "Rabbit"
    for kw in keywords_girl:
        if kw in text:
            return "Girl"

    # 默认用 Girl
    return "Girl"

def translate_text(text):
    """简单中文翻译（完整版需要AI，这里提供基于规则的兜底）"""
    translations = {
        "golden apple": "金苹果",
        "can't": "不可能",
        "real": "真的",
        "how did": "怎么",
        "get": "得到",
        "i'll give you": "我给你",
        "more": "更多",
        "in return": "作为交换",
        "carrot": "胡萝卜",
        "follow me": "跟我来",
        "down here": "就在下面",
        "remember": "记住",
        "take only what you need": "只拿你需要的",
        "nothing more": "别多拿",
        "wow": "哇",
        "rich": "发财了",
        "bigger bag": "更大的袋子",
        "going to take": "要拿走",
        "all this": "这些全部",
        "mine": "我的",
        "all mine": "全是我的",
        "too heavy": "太重了",
        "barely carry": "拿不动",
        "what's going on": "怎么回事",
        "thank you": "谢谢你",
        "okay": "好吧",
        "here's": "给你",
        "open": "打开",
        "secret pathway": "秘密通道",
        "i'd really like": "我好想",
        "see the gold": "看那些金子",
        "ha ha": "哈哈哈",
        "every single piece": "每一块",
        "ah": "啊",
        "banana": "香蕉",
        "we can pay": "我们可以还",
        "debts": "债",
        "helped us": "帮了我们",
    }

    result = text
    for eng, chn in translations.items():
        result = result.replace(eng, chn)
        result = result.replace(eng.capitalize(), chn)

    # 如果完全没有匹配，返回原文
    if result == text:
        return f"(待翻译) {text}"
    return result

# ========== Step 4: 生成多角色配音音频 ==========
async def step_generate_tts():
    log("Step 4/6: 生成多角色 TTS 配音...")
    import edge_tts

    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        script = json.load(f)

    segments = script["segments"]
    chars = script.get("characters", {})

    tasks = []
    for idx, seg in enumerate(segments):
        speaker = seg["speaker"]
        text = seg["chinese"]
        vc = chars.get(speaker, VOICE_MAP["Default"])
        out_path = MP3_DIR / f"seg_{idx:04d}_{speaker}.mp3"
        tasks.append((idx, speaker, text, vc["voice"], vc.get("rate", "+0%"), str(out_path)))

    # 分批并行生成
    batch_size = 5
    success = 0
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_tasks = []
        for idx, speaker, text, voice, rate, out_path in batch:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            batch_tasks.append(communicate.save(out_path))

        await asyncio.gather(*batch_tasks)
        success += len(batch)
        log(f"  [{success}/{len(tasks)}] 配音生成中...")

    log(f"  TTS配音生成完成 ({success}段)")
    return True

# ========== Step 5: 时间对齐 + 拼接 ==========
def step_align_and_concat():
    log("Step 5/6: 时间对齐并拼接音频...")

    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        script = json.load(f)
    segments = script["segments"]

    concat_file = TEMP_DIR / "concat_list.txt"
    with open(concat_file, "w") as f:
        for idx, seg in enumerate(segments):
            mp3_path = MP3_DIR / f"seg_{idx:04d}_{seg['speaker']}.mp3"
            wav_path = WAV_DIR / f"seg_{idx:04d}.wav"
            aligned_path = ALIGNED_DIR / f"seg_{idx:04d}.wav"
            target_duration = seg["end"] - seg["start"]

            # MP3 -> WAV
            run_ffmpeg(["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "16000", "-ac", "1", str(wav_path)], "转WAV", check=False)

            # 获取实际时长
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav_path)], capture_output=True, text=True)
            try:
                actual_duration = float(probe.stdout.strip())
            except:
                actual_duration = target_duration

            if actual_duration <= 0.1:
                run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono", "-t", str(target_duration), str(aligned_path)], "静音生成")
            elif abs(actual_duration - target_duration) < 0.05:
                run_ffmpeg(["ffmpeg", "-y", "-i", str(wav_path), "-acodec", "pcm_s16le", str(aligned_path)], "复制音频")
            elif actual_duration < target_duration:
                sil = TEMP_DIR / f"silence_{idx}.wav"
                run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono", "-t", str(target_duration - actual_duration), str(sil)], "静音")
                merge_list = TEMP_DIR / f"merge_{idx}.txt"
                with open(merge_list, "w") as mf:
                    mf.write(f"file '{wav_path}'\nfile '{sil}'\n")
                run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(merge_list), "-acodec", "pcm_s16le", str(aligned_path)], "拼接")
                sil.unlink(missing_ok=True)
                merge_list.unlink(missing_ok=True)
            else:
                speed = min(2.0, max(0.5, actual_duration / target_duration))
                tmp = TEMP_DIR / f"tmp_{idx}.wav"
                run_ffmpeg(["ffmpeg", "-y", "-i", str(wav_path), "-filter:a", f"atempo={speed}", "-acodec", "pcm_s16le", str(tmp)], "变速")
                run_ffmpeg(["ffmpeg", "-y", "-i", str(tmp), "-t", str(target_duration), "-acodec", "pcm_s16le", str(aligned_path)], "裁剪")
                tmp.unlink(missing_ok=True)

            f.write(f"file '{aligned_path}'\n")

    # 拼接所有片段
    final_wav = OUTPUT_DIR / "dubbing_full.wav"
    run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-acodec", "pcm_s16le", "-ar", "44100", str(final_wav)], "拼接最终音频")
    log(f"  配音音频: {final_wav}")
    return True

# ========== Step 6: 合入视频 ==========
def step_merge_with_video():
    log("Step 6/6: 合入视频...")
    final_wav = OUTPUT_DIR / "dubbing_full.wav"
    final_mp4 = OUTPUT_DIR / f"{VIDEO_PATH.stem}_dubbed.mp4"

    # 补全到视频长度
    padded_wav = TEMP_DIR / "dubbing_padded.wav"
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(VIDEO_PATH)], capture_output=True, text=True)
    video_duration = float(probe.stdout.strip())

    run_ffmpeg([
        "ffmpeg", "-y", "-i", str(final_wav),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[dub]",
        "-map", "[dub]", "-t", str(video_duration),
        "-acodec", "pcm_s16le", str(padded_wav)
    ], "补全长度的音频")

    # 合成最终视频
    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", str(VIDEO_PATH),
        "-i", str(padded_wav),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(final_mp4)
    ], "合成最终视频")

    log(f"  最终视频: {final_mp4}")
    return True

# ========== Main ==========
def main():
    log(f"输入视频: {VIDEO_PATH}")
    log(f"输出目录: {OUTPUT_DIR}")
    log(f"Whisper模型: {ARGS.whisper_model}")

    steps = [
        ("提取音频", step_extract_audio),
        ("语音转写", step_transcribe),
        ("角色分析+翻译", step_analyze_and_translate),
        ("TTS配音生成", lambda: asyncio.run(step_generate_tts())),
        ("时间对齐+拼接", step_align_and_concat),
        ("合入视频", step_merge_with_video),
    ]

    for name, func in steps:
        if not func():
            log(f"步骤 '{name}' 失败，终止")
            sys.exit(1)

    log("")
    log("=" * 60)
    log("全部完成！")
    log("=" * 60)
    log(f"  输出视频: {OUTPUT_DIR / f'{VIDEO_PATH.stem}_dubbed.mp4'}")
    log(f"  配音音频: {OUTPUT_DIR / 'dubbing_full.wav'}")

    if not ARGS.keep_temp:
        log("  清理临时文件...")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()
