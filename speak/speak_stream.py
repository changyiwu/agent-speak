# -*- coding: utf-8 -*-
"""edge-tts 串流播放：音訊邊生成邊播。

用法：
  echo 文字 | python speak_stream.py - [voice]
  python speak_stream.py "文字" [voice]
需要 mpv 或 ffplay 其中之一（管道播放器，皆無視窗）。
找不到播放器時以 exit code 3 結束，讓外層 speak.ps1 退回整檔模式。
送進 Edge-TTS 前先套讀音替換表（見 tts_lexicon.py）；找不到表就照原文念。
"""
import asyncio
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from tts_lexicon import speakable
except Exception:                                        # 副本缺檔或壞掉時照原文念
    def speakable(text):
        return text


async def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        text = sys.argv[1]
    else:
        text = sys.stdin.buffer.read().decode("utf-8")
    text = text.strip()
    if not text:
        sys.exit(2)
    text = speakable(text)
    voice = sys.argv[2] if len(sys.argv) > 2 else "zh-TW-HsiaoChenNeural"

    import edge_tts

    mpv = shutil.which("mpv")
    if mpv:
        cmd = [mpv, "--no-video", "--really-quiet", "--keep-open=no", "-"]
    else:
        ffplay = shutil.which("ffplay")
        if not ffplay:
            sys.exit(3)
        cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"]

    t0 = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    first = None
    playback_failed = False
    com = edge_tts.Communicate(text, voice)
    try:
        async for chunk in com.stream():
            if chunk["type"] != "audio":
                continue
            try:
                proc.stdin.write(chunk["data"])
                if first is None:
                    proc.stdin.flush()
                    first = time.perf_counter() - t0
                    print(f"first_audio_chunk_s={first:.1f}", flush=True)
            except (BrokenPipeError, OSError):
                playback_failed = True
                break
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            playback_failed = True
        try:
            return_code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.terminate()
            return_code = proc.wait(timeout=5)
            playback_failed = True

    if first is None or return_code != 0 or playback_failed:
        print("串流播放器未正常完成", file=sys.stderr)
        sys.exit(4)
    print(f"total_s={time.perf_counter() - t0:.1f}")


asyncio.run(main())
