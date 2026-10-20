# agent-speak 🔊

讓你的 AI Agent「用語音回答你」——使用 Edge-TTS 的串流語音回覆技能。

Voice-reply skill for AI agents (Claude Code / Codex / OpenCode / Antigravity) — streams Edge-TTS audio through a local hidden player, with no separate Edge-TTS API key or window pop-ups.

## 特色

- ⚡ **串流播放**：音訊邊生成邊播，不必等整個音檔生完；延遲取決於網路與上游服務
- 🔑 **無獨立 API Key**：使用 `edge-tts` 連接 Microsoft Edge 的線上語音服務
- 🪟 **行內無視窗**：ffplay/mpv 管道播放，不會跳出任何播放器視窗
- 🛡️ **三層備援**：串流 → 整檔（WPF MediaPlayer／WMPlayer COM）→ 離線 Windows SAPI，斷網也出得了聲
- 🗣️ 預設台灣中文小陳女聲 `zh-TW-HsiaoChenNeural`，一個參數換任何 Edge-TTS 聲音
- 📖 **讀音替換表**：送進 Edge-TTS 前套技能自帶的 `tts-lexicon.md`（奇數 → 基數、GPT-4 → GPT four），同層其他 TTS repo 的同一份表也會一起讀；找不到表就照原文念
- 🤝 **四個 Agent 通用**：同一份技能資料夾，Claude Code、Codex、OpenCode、Antigravity 都能用

## 需求

| 項目 | 說明 |
|------|------|
| Windows 10/11 | 播放備援用到 WPF／SAPI（核心生成跨平台，播放層目前為 Windows） |
| PowerShell 7（pwsh） | `winget install Microsoft.PowerShell` |
| Python 3.8+ ＋ edge-tts | `pip install edge-tts`（串流與整檔都直接跑 Python 模組，不靠 `edge-tts.exe`） |
| ffmpeg（含 ffplay）或 mpv | 串流播放用；沒有也能動（自動退到整檔模式）。`winget install Gyan.FFmpeg` |

PowerShell 7 是啟動本 Skill 的必要條件；Windows SAPI 只負責執行後的離線語音備援，不能取代 `pwsh`。
命令使用單次行程的 `-ExecutionPolicy Bypass`，只略過這次 Skill 腳本的簽章限制，不修改使用者或系統的全域執行政策。
Codex 等 Agent 的沙箱可能看不到 WindowsApps 或使用者層 PATH；若主機檢查已安裝、沙箱仍顯示缺少，應在取得批准後改用主機使用者環境執行，而不是重複安裝。

安裝後可先做不播放聲音的環境檢查：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File ./speak/speak.ps1 -Check
```

## 安裝（可下載 ZIP，不一定要 git clone）

把 `speak/` 資料夾整個複製到你所用工具的技能目錄：

| Agent | 技能目錄 |
|-------|---------|
| Claude Code | `~/.claude/skills/speak/` |
| Codex | `~/.agents/skills/speak/` |
| Antigravity | `~/.gemini/config/skills/speak/` |
| OpenCode | `~/.config/opencode/skills/speak/` |

裝好後對你的 Agent 說：**「用語音回答我」**、「唸出來」、「唸給我聽」即可觸發。

## 手動使用

```powershell
# 建議：從 UTF-8 文字檔安全讀取講稿
pwsh -NoProfile -ExecutionPolicy Bypass -File ./speak/speak.ps1 -File ./講稿.txt

# 換聲音（任何 edge-tts 支援的 voice）
pwsh -NoProfile -ExecutionPolicy Bypass -File ./speak/speak.ps1 -File ./講稿.txt -Voice zh-TW-HsiaoYuNeural

# 保留音檔（走整檔模式）
pwsh -NoProfile -ExecutionPolicy Bypass -File ./speak/speak.ps1 -File ./講稿.txt -Out ./out/reply.mp3
```

`-Text "固定文字"` 仍可供人工測試；Agent 處理任意使用者內容時應使用 `-File`，避免 shell 字元被誤解析。

可用聲音清單：`edge-tts --list-voices`

## 讀音替換表

Edge-TTS 不能用 SSML 指定讀音，多音字與英文詞念錯只能改字。`speak/tts_lexicon.py` 在送進 Edge-TTS 前（串流與整檔兩層）套一份 Markdown 替換表：

```markdown
| 原文 | 改寫 | 說明 |
|---|---|---|
| 奇數 | 基數 | 奇讀 jī |
| GPT-4 | `GPT four` | 英文型號用英文念 |
```

只讀表頭是「原文｜改寫」的表格；內容有 `|` 寫成 `\|`，反引號包住的格子會去掉反引號（用來標出前後空白）；長的原文先換，一次掃完不重複替換。技能**自帶一份** `speak/tts-lexicon.md`，安裝時跟著複製，單獨使用就有完整條目。這份表在 [media-video-specs](https://github.com/changyiwu/media-video-specs)、[media-short-film](https://github.com/changyiwu/media-short-film)、[media-voice-clone](https://github.com/changyiwu/media-voice-clone) 也各有一份、內容相同；找得到就一起讀，同一個原文以自帶那份為準。離線備援（SAPI／`say`）是別的引擎，照原文念。

找表順序（遠的在前、近的覆蓋遠的；任何一份讀不到都跳過，全部找不到就照原文念）：

1. 另外三份：從技能資料夾往上，每一層找 `<repo>/tts-lexicon.md`（從 repo 執行時適用）；找不到再看家目錄底下的雲端硬碟：`~/我的雲端硬碟`、`~/My Drive`、`~/Google Drive/(我的雲端硬碟|My Drive)`、macOS 的 `~/Library/CloudStorage/GoogleDrive-*/(我的雲端硬碟|My Drive)`，底下的 `agents/<repo>/tts-lexicon.md`
2. 自帶的 `speak/tts-lexicon.md`（設了環境變數 `TTS_LEXICON` 就改讀它指的表）

技能平常從全域技能目錄執行，自帶那份一定讀得到；另外三份只是補充。確認用了哪幾份表：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File ./speak/speak.ps1 -Check   # 看 LEXICON= 一行
python ./speak/tts_lexicon.py "奇數加一，GPT-4"                           # 試替換結果
```

串流播放時設 `SPEAK_DEBUG=1` 也會在結果帶出用了哪份表。表每次執行只讀一次，載入約數毫秒，不影響首聲。

## 運作原理

```
文字講稿 ─→ edge-tts 線上服務 ─→ 音訊 chunk ─→ ffplay/mpv stdin（邊收邊播）
                    │ 失敗時
                    ├─→ 整檔 mp3 → WPF MediaPlayer／WMPlayer COM（無視窗）
                    │ 再失敗（離線）
                    └─→ Windows SAPI 本機合成（零依賴）
```

## 檔案

- `speak/SKILL.md` — 技能說明（Agent 讀這份決定何時觸發、怎麼呼叫）
- `speak/speak.ps1` — 主腳本（模式選擇＋備援鏈）
- `speak/speak_stream.py` — Edge-TTS 串流播放器
- `speak/tts_lexicon.py` — 讀音替換表載入與替換

## 注意

- `edge-tts` 使用 Microsoft Edge 的線上語音服務；上游介面、可用性與限流可能變動，必要時執行 `pip install -U edge-tts`
- 本專案不保證免費額度、無限用量或服務 SLA；使用前請確認上游服務條款
- 要商用等級 SLA 可評估 [Azure Speech](https://azure.microsoft.com/pricing/details/speech/)；免費層與價格以官方當期頁面為準

## 測試

測試不會連網或播放聲音：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File ./tests/test_speak.ps1
python -m unittest ./tests/test_speak_stream.py ./tests/test_tts_lexicon.py
```

## License

MIT © 2026 mathruffian-dot（Sense Bar）
