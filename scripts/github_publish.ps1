# AnyDownloader - GitHub publisher (plain git push over HTTPS + REST API via curl)
# Asks for a Personal Access Token once, then:
#   1. creates the repo (REST API)
#   2. sets description + topics (REST API)
#   3. pushes main with plain git over HTTPS using the token
#   4. creates the v1.0.0 release and uploads the exe (REST API)
# The token is kept in memory only and never written to disk.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Set-Location "C:\Users\SHISHIR\Downloads\AnyDownloader"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AnyDownloader - GitHub publisher" -ForegroundColor Cyan
Write-Host "  Step 1: open  https://github.com/settings/tokens/new" -ForegroundColor White
Write-Host "  Step 2: create a CLASSIC token, tick 'repo' scope" -ForegroundColor White
Write-Host "  Step 3: generate, copy, paste it below (input hidden)" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$sec = Read-Host "Paste your GitHub Personal Access Token" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
$token = $token.Trim()
if (-not $token) { Write-Host "No token entered - aborting." -ForegroundColor Red; Read-Host "Enter to close"; exit 1 }

$auth = "Authorization: Bearer $token"

# --- 0. verify token -------------------------------------------------------
$me = curl.exe -s -H $auth https://api.github.com/user | ConvertFrom-Json
if (-not $me.login) { Write-Host "Token rejected by GitHub." -ForegroundColor Red; Read-Host "Enter to close"; exit 1 }
$login = $me.login
Write-Host "Signed in as: $login" -ForegroundColor Green

# --- 1. create the repository ---------------------------------------------
$repoJson = '{"name":"AnyDownloader","description":"A polished, Apple-style video & audio downloader for Windows, powered by yt-dlp. Single exe, batch downloads, beautiful UI.","homepage":"https://github.com/' + $login + '/AnyDownloader","private":false,"has_issues":true,"has_wiki":false,"auto_init":false}'
$repo = curl.exe -s -X POST -H $auth -H "Accept: application/vnd.github+json" -d $repoJson https://api.github.com/user/repos | ConvertFrom-Json
if ($repo.html_url) {
    Write-Host "Repository created: $($repo.html_url)" -ForegroundColor Green
} elseif ($repo.errors -or $repo.message -match "already exists") {
    Write-Host "Repository already exists - continuing." -ForegroundColor Yellow
} else {
    Write-Host "Repo creation problem: $($repo.message)" -ForegroundColor Yellow
}

# --- 2. topics --------------------------------------------------------------
$topicsJson = '{"names":["yt-dlp","youtube-downloader","video-downloader","audio-downloader","downloader","windows","desktop-app","pyside6","qt","python","batch-download","ffmpeg"]}'
$null = curl.exe -s -X PUT -H $auth -H "Accept: application/vnd.github+json" -d $topicsJson "https://api.github.com/repos/$login/AnyDownloader/topics"
Write-Host "Topics set." -ForegroundColor Green

# --- 3. push with plain git over HTTPS -------------------------------------
git add -A 2>$null
git -c core.safecrlf=false commit -m "AnyDownloader v1.0.0" 2>$null | Out-Null
git remote remove origin 2>$null | Out-Null
git remote add origin "https://github.com/$login/AnyDownloader.git"

$pushUrl = "https://x-access-token:$token@github.com/$login/AnyDownloader.git"
Write-Host "Pushing main branch (plain git over HTTPS)..."
git push $pushUrl main:main 2>&1 | ForEach-Object { if ($_ -notmatch "x-access-token") { Write-Host $_ } }
if ($LASTEXITCODE -ne 0) { Write-Host "Push FAILED." -ForegroundColor Red; Read-Host "Enter to close"; exit 1 }
git branch --set-upstream-to=origin/main main 2>$null | Out-Null
Write-Host "Pushed." -ForegroundColor Green

# --- 4. release v1.0.0 with the exe ----------------------------------------
$exe = "build\dist\AnyDownloader.exe"
if (-not (Test-Path $exe)) { Write-Host "exe not found at $exe - skipping release." -ForegroundColor Yellow; Read-Host "Enter to close"; exit 0 }

$relJson = '{"tag_name":"v1.0.0","target_commitish":"main","name":"AnyDownloader v1.0.0","body":"First public release of AnyDownloader.","draft":false,"prerelease":false}'
$rel = curl.exe -s -X POST -H $auth -H "Accept: application/vnd.github+json" -d $relJson "https://api.github.com/repos/$login/AnyDownloader/releases" | ConvertFrom-Json
if ($rel.upload_url) {
    Write-Host "Release created: $($rel.html_url)" -ForegroundColor Green
    $uploadBase = $rel.upload_url -replace "\{\?name,label\}$", ""
    Write-Host "Uploading exe (about 100 MB, be patient)..."
    curl.exe -s -X POST -H $auth -H "Content-Type: application/octet-stream" --data-binary "@$exe" "$uploadBase?name=AnyDownloader-v1.0.0-windows-x64.exe" | Out-Null
    Write-Host "Release asset uploaded." -ForegroundColor Green
} else {
    Write-Host "Release problem: $($rel.message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ALL DONE - repository:  https://github.com/$login/AnyDownloader" -ForegroundColor Green
Write-Host "  Releases:               https://github.com/$login/AnyDownloader/releases" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Read-Host "Enter to close"
