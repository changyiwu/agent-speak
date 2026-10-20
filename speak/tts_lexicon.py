# -*- coding: utf-8 -*-
"""讀音替換表：送進 Edge-TTS 前把念錯的詞換成念得對的寫法（多音字、英文詞）。

Edge-TTS 不能用 SSML 指定讀音，只能改字。表是 Markdown（| 原文 | 改寫 | 說明 |），
主表與其他 TTS 專案共用，本技能不內建任何條目；找不到表就照原文念，不報錯、不拖慢。

找表的順序（找到第一份就停）：
  1. 環境變數 TTS_LEXICON（有設就只用它）
  2. 從本技能資料夾往上，每一層找 ai-video-workflow/tts-lexicon.md
  3. 常見的雲端硬碟位置（家目錄底下，不寫死磁碟代號）：
       ~/我的雲端硬碟、~/My Drive、~/Google Drive/(我的雲端硬碟|My Drive)、
       macOS 的 ~/Library/CloudStorage/GoogleDrive-*/(我的雲端硬碟|My Drive)
     底下的 agents/ai-video-workflow/tts-lexicon.md
SPEAK_DEBUG=1 時在 stderr 印出用了哪份表。

試表：python tts_lexicon.py "要念的句子"
看用哪份：python tts_lexicon.py --where
"""
import os
import re
import sys

NAME = "tts-lexicon.md"
REL = os.path.join("ai-video-workflow", NAME)
HEAD = ("原文", "改寫")
DRIVES = ("我的雲端硬碟", "My Drive")


def debug(msg):
    if os.environ.get("SPEAK_DEBUG"):
        print(f"[lexicon] {msg}", file=sys.stderr, flush=True)


def candidates(skill_dir=None, home=None):
    """依序回傳可能的主表位置（不檢查存在）"""
    env = os.environ.get("TTS_LEXICON")
    if env:
        yield os.path.expanduser(env)
        return
    d = os.path.abspath(skill_dir or os.path.dirname(os.path.abspath(__file__)))
    while True:
        yield os.path.join(d, REL)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    home = home or os.path.expanduser("~")
    roots = [os.path.join(home, x) for x in DRIVES]
    roots += [os.path.join(home, "Google Drive", x) for x in DRIVES]
    if sys.platform == "darwin":
        import glob                                      # 只有 macOS 用得到，省下其他平台的匯入時間
        for acct in sorted(glob.glob(os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*"))):
            roots += [os.path.join(acct, x) for x in DRIVES]
    for r in roots:
        yield os.path.join(r, "agents", REL)


def find(skill_dir=None, home=None):
    for p in candidates(skill_dir, home):
        if os.path.isfile(p):
            return p
    return None


def cells(line):
    s = line.strip()[1:]                                 # 去掉開頭的 |
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    out = []
    for c in re.split(r"(?<!\\)\|", s):
        c = c.strip().replace("\\|", "|")
        if len(c) >= 2 and c[0] == c[-1] == "`":         # `GPT four` 這種用反引號標出空白的寫法
            c = c[1:-1]
        out.append(c)
    return out


def parse(path):
    """只讀表頭是「原文｜改寫」的 Markdown 表格；格式不對的列跳過，不讓語音回覆失敗"""
    table, inside = {}, False
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith("|"):
            inside = False
            continue
        c = cells(line)
        if tuple(c[:2]) == HEAD:
            inside = True
            continue
        if not inside or all(re.fullmatch(r":?-+:?", x) for x in c if x):
            continue
        if len(c) < 2 or not c[0] or not c[1]:
            debug(f"{path}:{n} 格式不對，跳過：{line}")
            continue
        table[c[0]] = c[1]
    return table


_cache = None


def load(skill_dir=None, home=None):
    """回傳 (表的路徑或 None, 表)；同一個行程只讀一次，任何錯誤都當成沒有表"""
    global _cache
    if _cache is None:
        path, table = None, {}
        try:
            path = find(skill_dir, home)
            if path:
                table = parse(path)
        except Exception as e:                           # 表壞掉也不能讓語音回覆失敗
            debug(f"讀表失敗，不做替換：{e}")
            path, table = None, {}
        debug(f"{len(table)} 條：{path}" if path else f"找不到 {NAME}，不做替換")
        _cache = (path, table)
    return _cache


def speakable(text, table=None):
    """長的原文先比對，一次掃完：換過的結果不會再被其他條目換"""
    if table is None:
        table = load()[1]
    if not table:
        return text
    pat = re.compile("|".join(re.escape(k) for k in sorted(table, key=len, reverse=True)))
    return pat.sub(lambda m: table[m.group(0)], text)


def main(argv):
    import json
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if argv[:1] == ["--where"]:
        path, table = load()
        result = {"path": path, "count": len(table)}
        print(json.dumps(result) if as_json else (f"{path}（{len(table)} 條）" if path else "none"))
        return
    if argv and argv[0] != "-":
        text = argv[0]
    else:
        text = sys.stdin.buffer.read().decode("utf-8")
    out = speakable(text)
    # --json 輸出純 ASCII，給 speak.ps1 讀，避開主控台編碼（cp950 等）把中文弄壞
    print(json.dumps(out) if as_json else out)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main(sys.argv[1:])
