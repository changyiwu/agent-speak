# agent-speak-skill（專案藍圖）

> 本檔為跨 Agent 通用的專案藍圖（AGENTS.md 開放標準）。任何 Agent 的每個 session 都應先讀本檔＋`handoff.md`。
> Claude Code 預設只在沒有 `CLAUDE.md` 時才讀 `AGENTS.md`，故由 `CLAUDE.md` 的 `@AGENTS.md` import 本檔（`CLAUDE.md` 只有這一行）；Claude 專屬規範寫在本檔〈Claude Code 專屬〉一節。

## 專案簡介

建立可供 Claude Code、Codex、OpenCode、Antigravity 共用的 Windows 台灣中文語音回覆 Skill，以 Edge-TTS 串流播放為主，並提供整檔播放與 Windows SAPI 備援。

## 關鍵時程

目前沒有固定時程。

## 目標與路線圖

- [x] 階段一：完成安全傳參、跨 Agent 相容性、錯誤處理與暫存檔修正
- [x] 階段二：通過 Skill validator、語法解析與隔離式失敗情境測試
- [x] 階段三：完成 GitHub 與 Obsidian 初始化
- [x] 階段四：同步到四個 Agent 全域技能目錄，並完成逐檔 SHA-256、額外檔案與 UTF-8 BOM 驗證
- [x] 階段五：在 `SKILL.md` 明訂 PowerShell 7 為硬需求，並補齊當前電腦的本機語音依賴
- [ ] 階段六：其餘電腦補齊語音依賴並跑 `-Check`，再各自跑 `sync-skills` 取得新版 `SKILL.md`

## 資料夾結構

```text
agent-speak-skill/
├── speak/                 # 可安裝的 Skill 來源目錄
│   ├── agents/            # Codex UI metadata
│   ├── SKILL.md           # 觸發條件與 Agent 執行流程
│   ├── speak.ps1          # Windows 主控、播放與備援腳本
│   ├── speak_stream.py    # Edge-TTS 串流播放器
│   ├── tts_lexicon.py     # 讀音替換表載入（自帶那份＋同層另外三份合併）
│   └── tts-lexicon.md     # 讀音替換表（四個 repo 各一份、內容相同）
├── tests/                 # 不連網、不播放聲音的隔離測試
├── AGENTS.md              # 跨 Agent 專案藍圖
├── handoff.md             # 跨工作階段交接（本機檔，git 不追蹤，靠 GDrive 同步）
├── CLAUDE.md              # Claude Code 橋接
├── .gitattributes         # 固定文字檔為 LF，避免跨電腦 hash 漂移
├── README.md              # 專案安裝與使用說明
├── LICENSE                # MIT 授權
└── .gitignore             # 本機與敏感檔排除規則
```

## 同步層級（本專案初始化至第 3 層級）

| 層級 | 平台 | 位置 | 讀取時機 |
|------|------|------|---------|
| L1 | 本地（GDrive） | `AGENTS.md`＋`handoff.md`＋`CLAUDE.md`（橋接） | 每個 session |
| L2 | GitHub | [changyiwu/agent-speak-skill](https://github.com/changyiwu/agent-speak-skill)（公開） | 指定時 |
| L3 | Obsidian | `agent-speak-skill/專案工作流程.md` | 有需要時 |

## 三個檔案的職責（依「時效性」分家，不是依「詳細程度」）

| 檔案 | 時效 | 寫入方式 | 放什麼 |
|------|------|---------|--------|
| `handoff.md` | **只對下一個 session 有效**，過期即丟 | 每次收工整份重寫 | 做到哪、下一步、**這次**的暫時 workaround |
| `AGENTS.md`（本檔） | **長期有效**，每個 session 都適用 | 只有規則本身變了才改 | 目標、路線圖、常設規則、結構 |
| Obsidian／`git log` | **歷史**：發生過什麼、為什麼 | 只增不刪 | 決策紀錄、踩坑完整版、逐次進度 |

驗收標準：**`handoff.md` 整份刪掉，不應損失任何長期資訊**——會的話代表該升級進本檔卻沒升級。

**本檔不要出現的東西**：❌ `## 最近進度`／逐次工作紀錄、❌ 決策理由與踩坑完整版。歷史寫 L3 筆記的〈🗓️ 最近更動紀錄〉〈🧠 決策紀錄〉〈🕳️ 踩坑筆記〉；踩過的坑只把**結論**收斂成一條祈使句寫進〈工作約定〉，原因留 L3。

## 工作約定

- 任何 Agent、任何電腦：**開工先讀 `handoff.md`，收工必更新 `handoff.md`**
- 修改共用檔案前先讀最新內容，避免覆蓋其他 Agent 的變更
- 所有回應與文件使用繁體中文
- 修改前先確認計畫，優先保留原有資料結構
- 全域技能目錄、Git commit、push 與部署必須取得使用者授權；專案初始化請求僅授權本專案的初始化流程
- 本專案 GitHub repo 為公開；commit 前必須掃描敏感資料與不應公開的素材
- 四個 Agent 的安裝來源固定為 `speak/`，安裝名稱由 frontmatter `name: speak` 決定
- 同步前先確認 Git 來源可信；同步後逐一比對檔案清單、SHA-256 與 UTF-8 BOM
- **`speak.ps1` 必須用 `pwsh` 執行**。它是 UTF-8 無 BOM，Windows PowerShell 5.1 會以 ANSI 解讀，中文變亂碼、引號被吃掉，在 **parse 階段就失敗**（`Unexpected token ')'`、`The string is missing the terminator`），連 `-Check` 都跑不到。**看到這種語法錯誤是用錯直譯器，不是腳本壞掉**
- **`pwsh` 可能是 winget 的 MSIX 版**，解析到 `AppData\Local\Microsoft\WindowsApps\pwsh.exe`，`C:\Program Files\PowerShell` 並不存在。一般沙箱看不到 `WindowsApps`，會**誤報 pwsh 未安裝**——那是假性缺少，不要重裝，實體在 `C:\Program Files\WindowsApps\Microsoft.PowerShell_*`
- **不要把使用者提供的講稿直接插入 shell 命令字串**，一律寫成 UTF-8 暫存文字檔再用 `-File` 傳入
- **讀音替換表自帶一份**：`speak/tts-lexicon.md`，跟技能一起安裝。這份表有**四份、內容逐位元組相同**（另外三份在 agent-video-specs、ai-video-workflow、voxcpm2-voice-cloner 的根目錄；四個 repo 都公開，各自單獨下載就要能用），**改表時四份一起改**，用 `python ai-video-workflow/tools/tts_lexicon.py --check`／`--sync` 檢查與合併。`tts_lexicon.py` 會把找得到的另外三份一起讀（自帶那份優先）；不要 import 別的 repo 的程式，解析規則要跟表頭寫的一致。任何一份讀不到或壞掉都跳過，全部找不到必須安靜地照原文念（2026-10-20 前曾規定本技能不內建條目、只讀 ai-video-workflow 那份，結果單獨安裝的人完全沒有替換，已廢止）
- **呼叫 Edge-TTS 一律用 `python -m edge_tts`，不要直接跑 pip 產生的 `edge-tts.exe`**：它沒有簽章，Windows 智慧型應用程式控制開啟時會被封鎖（錯誤碼 4551），pwsh 7.6 擷取輸出時還會誤報成 `StandardOutputEncoding is only supported when standard output is redirected`——看到這個錯誤是被封鎖，不是編碼問題
- winget 裝完會改 PATH，**同一個 shell session 要重新載入環境變數**才找得到 `pwsh`／`ffplay`

## 全域技能同步狀態

2026-10-20 重新同步（`88577a7`：讀音替換表＋整檔模式改用 `python -m edge_tts`）；四份副本各 5 個檔案，與專案來源的相對檔案清單及 SHA-256 完全一致，沒有額外檔案，且 `SKILL.md` 均無 UTF-8 BOM。

- Claude Code：`~\.claude\skills\speak`
- Codex：`~\.agents\skills\speak`
- OpenCode：`~\.config\opencode\skills\speak`
- Antigravity：`~\.gemini\config\skills\speak`

四個安裝目錄與本機語音依賴**都不跨電腦同步**，每台要各自安裝依賴並跑 `sync-skills`。**哪台裝到什麼程度、副本是哪一版，記在 `handoff.md`**（本機檔，不進 repo）。跨機安裝清單在 `我的雲端硬碟\agents\.skill-install\<電腦名>.json`，同樣不在 repo 內。
