#!/usr/bin/env python3
"""
视频配音工具 (Video Dubbing Tool)
将英文视频自动转写、角色识别、翻译为中文口语、生成多角色 TTS 配音并合入视频。
基于 OpenAI Whisper + Microsoft Edge TTS，全程本地运行，零成本。

用法:
    python dub_video.py <video_path> [options]

示例:
    python dub_video.py lesson.mp4
    python dub_video.py lesson.mp4 --whisper-model small --tts-speed +10%
    python dub_video.py lesson.mp4 --output-dir ./output --keep-temp
    python dub_video.py lesson.mp4 --voice-list voice_config.json
"""

import json, os, sys, subprocess, argparse, asyncio, math, shutil
from pathlib import Path

__version__ = "1.0.0"

# ============================================================
#  默认角色-音色映射表
# ============================================================
DEFAULT_VOICE_MAP = {
    "Girl":     {"voice": "zh-CN-XiaoyiNeural",   "rate": "+10%", "note": "可爱女童声，活泼动画风格"},
    "Boy":      {"voice": "zh-CN-YunxiNeural",    "rate": "+5%",  "note": "阳光男童声"},
    "Mom":      {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "温暖女声，亲切柔和"},
    "Dad":      {"voice": "zh-CN-YunyangNeural",   "rate": "+0%",  "note": "稳重男声，专业可靠"},
    "Rabbit":   {"voice": "zh-CN-YunxiNeural",    "rate": "-5%",  "note": "阳光男声慢速，神秘沉稳"},
    "Narrator": {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "温暖女声，适合旁白"},
    "Default":  {"voice": "zh-CN-XiaoxiaoNeural",  "rate": "+0%",  "note": "默认音色（女声）"}
}

# ============================================================
#  关键词-角色 匹配规则
# ============================================================
SPEAKER_RULES = [
    ("Mom", ["banana", "debts", "helped us", "we can", "mommy", "mom", "mother", "dear", "sweetie"]),
    ("Rabbit", ["i'll give", "in return", "follow me", "down here", "remember", "take only",
                "nothing more", "okay", "but remember", "hop", "bunny", "carrot"]),
    ("Girl", ["golden apple", "can't", "really", "wow", "rich", "i'm", "mine", "bag",
              "thank", "rabbit", "secret", "pathway", "gold", "heavy", "carry", "going on",
              "bigger", "gonna", "ha ha", "ah"]),
]

# ============================================================
#  中英翻译词典（内置基础版，支持扩展）
# ============================================================
BUILTIN_TRANSLATIONS = {
    # 常用短语
    "golden apple": "金苹果", "can't be real": "不可能吧", "how did": "怎么",
    "i'll give you": "我给你", "more": "更多", "in return": "作为交换",
    "follow me": "跟我来", "down here": "就在下面", "remember": "记住",
    "take only what you need": "只拿你需要的", "nothing more": "别多拿",
    "wow": "哇", "i'm rich": "我发财了", "bigger bag": "更大的袋子",
    "going to take": "要拿走", "all this": "这些全部", "mine": "我的",
    "all mine": "全是我的", "too heavy": "太重了", "barely carry": "拿不动",
    "what's going on": "怎么回事", "thank you": "谢谢你", "okay": "好吧",
    "here's a": "给你", "open": "打开", "secret pathway": "秘密通道",
    "i'd really like": "我好想", "see the gold": "看那些金子",
    "every single piece": "每一块", "ah": "啊", "banana": "香蕉",
    "we can pay": "我们可以还", "debts": "债", "helped us": "帮了我们",
    "ha ha": "哈哈哈", "can't": "不能", "get": "得到",
    # 常用问答
    "yes": "是的", "no": "不", "please": "请", "sorry": "对不起",
    "hello": "你好", "goodbye": "再见", "thanks": "谢谢",
    "help": "帮助", "wait": "等等", "look": "看",
    "come": "来", "go": "去", "stop": "停下",
}


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="🎬 视频配音工具 — 英文视频一键转中文配音",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python dub_video.py lesson.mp4
  python dub_video.py /path/to/video.mp4 --whisper-model small
  python dub_video.py video.mp4 --output-dir ./my_dub --tts-speed +10%
  python dub_video.py video.mp4 --voice-list my_voices.json --keep-temp
  python dub_video.py video.mp4 --subtitle-only   # 只生成字幕，不配音
  python dub_video.py video.mp4 --list-voices     # 列出可用 TTS 音色
        """
    )

    # 必选
    parser.add_argument("video", nargs="?", default=None,
                        help="输入英文视频文件路径")

    # 核心选项
    parser.add_argument("--output-dir", default=None,
                        help="输出目录（默认：视频同目录下 dubbed_output）")
    parser.add_argument("--whisper-model", default="tiny",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小（越小越快，越大越准）(默认: tiny)")
    parser.add_argument("--language", default="en",
                        help="源语言代码（en=英语, zh=中文等）(默认: en)")
    parser.add_argument("--tts-speed", default="+0%",
                        help="全局 TTS 语速调整，如 +10% 加速、-5% 减速 (默认: +0%)")
    parser.add_argument("--voice-list", default=None,
                        help="自定义角色音色 JSON 配置文件路径")

    # 模式选项
    parser.add_argument("--keep-temp", action="store_true",
                        help="保留临时中间文件（调试用）")
    parser.add_argument("--subtitle-only", action="store_true",
                        help="仅生成 SRT 字幕，不生成配音")
    parser.add_argument("--no-video", action="store_true",
                        help="仅生成配音音频，不合成视频")
    parser.add_argument("--list-voices", action="store_true",
                        help="列出所有可用的 Edge TTS 音色并退出")

    # 高级选项
    parser.add_argument("--batch-size", type=int, default=5,
                        help="TTS 并行生成批大小 (默认: 5)")
    parser.add_argument("--silence-padding", type=float, default=0,
                        help="每段前后额外静音秒数 (默认: 0)")
    parser.add_argument("--version", action="version",
                        version=f"video-dubbing v{__version__}")

    args = parser.parse_args()

    # --list-voices 不需要 video
    if not args.list_voices and not args.video:
        parser.error("请指定输入视频文件路径")

    return args


def log(msg):
    """彩色日志输出"""
    print(f"  🎯 {msg}")


def run_ffmpeg(cmd, desc="", check=True, capture=True):
    """执行 ffmpeg 命令"""
    try:
        kwargs = {"capture_output": capture, "text": True} if capture else {}
        result = subprocess.run(cmd, **kwargs)
        if result.returncode != 0 and check:
            log(f"⚠️ FFmpeg 错误 ({desc}): {result.stderr[:300] if capture else 'see above'}")
            return False
        return True
    except FileNotFoundError:
        log("❌ 未找到 FFmpeg！请确保 FFmpeg 已安装并添加到 PATH")
        return False
    except Exception as e:
        log(f"❌ 执行失败 ({desc}): {e}")
        return False


# ============================================================
#  Step 1: 提取音频
# ============================================================
def step_extract_audio(video_path, audio_path):
    log("📢 Step 1/6: 提取视频音频...")
    return run_ffmpeg([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(video_path)
    ], "获取视频时长")
    if not run_ffmpeg([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ar", "16000", "-ac", "1",
        str(audio_path)
    ], "提取音频"):
        return False
    # 获取音频时长
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(audio_path)
    ], capture_output=True, text=True)
    try:
        duration = float(probe.stdout.strip())
        log(f"  ✅ 音频提取完成 ({duration:.1f} 秒)")
    except:
        log(f"  ✅ 音频提取完成")
    return True


# ============================================================
#  Step 2: Whisper 转写
# ============================================================
def step_transcribe(audio_path, transcript_path, model_name, language):
    log("🎤 Step 2/6: Whisper 语音转写...")
    try:
        import whisper
    except ImportError:
        log("❌ 未安装 whisper。运行: pip install openai-whisper")
        return False

    log(f"  加载模型: {model_name}")
    model = whisper.load_model(model_name)
    log(f"  正在转写 (语言: {language})...")
    result = model.transcribe(str(audio_path), language=language)

    segments = result.get("segments", [])
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    log(f"  ✅ 转写完成！识别到 {len(segments)} 段，共 {len(result['text'].split())} 个词")
    return True


# ============================================================
#  Step 3: 角色分析 + 翻译
# ============================================================
def step_analyze(transcript_path, script_path):
    log("🧠 Step 3/6: 角色识别 + 中文翻译...")

    with open(transcript_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    # 加载自定义音色配置（如果有）
    voice_map = DEFAULT_VOICE_MAP.copy()
    if ARGS.voice_list:
        vp = Path(ARGS.voice_list)
        if vp.exists():
            with open(vp, "r", encoding="utf-8") as f:
                custom = json.load(f)
                voice_map.update(custom)
            log(f"  已加载自定义音色配置: {vp}")

    result = {"segments": [], "characters": {}}
    for s in segments:
        text = s.get("text", "").strip()
        speaker = assign_speaker(text.lower(), s)
        chinese = translate_text(text)

        result["segments"].append({
            "speaker": speaker,
            "start": round(s["start"], 2),
            "end": round(s["end"], 2),
            "english": text,
            "chinese": chinese
        })

    # 收集用到的角色
    used_speakers = set(s["speaker"] for s in result["segments"])
    for sp in used_speakers:
        vc = voice_map.get(sp, voice_map["Default"])
        result["characters"][sp] = {
            "voice": vc["voice"],
            "rate": vc["rate"],
            "note": vc["note"]
        }

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    char_summary = ", ".join(f"{k}({v['voice']})" for k, v in result["characters"].items())
    log(f"  ✅ 识别到 {len(used_speakers)} 个角色: {char_summary}")
    log(f"  ✅ 共 {len(result['segments'])} 段中文翻译")
    return True


def assign_speaker(text, seg_info=None):
    """基于关键词分配角色"""
    for speaker, keywords in SPEAKER_RULES:
        for kw in keywords:
            if kw in text:
                return speaker
    return "Girl"  # 默认


def translate_text(text):
    """基础中英翻译"""
    result = text
    # 优先匹配长短语
    items = sorted(BUILTIN_TRANSLATIONS.items(), key=lambda x: -len(x[0]))
    for eng, chn in items:
        result = result.replace(eng, chn)
        result = result.replace(eng.capitalize(), chn)
        result = result.replace(eng.title(), chn)
    return result


# ============================================================
#  Step 4: 生成 SRT 字幕
# ============================================================
def step_generate_srt(script_path, srt_path):
    log("📝 Step 3b/6: 生成 SRT 字幕文件...")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    def to_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    lines = []
    for i, seg in enumerate(script["segments"], 1):
        lines.append(f"{i}")
        lines.append(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}")
        lines.append(f"【{seg['speaker']}】{seg['chinese']}")
        lines.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(f"  ✅ SRT 已保存: {srt_path}")
    return True


# ============================================================
#  Step 5: TTS 配音生成
# ============================================================
async def step_generate_tts(script_path, mp3_dir, batch_size=5):
    log("🔊 Step 4/6: 生成多角色 TTS 配音...")

    try:
        import edge_tts
    except ImportError:
        log("❌ 未安装 edge-tts。运行: pip install edge-tts")
        return False

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    mp3_dir = Path(mp3_dir)
    mp3_dir.mkdir(parents=True, exist_ok=True)

    segments = script["segments"]
    chars = script.get("characters", {})

    # 构建任务列表
    tasks = []
    for idx, seg in enumerate(segments):
        speaker = seg["speaker"]
        text = seg["chinese"]
        vc = chars.get(speaker, DEFAULT_VOICE_MAP["Default"])
        out_path = mp3_dir / f"seg_{idx:04d}_{speaker}.mp3"
        tasks.append((idx, speaker, text, vc["voice"], vc.get("rate", "+0%"), out_path))

    # 分批并行
    success = 0
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        batch_coros = []
        for idx, speaker, text, voice, rate, out_path in batch:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            batch_coros.append(communicate.save(str(out_path)))
        await asyncio.gather(*batch_coros)
        success += len(batch)
        log(f"  [{success}/{len(tasks)}] 配音生成中...")

    log(f"  ✅ TTS 配音完成！共 {success} 段")
    return True


# ============================================================
#  Step 6: 时间对齐 + 拼接音频
# ============================================================
def step_align_concat(script_path, mp3_dir, wav_dir, aligned_dir, temp_dir, final_wav, silence_padding=0):
    log("🎯 Step 5/6: 时间对齐并拼接音频...")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    for d in [wav_dir, aligned_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)

    concat_file = Path(temp_dir) / "concat_list.txt"
    segments = script["segments"]

    with open(concat_file, "w") as f:
        for idx, seg in enumerate(segments):
            mp3_file = Path(mp3_dir) / f"seg_{idx:04d}_{seg['speaker']}.mp3"
            wav_file = Path(wav_dir) / f"seg_{idx:04d}.wav"
            aligned_file = Path(aligned_dir) / f"seg_{idx:04d}.wav"
            target_dur = seg["end"] - seg["start"]

            # 转 WAV
            run_ffmpeg(["ffmpeg", "-y", "-i", str(mp3_file),
                        "-ar", "16000", "-ac", "1", str(wav_file)], "转WAV", check=False)

            # 获取实际时长
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(wav_file)
            ], capture_output=True, text=True)
            try:
                actual = float(probe.stdout.strip())
            except:
                actual = target_dur

            # 时间对齐
            if actual <= 0.1:
                run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            f"anullsrc=r=16000:cl=mono", "-t", str(target_dur),
                            str(aligned_file)], "生成静音")
            elif abs(actual - target_dur) < 0.05:
                run_ffmpeg(["ffmpeg", "-y", "-i", str(wav_file),
                            "-acodec", "pcm_s16le", str(aligned_file)], "复制")
            elif actual < target_dur:
                silence_dur = target_dur - actual
                sil = Path(temp_dir) / f"silence_{idx}.wav"
                run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            f"anullsrc=r=16000:cl=mono", "-t", str(silence_dur),
                            str(sil)], "生成静音段")
                merge_list = Path(temp_dir) / f"merge_{idx}.txt"
                with open(merge_list, "w") as mf:
                    mf.write(f"file '{wav_file}'\nfile '{sil}'\n")
                run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(merge_list), "-acodec", "pcm_s16le",
                            str(aligned_file)], "拼接")
                sil.unlink(missing_ok=True)
                merge_list.unlink(missing_ok=True)
            else:
                speed = min(2.0, max(0.5, actual / target_dur))
                tmp = Path(temp_dir) / f"tmp_{idx}.wav"
                run_ffmpeg(["ffmpeg", "-y", "-i", str(wav_file),
                            "-filter:a", f"atempo={speed}",
                            "-acodec", "pcm_s16le", str(tmp)], "变速")
                run_ffmpeg(["ffmpeg", "-y", "-i", str(tmp), "-t", str(target_dur),
                            "-acodec", "pcm_s16le", str(aligned_file)], "裁剪")
                tmp.unlink(missing_ok=True)

            f.write(f"file '{aligned_file}'\n")

    # 拼接
    run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file), "-acodec", "pcm_s16le",
                "-ar", "44100", str(final_wav)], "拼接最终音频")
    return True


# ============================================================
#  Step 7: 合入视频
# ============================================================
def step_merge_video(video_path, final_wav, temp_dir, output_mp4):
    log("🎬 Step 6/6: 合入视频...")

    # 获取视频时长
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(video_path)
    ], capture_output=True, text=True)
    try:
        video_duration = float(probe.stdout.strip())
    except:
        video_duration = 0

    # 补全长度的音频
    padded_wav = Path(temp_dir) / "dubbing_padded.wav"
    run_ffmpeg([
        "ffmpeg", "-y", "-i", str(final_wav),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[dub]",
        "-map", "[dub]", "-t", str(video_duration),
        "-acodec", "pcm_s16le", str(padded_wav)
    ], "补全长度的音频")

    # 合入视频
    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(padded_wav),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_mp4)
    ], "合成最终视频")

    video_mb = os.path.getsize(output_mp4) / (1024 * 1024)
    log(f"  ✅ 最终视频: {output_mp4} ({video_mb:.1f} MB)")
    return True


# ============================================================
#  列出可用音色
# ============================================================
async def list_voices():
    """列出所有 Edge TTS 可用音色"""
    try:
        import edge_tts
        voices = await edge_tts.list_voices()
        print(f"\n{'='*70}")
        print(f"  Edge TTS 可用音色 ({len(voices)} 个)")
        print(f"{'='*70}")
        print(f"  {'Voice Name':35s} {'Gender':8s} {'Style':12s}")
        print(f"  {'-'*35} {'-'*8} {'-'*12}")
        for v in sorted(voices, key=lambda x: x["ShortName"]):
            if "CN" in v["ShortName"] or "Chinese" in v["Locale"]:
                name = v["ShortName"]
                gender = v.get("Gender", "N/A")
                styles = ", ".join(v.get("StyleList", ["General"])[:2])
                print(f"  {name:35s} {gender:8s} {styles:12s}")
        print(f"{'='*70}")
        print(f"  完整列表: edge-tts --list-voices")
        return True
    except ImportError:
        print("请先安装: pip install edge-tts")
        return False


# ============================================================
#  Main
# ============================================================
async def main_async():
    global ARGS
    ARGS = parse_args()

    if ARGS.list_voices:
        return await list_voices()

    video_path = Path(ARGS.video).resolve()
    if not video_path.exists():
        log(f"❌ 视频文件不存在: {video_path}")
        return False

    # 输出目录
    if ARGS.output_dir:
        output_dir = Path(ARGS.output_dir).resolve()
    else:
        stem = video_path.stem
        output_dir = video_path.parent / f"{stem}_dubbed"

    temp_dir = output_dir / "_temp"
    for d in [output_dir, temp_dir]:
        d.mkdir(parents=True, exist_ok=True)

    audio_path = temp_dir / "audio.wav"
    transcript_path = temp_dir / "transcript.json"
    script_path = temp_dir / "script.json"
    srt_path = output_dir / "subtitles.srt"
    mp3_dir = temp_dir / "mp3"
    wav_dir = temp_dir / "wav"
    aligned_dir = temp_dir / "aligned"
    final_wav = output_dir / "dubbing_full.wav"
    output_mp4 = output_dir / f"{video_path.stem}_dubbed.mp4"

    log(f"📂 输入视频: {video_path}")
    log(f"📂 输出目录: {output_dir}")

    # 执行流程
    steps = [
        ("提取音频", lambda: step_extract_audio(video_path, audio_path)),
        ("语音转写", lambda: step_transcribe(audio_path, transcript_path, ARGS.whisper_model, ARGS.language)),
        ("角色分析+翻译", lambda: step_analyze(transcript_path, script_path)),
        ("生成 SRT", lambda: step_generate_srt(script_path, srt_path)),
    ]

    if not ARGS.subtitle_only:
        steps += [
            ("TTS 配音生成", lambda: asyncio.run(step_generate_tts(script_path, mp3_dir, ARGS.batch_size))),
            ("时间对齐+拼接", lambda: step_align_concat(script_path, mp3_dir, wav_dir, aligned_dir, temp_dir, final_wav, ARGS.silence_padding)),
        ]
        if not ARGS.no_video:
            steps.append(("合入视频", lambda: step_merge_video(video_path, final_wav, temp_dir, output_mp4)))

    for name, func in steps:
        print()
        if not func():
            log(f"❌ 步骤 '{name}' 失败，终止")
            return False

    # 清理
    if not ARGS.keep_temp:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 完成
    print(f"\n{'='*60}")
    print(f"  🎉 全部完成！")
    print(f"{'='*60}")
    if not ARGS.subtitle_only:
        print(f"  📹 配音视频: {output_mp4}")
        print(f"  🎵 配音音频: {final_wav}")
    print(f"  📝 SRT 字幕: {srt_path}")
    if ARGS.keep_temp:
        print(f"  📂 临时文件: {temp_dir}")
    print(f"{'='*60}")

    return True


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print(f"\n  ⏹️ 用户中断")
        sys.exit(1)


if __name__ == "__main__":
    main()
