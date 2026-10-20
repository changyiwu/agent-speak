"""tts_lexicon.py 的隔離測試；只用暫存資料夾，不讀本機真正的主表。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "speak"))
import tts_lexicon  # noqa: E402

TABLE = r"""# 讀音替換表

說明文字裡的表格不算：

| 欄位 | 意思 |
|---|---|
| 奇數 | 不該被讀進來 |

## 替換表

| 原文 | 改寫 | 說明 |
|:---|---:|---|
| 奇數 | 基數 | 奇讀 jī |
| 十一少一 | 十一少了一 | 少讀 shǎo |
| GPT-4 | `GPT four` | 反引號標出空白 |
| A\|B | A or B | 跳脫的直線 |
| 少一 | 少壹 | 比十一少一短，不該先換 |
| 基數 | 不該再換 | 換過的結果不會再被換 |
| 壞掉的列 | | 改寫空白，跳過 |

結尾段落
"""


def write(path: Path, text: str = TABLE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class LexiconTests(unittest.TestCase):
    def setUp(self) -> None:
        tts_lexicon._cache = None
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if k != "TTS_LEXICON"}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_parse_reads_only_lexicon_table(self) -> None:
        table = tts_lexicon.parse(write(self.root / "t.md"))
        self.assertEqual(table["奇數"], "基數")
        self.assertEqual(table["GPT-4"], "GPT four")
        self.assertEqual(table["A|B"], "A or B")
        self.assertNotIn("壞掉的列", table)
        self.assertEqual(len(table), 6)

    def test_speakable_longest_first_single_pass(self) -> None:
        table = tts_lexicon.parse(write(self.root / "t.md"))
        out = tts_lexicon.speakable("奇數，十比十一少一，GPT-4，A|B", table)
        self.assertEqual(out, "基數，十比十一少了一，GPT four，A or B")

    def test_env_var_wins(self) -> None:
        env_table = write(self.root / "elsewhere" / "x.md")
        skill = self.root / "agents" / "speak-skill" / "speak"
        write(self.root / "agents" / "ai-video-workflow" / "tts-lexicon.md")
        with mock.patch.dict(os.environ, {"TTS_LEXICON": str(env_table)}):
            self.assertEqual(tts_lexicon.find(skill, self.root / "home"), str(env_table))

    def test_env_var_pointing_nowhere_means_no_table(self) -> None:
        skill = self.root / "agents" / "speak-skill" / "speak"
        write(self.root / "agents" / "ai-video-workflow" / "tts-lexicon.md")
        with mock.patch.dict(os.environ, {"TTS_LEXICON": str(self.root / "missing.md")}):
            self.assertIsNone(tts_lexicon.find(skill, self.root / "home"))

    def test_walks_up_from_skill_dir(self) -> None:
        master = write(self.root / "agents" / "ai-video-workflow" / "tts-lexicon.md")
        skill = self.root / "agents" / "agent-speak-skill" / "speak"
        skill.mkdir(parents=True)
        self.assertEqual(tts_lexicon.find(skill, self.root / "home"), str(master))

    def test_google_drive_default_under_home(self) -> None:
        home = self.root / "home"
        skill = home / ".claude" / "skills" / "speak"
        master = write(home / "我的雲端硬碟" / "agents" / "ai-video-workflow" / "tts-lexicon.md")
        self.assertEqual(tts_lexicon.find(skill, home), str(master))

    def test_macos_cloudstorage_default(self) -> None:
        home = self.root / "home"
        skill = home / ".claude" / "skills" / "speak"
        master = write(
            home / "Library" / "CloudStorage" / "GoogleDrive-someone@example.com"
            / "My Drive" / "agents" / "ai-video-workflow" / "tts-lexicon.md"
        )
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertEqual(tts_lexicon.find(skill, home), str(master))

    def test_not_found_keeps_text(self) -> None:
        home = self.root / "home"
        path, table = tts_lexicon.load(home / ".claude" / "skills" / "speak", home)
        self.assertIsNone(path)
        self.assertEqual(table, {})
        self.assertEqual(tts_lexicon.speakable("奇數", table), "奇數")

    def test_unreadable_table_is_ignored(self) -> None:
        bad = self.root / "bad.md"
        bad.write_bytes(b"\xff\xfe\x00broken")
        with mock.patch.dict(os.environ, {"TTS_LEXICON": str(bad)}):
            path, table = tts_lexicon.load()
        self.assertIsNone(path)
        self.assertEqual(table, {})


if __name__ == "__main__":
    unittest.main()
