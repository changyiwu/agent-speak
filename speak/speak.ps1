# speak.ps1 — 快速語音回覆（預設串流：邊生成邊播；備援整檔；再備援作業系統內建語音）
# 用法：
#   pwsh -ExecutionPolicy Bypass -File speak.ps1 "要唸的文字"
#   pwsh -ExecutionPolicy Bypass -File speak.ps1 -File 講稿.txt
#   pwsh -ExecutionPolicy Bypass -File speak.ps1 "文字" -Voice zh-TW-HsiaoYuNeural
#   pwsh -ExecutionPolicy Bypass -File speak.ps1 "文字" -Out "<路徑>/回覆.mp3"   # 指定 -Out 時走整檔模式並保留音檔
#
# 三層備援鏈，每層的平台差異：
#   1. 串流（Edge-TTS + ffplay/mpv）      — 兩平台相同
#   2. 整檔播放                            — Windows 走 MediaPlayer/WMPlayer，macOS 走 afplay
#   3. 離線備援                            — Windows 走 SAPI，macOS 走內建 say
#
# 送進 Edge-TTS 前（第 1、2 層）先套讀音替換表 tts-lexicon.md（找法見 tts_lexicon.py）；
# 第 3 層是別的引擎，照原文念。-Check 會印出用了哪份表。
param(
  [Parameter(Position = 0)][string]$Text,
  [string]$File,
  [ValidatePattern('^[A-Za-z0-9-]+$')]
  [string]$Voice = "zh-TW-HsiaoChenNeural",
  [string]$Out,
  [switch]$NoStream,
  [switch]$Check
)
$ErrorActionPreference = "Stop"

if ($null -eq $IsWindows) {
  throw '需要 PowerShell 7（pwsh）；5.1 沒有 $IsWindows，平台判斷會靜默走錯分支'
}

function Get-PythonCommand {
  foreach ($name in @("python", "python3", "py")) {
    $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
      return [pscustomobject]@{
        Source = $command.Source
        PrefixArgs = if ($name -eq "py") { @("-3") } else { @() }
      }
    }
  }
  return $null
}

# 讀音替換表的 Python 輔助程式輸出純 ASCII 的 JSON，避開主控台編碼把中文弄壞
$LexiconScript = if ($PSScriptRoot) { Join-Path $PSScriptRoot "tts_lexicon.py" } else { $null }
function Invoke-Lexicon($py, [string[]]$argList, $inputText) {
  if (-not $py -or -not $LexiconScript -or -not (Test-Path -LiteralPath $LexiconScript)) { return $null }
  try {
    $json = if ($null -ne $inputText) { $inputText | & $py.Source @($py.PrefixArgs) $LexiconScript @argList --json 2>$null }
            else { & $py.Source @($py.PrefixArgs) $LexiconScript @argList --json 2>$null }
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    return ($json -join "") | ConvertFrom-Json
  } catch { return $null }
}

function Get-LexiconInfo($py) {
  $info = Invoke-Lexicon $py @("--where") $null
  if (-not $info) { return "unavailable" }
  if (-not $info.path) { return "none" }
  "$($info.path)（$($info.count) 條）"
}

# 找不到表、沒有 Python 或任何錯誤都回原文，語音回覆不因此失敗
function Get-SpeakableText($py, [string]$t) {
  $r = Invoke-Lexicon $py @("-") $t
  if ($r -is [string] -and $r.Trim()) { return $r.Trim() }   # 管線會在尾端多帶一個換行
  return $t
}

function Test-EdgeModule($py) {
  if (-not $py) { return $false }
  try {
    & $py.Source @($py.PrefixArgs) -c "import edge_tts" 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch { return $false }
}

# 整檔模式用哪條路生成：優先 python -m edge_tts。pip 產生的 edge-tts.exe 啟動器沒有簽章，
# Windows 智慧型應用程式控制會封鎖它（pwsh 7.6 擷取輸出時還會誤報成 StandardOutputEncoding 錯誤）；
# python.exe 有簽章不受影響。沒有 Python 模組（例如 pipx 安裝）才退回 edge-tts 指令，且要真的跑得起來。
function Get-EdgeFileCommand($py) {
  if (Test-EdgeModule $py) {
    return [pscustomobject]@{ Source = $py.Source; PrefixArgs = @($py.PrefixArgs) + @("-m", "edge_tts") }
  }
  $cli = Get-Command edge-tts -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $cli) { return $null }
  try {
    $null = & $cli.Source --version 2>&1
    if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ Source = $cli.Source; PrefixArgs = @() } }
  } catch { }
  return $null
}

function Test-Assembly([string]$name) {
  try { Add-Type -AssemblyName $name -ErrorAction Stop; return $true }
  catch { return $false }
}

if ($Check) {
  $py = Get-PythonCommand
  $hasEdgeModule = Test-EdgeModule $py
  $hasPlayer = [bool]((Get-Command mpv -ErrorAction SilentlyContinue) -or (Get-Command ffplay -ErrorAction SilentlyContinue))
  $hasFileTts = [bool](Get-EdgeFileCommand $py)   # 與整檔模式實際走的路相同
  $hasOffline = if ($IsWindows) { Test-Assembly "System.Speech" }
                else { [bool](Get-Command say -ErrorAction SilentlyContinue) }
  "STREAM_READY=$([bool]($py -and $hasEdgeModule -and $hasPlayer))"
  "FILE_READY=$hasFileTts"
  "OFFLINE_READY=$hasOffline"     # Windows 是 SAPI，macOS 是內建 say
  "LEXICON=$(Get-LexiconInfo $py)"  # 讀音替換表；none 代表照原文念
  if (-not $hasFileTts -and -not $hasOffline) { exit 1 }
  return
}

if ($File -and $Text) { throw "-Text 與 -File 只能擇一" }
if ($File) { $Text = Get-Content -LiteralPath $File -Raw -Encoding UTF8 }
if (-not $Text) { throw "沒有要唸的文字（positional 或 -File 擇一）" }

function Get-MacSayVoice {
  # 依台灣中文優先排序；找不到就回 $null，讓 say 用系統預設嗓音
  $voices = & say -v '?' 2>$null
  foreach ($want in 'Meijia', 'Sinji', 'Tingting') {
    if ($voices -match "(?m)^$want\s") { return $want }
  }
  return $null
}

function Invoke-OfflineFallback([string]$t) {
  if ($IsWindows) {
    Add-Type -AssemblyName System.Speech
    $sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try { $sp.Speak($t) }
    finally { $sp.Dispose() }
    return "已唸完（SAPI 離線備援，未產生音檔）"
  }

  # macOS：say 是系統內建，不需安裝。走 -f 讀檔而不是把講稿當參數，
  # 避免以 - 開頭的文字被當成選項，也避開長文字的參數長度限制。
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("say_{0}.txt" -f [guid]::NewGuid().ToString("N"))
  [IO.File]::WriteAllText($tmp, $t, [Text.UTF8Encoding]::new($false))
  try {
    $v = Get-MacSayVoice
    if ($v) { & say -v $v -f $tmp } else { & say -f $tmp }
  } finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  }
  $suffix = if ($v) { "／$v" } else { "／系統預設嗓音" }
  "已唸完（macOS say 離線備援$suffix，未產生音檔）"
}

# ============ 1. 串流模式（預設）：邊生成邊播放 ============
$py = Get-PythonCommand
$hasPlayer = (Get-Command mpv -ErrorAction SilentlyContinue) -or (Get-Command ffplay -ErrorAction SilentlyContinue)
if (-not $NoStream -and -not $Out -and $py -and $hasPlayer) {
  $streamScript = Join-Path $PSScriptRoot "speak_stream.py"
  $result = $Text | & $py.Source @($py.PrefixArgs) $streamScript - $Voice 2>&1
  if ($LASTEXITCODE -eq 0) {
    "已唸完（Edge-TTS 串流／$Voice）｜$($result -join '｜')"
    return
  }
  Write-Warning "Edge-TTS 串流失敗，改用整檔或 SAPI 備援。"
  # 串流失敗 → 往下走整檔模式
}

# ============ 2. 整檔模式：生成 mp3 後行內播放（無視窗） ============
# 這一層任何例外都退到離線備援，語音回覆不因整檔模式壞掉而整個失敗
$edge = Get-EdgeFileCommand $py
if (-not $edge) { Invoke-OfflineFallback $Text; return }
$ttsText = Get-SpeakableText $py $Text

$keepOutput = [bool]$Out
$tmpDir = Join-Path ([IO.Path]::GetTempPath()) "agent-speak"
if (-not $keepOutput) {
  $Out = Join-Path $tmpDir ("speak_{0}.mp3" -f [guid]::NewGuid().ToString("N"))
}
# 講稿寫成 UTF-8 暫存檔交給 --file，不放進命令列：避開以 - 開頭被當成選項，也避開命令列長度上限
$textFile = Join-Path $tmpDir ("speak_{0}.txt" -f [guid]::NewGuid().ToString("N"))
$played = $false
try {
  New-Item -ItemType Directory -Force $tmpDir | Out-Null
  [IO.File]::WriteAllText($textFile, $ttsText, [Text.UTF8Encoding]::new($false))
  $edgeOutput = & $edge.Source @($edge.PrefixArgs) --file $textFile --voice $Voice --write-media $Out 2>&1
  $edgeExitCode = $LASTEXITCODE
  $validOutput = (Test-Path -LiteralPath $Out) -and ((Get-Item -LiteralPath $Out).Length -gt 0)
  if ($edgeExitCode -ne 0 -or -not $validOutput) {
    throw "Edge-TTS 整檔生成失敗（exit $edgeExitCode）：$(@($edgeOutput)[-1])"
  }

  if (-not $IsWindows) {
    # macOS：afplay 是系統內建，阻塞到播完、不開視窗，剛好符合「絕不 Start-Process 開播放器」
    & afplay $Out
    $played = ($LASTEXITCODE -eq 0)
  }
  else {
    try {
      Add-Type -AssemblyName PresentationCore
      $mp = New-Object System.Windows.Media.MediaPlayer
      try {
        $mp.Volume = 1.0
        $mp.Open([Uri](Resolve-Path -LiteralPath $Out).Path)
        $tries = 0
        while (-not $mp.NaturalDuration.HasTimeSpan -and $tries -lt 100) { Start-Sleep -Milliseconds 100; $tries++ }
        if (-not $mp.NaturalDuration.HasTimeSpan) { throw "無法取得音檔長度" }
        $mp.Play()
        Start-Sleep -Seconds ([math]::Ceiling($mp.NaturalDuration.TimeSpan.TotalSeconds) + 1)
      } finally {
        $mp.Close()
      }
      $played = $true
    } catch {
      try {
        $p = New-Object -ComObject WMPlayer.OCX.7
        try {
          $p.settings.volume = 100
          $p.URL = (Resolve-Path -LiteralPath $Out).Path
          $p.controls.play()
          $deadline = (Get-Date).AddMinutes(5)
          Start-Sleep -Milliseconds 600
          while ($p.playState -in 6, 9, 11) {
            if ((Get-Date) -gt $deadline) { throw "WMPlayer 載入逾時" }
            Start-Sleep -Milliseconds 200
          }
          while ($p.playState -eq 3) {
            if ((Get-Date) -gt $deadline) { throw "WMPlayer 播放逾時" }
            Start-Sleep -Milliseconds 300
          }
        } finally {
          $p.close()
        }
        $played = $true
      } catch { }
    }
  }
  if (-not $played) { Write-Warning "本機播放器失敗，改用作業系統內建語音備援。" }
} catch {
  Write-Warning "$($_.Exception.Message)；改用作業系統內建語音備援。"
} finally {
  Remove-Item -LiteralPath $textFile -Force -ErrorAction SilentlyContinue
  if (-not $keepOutput -and (Test-Path -LiteralPath $Out)) {
    Remove-Item -LiteralPath $Out -Force -ErrorAction SilentlyContinue
  }
}

if ($played) {
  if ($keepOutput) { "已唸完（Edge-TTS 整檔／$Voice），音檔：$Out" }
  else { "已唸完（Edge-TTS 整檔／$Voice），暫存音檔已清理" }
} else {
  Invoke-OfflineFallback $Text
}
