# -*- coding: utf-8 -*-
"""讀音替換表：送進 Edge-TTS 前把念錯的詞換成念得對的寫法（多音字、英文詞）。

Edge-TTS 不能用 SSML 指定讀音，只能改字。表是 Markdown（| 原文 | 改寫 | 說明 |），
本技能自帶一份 tts-lexicon.md（跟本檔放在一起，裝成全域技能時一起複製）。這份表有四份、內容完全相同，
另外三份在 media-video-specs、media-short-film、media-voice-clone 的根目錄；找得到就一起讀（合併），
同一個原文以近的為準。任何一份讀不到或壞掉都跳過，全部找不到就照原文念，不報錯、不拖慢。

找表的順序（遠的在前、近的覆蓋遠的）：
  1. 另外三份：從本技能資料夾往上，每一層找 <repo>/tts-lexicon.md（從 repo 原始檔執行時找得到）；
     找不到再看常見的雲端硬碟位置（家目錄底下，不寫死磁碟代號；裝成全域技能時靠這個）：
       ~/我的雲端硬碟、~/My Drive、~/Google Drive/(我的雲端硬碟|My Drive)、
       macOS 的 ~/Library/CloudStorage/GoogleDrive-*/(我的雲端硬碟|My Drive)
     底下的 agents/<repo>/tts-lexicon.md
  2. 自帶的那份（設了環境變數 TTS_LEXICON 就改讀它指的表）
SPEAK_DEBUG=1 時在 stderr 印出用了哪幾份表。

試表：python tts_lexicon.py "要念的句子"
看用哪幾份：python tts_lexicon.py --where
"""
import os
import re
import sys

NAME = "tts-lexicon.md"
HEAD = ("原文", "改寫")
DRIVES = ("我的雲端硬碟", "My Drive")
# 同內容的另外三份（repo 名稱）；表都在 repo 根目錄
SIBLINGS = ("media-video-specs", "media-short-film", "media-voice-clone")


def debug(msg):
    if os.environ.get("SPEAK_DEBUG"):
        print(f"[lexicon] {msg}", file=sys.stderr, flush=True)


def skill_dir_of(skill_dir=None):
    return os.path.abspath(skill_dir or os.path.dirname(os.path.abspath(__file__)))


def own(skill_dir=None):
    """自帶的那份；設了 TTS_LEXICON 就改用它指的表"""
    env = os.environ.get("TTS_LEXICON")
    return os.path.expanduser(env) if env else os.path.join(skill_dir_of(skill_dir), NAME)


def drive_roots(home=None):
    home = home or os.path.expanduser("~")
    roots = [os.path.join(home, x) for x in DRIVES]
    roots += [os.path.join(home, "Google Drive", x) for x in DRIVES]
    if sys.platform == "darwin":
        import glob                                      # 只有 macOS 用得到，省下其他平台的匯入時間
        for acct in sorted(glob.glob(os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*"))):
            roots += [os.path.join(acct, x) for x in DRIVES]
    return [os.path.join(r, "agents") for r in roots]


def sibling_candidates(repo, skill_dir=None, home=None):
    """某一份的可能位置（不檢查存在）：先往上找，再找雲端硬碟"""
    d = skill_dir_of(skill_dir)
    while True:
        yield os.path.join(d, repo, NAME)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for a in drive_roots(home):
        yield os.path.join(a, repo, NAME)


def find_all(skill_dir=None, home=None):
    """存在的表，遠的在前、近的在後（自帶那份最近）"""
    out = []
    for repo in SIBLINGS:
        p = next((p for p in sibling_candidates(repo, skill_dir, home) if os.path.isfile(p)), None)
        if p:
            out.append(p)
    p = own(skill_dir)
    if os.path.isfile(p):
        out.append(p)
    seen, uniq = set(), []
    for p in out:
        key = os.path.normcase(os.path.realpath(p))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def find(skill_dir=None, home=None):
    """最近的那份（通常是自帶的）；一份都沒有就是 None"""
    files = find_all(skill_dir, home)
    return files[-1] if files else None


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
    """回傳 (最近那份表的路徑或 None, 合併後的表, 實際讀到的表清單)；同一個行程只讀一次，壞掉的表跳過"""
    global _cache
    if _cache is None:
        table, used = {}, []
        try:
            files = find_all(skill_dir, home)
        except Exception as e:                           # 找表本身出錯也不能讓語音回覆失敗
            debug(f"找表失敗，不做替換：{e}")
            files = []
        for p in files:
            try:
                table.update(parse(p))
                used.append(p)
            except Exception as e:                       # 一份壞掉不影響其他份
                debug(f"讀表失敗，跳過 {p}：{e}")
        debug(f"{len(table)} 條：{'、'.join(used)}" if used else f"找不到 {NAME}，不做替換")
        _cache = (used[-1] if used else None, table, used)
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
        path, table, used = load()
        result = {"path": path, "paths": used, "count": len(table)}
        if as_json:
            print(json.dumps(result))
        else:
            print("、".join(used) + f"（共 {len(table)} 條）" if used else "none")
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
