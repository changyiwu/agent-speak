"""speak_stream.py 的隔離測試；不連網、不啟動真實播放器。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import runpy
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "speak" / "speak_stream.py"


class FakeStdin:
    def __init__(self, fail_write: bool = False) -> None:
        self.fail_write = fail_write
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        if self.fail_write:
            raise BrokenPipeError
        self.data.extend(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class FakeProcess:
    def __init__(self, return_code: int = 0, fail_write: bool = False) -> None:
        self.stdin = FakeStdin(fail_write=fail_write)
        self.return_code = return_code

    def wait(self, timeout: int | None = None) -> int:
        return self.return_code

    def terminate(self) -> None:
        return None


def fake_edge_tts(chunks: list[dict[str, object]]) -> types.ModuleType:
    module = types.ModuleType("edge_tts")
    module.last_voice = None
    module.last_text = None

    class Communicate:
        def __init__(self, text: str, voice: str) -> None:
            self.text = text
            self.voice = voice
            module.last_voice = voice
            module.last_text = text

        async def stream(self):
            for chunk in chunks:
                yield chunk

    module.Communicate = Communicate
    return module


class SpeakStreamTests(unittest.TestCase):
    def run_stream(
        self,
        *,
        chunks: list[dict[str, object]],
        player_code: int = 0,
        fail_write: bool = False,
        player_present: bool = True,
        text: str = "測試文字",
        lexicon: str | None = None,
    ) -> tuple[int, str, str, str | None]:
        process = FakeProcess(return_code=player_code, fail_write=fail_write)
        edge_module = fake_edge_tts(chunks)
        stdout = io.StringIO()
        stderr = io.StringIO()

        def which(name: str) -> str | None:
            if player_present and name == "mpv":
                return "mock-mpv"
            return None

        # 讀音替換表一律指向測試給的檔（沒給就指向不存在的檔），不讀本機另外三份同內容的表
        spec = importlib.util.spec_from_file_location("tts_lexicon", SCRIPT.parent / "tts_lexicon.py")
        lexicon_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lexicon_module)
        lexicon_module.SIBLINGS = ()
        env = {"TTS_LEXICON": lexicon or os.path.join(tempfile.gettempdir(), "no-such-lexicon.md")}
        self.edge_module = edge_module
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.dict(sys.modules, {"edge_tts": edge_module, "tts_lexicon": lexicon_module}),
            mock.patch("shutil.which", side_effect=which),
            mock.patch("subprocess.Popen", return_value=process),
            mock.patch.object(sys, "argv", [str(SCRIPT), text]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as exc:
                return (
                    int(exc.code or 0),
                    stdout.getvalue(),
                    stderr.getvalue(),
                    edge_module.last_voice,
                )
        return 0, stdout.getvalue(), stderr.getvalue(), edge_module.last_voice

    def test_success_reports_metrics(self) -> None:
        code, stdout, _, voice = self.run_stream(
            chunks=[{"type": "audio", "data": b"audio"}]
        )
        self.assertEqual(code, 0)
        self.assertEqual(voice, "zh-TW-HsiaoChenNeural")
        self.assertIn("first_audio_chunk_s=", stdout)
        self.assertIn("total_s=", stdout)

    def test_lexicon_rewrites_text_sent_to_edge_tts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tts-lexicon.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "| 原文 | 改寫 | 說明 |\n|---|---|---|\n"
                    "| 奇數 | 基數 | |\n| GPT-4 | `GPT four` | |\n"
                )
            code, _, _, _ = self.run_stream(
                chunks=[{"type": "audio", "data": b"audio"}],
                text="奇數和 GPT-4",
                lexicon=path,
            )
        self.assertEqual(code, 0)
        self.assertEqual(self.edge_module.last_text, "基數和 GPT four")

    def test_missing_lexicon_keeps_text(self) -> None:
        code, _, _, _ = self.run_stream(
            chunks=[{"type": "audio", "data": b"audio"}], text="奇數和 GPT-4"
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.edge_module.last_text, "奇數和 GPT-4")

    def test_missing_player_returns_three(self) -> None:
        code, _, _, _ = self.run_stream(chunks=[], player_present=False)
        self.assertEqual(code, 3)

    def test_broken_pipe_returns_four(self) -> None:
        code, _, stderr, _ = self.run_stream(
            chunks=[{"type": "audio", "data": b"audio"}], fail_write=True
        )
        self.assertEqual(code, 4)
        self.assertIn("未正常完成", stderr)

    def test_nonzero_player_exit_returns_four(self) -> None:
        code, _, _, _ = self.run_stream(
            chunks=[{"type": "audio", "data": b"audio"}], player_code=1
        )
        self.assertEqual(code, 4)


if __name__ == "__main__":
    unittest.main()
