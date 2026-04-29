Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

Write-Host "Building standalone executable with PyInstaller..."
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/local-llm-wiki.spec

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $repoRoot\\dist\\local-llm-wiki.exe"
