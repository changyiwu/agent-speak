---
name: speak
description: 快速語音回覆技能。當使用者說「唸出來」「用語音回答」「用語音講結論」「唸給我聽」「語音摘要」，或以語音對話並希望得到語音回覆時，請一定要使用此技能。使用 Edge-TTS 生成台灣中文語音並在本機無視窗播放。只有使用者明確指定「用小吳（或其他已克隆人聲）的聲音」時，才在 voice-cloner 技能可用的情況下改用該技能；否則使用本技能。
---

# speak — 快速語音回覆

## 用途
把一段結論或摘要用自然的台灣中文語音唸出來，達成「使用者語音輸入 → Agent 語音回覆」的對話循環。

- 生成＋播放：**預設串流**（Edge-TTS 邊生成邊播；ffplay/mpv 管道播放，無視窗）
- 備援鏈：串流 → 整檔 → 作業系統內建語音；絕不 `Start-Process` 開播放器

| 層 | Windows | macOS |
|----|---------|-------|
| 1. 串流 | Edge-TTS ＋ ffplay/mpv | 相同 |
| 2. 整檔播放 | MediaPlayer → WMPlayer COM | `afplay`（系統內建） |
| 3. 離線備援 | SAPI | `say`（系統內建；嗓音優先序 Meijia → Sinji → Tingting） |
- 小吳或其他已克隆人聲**只在使用者明確指名且 `voice-cloner` 可用時**改走該技能；不可用時要先說明

## 環境需求

- **必須用 PowerShell 7（`pwsh`）執行，不可退回 Windows PowerShell 5.1（`powershell`）**：`speak.ps1` 是 UTF-8 無 BOM，5.1 會用系統 ANSI 編碼去解，中文字串變亂碼、引號被吃掉，整份腳本在 **parse 階段就失敗**（`Unexpected token ')'`、`The string is missing the terminator`），連 `-Check` 都跑不到。看到這類語法錯誤是用錯直譯器，不是腳本壞掉——先確認 `pwsh` 是否存在，沒有就請使用者安裝 PowerShell 7，不要改用 `powershell` 硬跑。
- **macOS**：先 `brew install --cask powershell`。第 2、3 層用的 `afplay` 與 `say` 都是系統內建，不必另外安裝。
- 串流模式另需 Python 3 ＋ `edge_tts` 模組 ＋ `ffplay` 或 `mpv`；整檔模式優先用同一個 Python 跑 `python -m edge_tts`，沒有該模組才改用 `edge-tts` 指令（pip 產生的 `edge-tts.exe` 沒有簽章，Windows 智慧型應用程式控制開啟時會被封鎖，所以不靠它）。兩條路都不通、或整檔模式中途出任何錯，都會退到作業系統內建語音（可離線但機器感重）。
- 換到新電腦第一次使用前，先跑一次不播放聲音的環境檢查：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "<本技能資料夾>/speak.ps1" -Check
```

輸出三個旗標 `STREAM_READY`／`FILE_READY`／`OFFLINE_READY` 與讀音替換表位置 `LEXICON`；只有 `OFFLINE_READY=True` 代表 Edge-TTS 兩條路都斷，要先補依賴再用。（`OFFLINE_READY` 在 Windows 量的是 SAPI、在 macOS 量的是 `say`。）

## 讀音替換表（多音字、英文詞）

Edge-TTS 不能用 SSML 指定讀音，念錯只能改字。串流與整檔兩層送進 Edge-TTS 前，會先套共用的讀音替換表 `tts-lexicon.md`（例：奇數 → 基數、十一少一 → 十一少了一、GPT-4 → GPT four）；講稿照正確用字寫，不必自己改字。第 3 層離線備援是別的引擎，照原文念。

找表順序（找到第一份就停；都找不到就照原文念，不報錯、不拖慢）：
1. 環境變數 `TTS_LEXICON`（有設就只用它）
2. 從本技能資料夾往上，每一層找 `ai-video-workflow/tts-lexicon.md`
3. 家目錄底下的雲端硬碟：`~/我的雲端硬碟`、`~/My Drive`、`~/Google Drive/(我的雲端硬碟|My Drive)`、macOS 的 `~/Library/CloudStorage/GoogleDrive-*/(我的雲端硬碟|My Drive)`，底下的 `agents/ai-video-workflow/tts-lexicon.md`

`-Check` 的 `LEXICON=` 一行會顯示用了哪份表（`none`＝沒找到）；設 `SPEAK_DEBUG=1` 時串流播放的結果也會帶出用了哪份表。雲端硬碟掛成磁碟代號（例如 Windows 串流模式的 `G:`）或放在其他位置時，設 `TTS_LEXICON` 指向它。要新增讀音請改主表，不要改本技能。

## 執行步驟

### 1. 撰寫講稿
- 口語化、精簡（100–250 字），數字用中文（「五十頁」不要「50頁」）；多音字、英文型號照正確用字寫，讀音替換表會處理
- 只講結論與下一步，細節留在文字回覆

### 2. 安全準備講稿檔

使用目前 Agent 的檔案寫入能力，把講稿寫成 UTF-8 暫存文字檔。不要把任意講稿直接插入 shell 命令字串，以免引號、反引號或 PowerShell 語法造成解析與安全問題。

### 3. 生成＋播放

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "<本技能資料夾>/speak.ps1" -File "<講稿暫存檔.txt>"
```
（`<本技能資料夾>`＝本 SKILL.md 所在目錄，即技能載入時顯示的 base directory）

若目前 Agent 的命令工具支援背景執行，就在背景播放並同步撰寫文字回覆；不支援時使用前景執行，不要傳入不存在的背景參數。完成後刪除剛建立的講稿暫存檔。輸出若有 `first_audio_chunk_s`／`total_s`，可在文字回覆中簡短回報。

若 Agent 沙箱找不到主機已安裝的 `pwsh`、Python、`edge-tts` 或播放器，取得使用者批准後改在主機使用者環境執行；不要因沙箱 PATH 或 WindowsApps 權限造成的假性缺少而重複安裝。

其他選項：
- 預設聲音 `zh-TW-HsiaoChenNeural`（小陳女聲）；其他台灣中文可選 `zh-TW-HsiaoYuNeural`（小玉女聲）或 `zh-TW-YunJheNeural`（雲哲男聲）
- 使用者說「存起來」→ 加 `-Out "<專案路徑>.mp3"`（走整檔模式並保留音檔）
- 串流不產生檔案；整檔備援的暫存音檔會在播放後自動刪除；需要保留時才用 `-Out`

### 4. 回報
一句話帶過即可（模式、首個音訊 chunk 延遲、音檔位置若有存）。不要重複唸稿內容。

## 注意
- 使用者句子含「小吳的聲音」「用○○的聲音」→ `voice-cloner` 可用時改用該技能；不可用時告知使用者
- Edge-TTS 需要網路；離線時自動退到作業系統內建語音（Windows SAPI／macOS `say`，機器感較重但可離線使用）
- 不要用 `Start-Process` 播放——會開外部程式視窗，使用者明確不要
