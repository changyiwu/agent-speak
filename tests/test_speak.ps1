# speak.ps1 的隔離測試；只執行靜態解析與 -Check，不播放聲音。
param([string]$ProjectRoot)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) { $ProjectRoot = Split-Path $PSScriptRoot -Parent }
$scriptPath = Join-Path $ProjectRoot "speak/speak.ps1"
$content = Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8

$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseInput(
  $content,
  [ref]$tokens,
  [ref]$errors
) | Out-Null
if ($errors.Count -gt 0) {
  throw "PowerShell 語法解析失敗：$($errors.Message -join '；')"
}

$scriptBlock = [scriptblock]::Create($content)
if ($content -notmatch '\[string\]\$Voice\s*=\s*"zh-TW-HsiaoChenNeural"') {
  throw "PowerShell 預設聲音不是 zh-TW-HsiaoChenNeural"
}
$checkOutput = @(& $scriptBlock -Check)
if (-not ($checkOutput -match '^STREAM_READY=')) { throw "缺少 STREAM_READY 檢查結果" }
if (-not ($checkOutput -match '^FILE_READY=')) { throw "缺少 FILE_READY 檢查結果" }
if (-not ($checkOutput -match '^OFFLINE_READY=')) { throw "缺少 OFFLINE_READY 檢查結果" }
if (-not ($checkOutput -match '^LEXICON=')) { throw "缺少 LEXICON 檢查結果" }

# 整檔模式送進 edge-tts 前的讀音替換：只取出相關函式來測，不連網、不播放
$ast = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$null, [ref]$null)
$functions = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)
foreach ($name in "Get-PythonCommand", "Invoke-Lexicon", "Get-SpeakableText", "Test-EdgeModule", "Get-EdgeFileCommand") {
  . ([scriptblock]::Create(($functions | Where-Object Name -eq $name).Extent.Text))
}
$py = Get-PythonCommand
$tmpDir = Join-Path ([IO.Path]::GetTempPath()) ("speak_test_{0}" -f [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmpDir | Out-Null
# 只讀測試給的表：把 tts_lexicon.py 複製到暫存資料夾（往上找不到另外三份同內容的表），
# 家目錄也暫時指到暫存資料夾（找不到雲端硬碟裡的那幾份）
$isoSkill = Join-Path $tmpDir "skill"
New-Item -ItemType Directory -Force $isoSkill | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "speak/tts_lexicon.py") -Destination $isoSkill
$LexiconScript = Join-Path $isoSkill "tts_lexicon.py"
$savedLexicon = $env:TTS_LEXICON
$savedUserProfile = $env:USERPROFILE
$savedHome = $env:HOME
$env:USERPROFILE = $tmpDir
$env:HOME = $tmpDir
try {
  $lexicon = Join-Path $tmpDir "tts-lexicon.md"
  [IO.File]::WriteAllText($lexicon, "| 原文 | 改寫 | 說明 |`n|---|---|---|`n| 奇數 | 基數 | |`n| GPT-4 | ``GPT four`` | |`n", [Text.UTF8Encoding]::new($false))
  $sample = "奇數和 GPT-4"
  if ($py) {
    $env:TTS_LEXICON = $lexicon
    $got = Get-SpeakableText $py $sample
    if ($got -ne "基數和 GPT four") { throw "整檔模式沒有套讀音替換表：$got" }
  }
  $env:TTS_LEXICON = Join-Path $tmpDir "missing.md"
  if ((Get-SpeakableText $py $sample) -ne $sample) { throw "找不到替換表時應照原文" }
  if ((Get-SpeakableText $null $sample) -ne $sample) { throw "沒有 Python 時應照原文" }

  # 整檔模式的生成指令：有 edge_tts 模組就走 python -m edge_tts，不碰可能被應用程式控制封鎖的 edge-tts.exe
  $fileCmd = Get-EdgeFileCommand $py
  if ($py -and (Test-EdgeModule $py)) {
    if ($fileCmd.Source -ne $py.Source -or ($fileCmd.PrefixArgs -join " ") -notmatch '-m edge_tts$') {
      throw "有 edge_tts 模組時整檔模式應走 python -m edge_tts：$($fileCmd.Source) $($fileCmd.PrefixArgs)"
    }
  }
  if (-not ($checkOutput -contains "FILE_READY=$([bool]$fileCmd)")) { throw "-Check 的 FILE_READY 與整檔模式實際走的路不一致" }
  # 沒有 Python 也找不到 edge-tts 指令時回 $null，整檔模式直接退到離線備援
  $savedPath = $env:PATH
  try {
    $env:PATH = $tmpDir
    if ($null -ne (Get-EdgeFileCommand $null)) { throw "沒有任何 Edge-TTS 時應回 null" }
  } finally { $env:PATH = $savedPath }
} finally {
  $env:TTS_LEXICON = $savedLexicon
  $env:USERPROFILE = $savedUserProfile
  $env:HOME = $savedHome
  Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

$threw = $false
try {
  & $scriptBlock -Text "測試" -File "不存在.txt"
} catch {
  $threw = ($_.Exception.Message -match "只能擇一")
}
if (-not $threw) { throw "-Text 與 -File 同時使用時應拒絕執行" }

"POWERSHELL_TESTS_PASSED"
