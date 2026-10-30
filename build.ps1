param(
  [string]$Python = 'python',
  [switch]$SkipRender
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
  & $Python tools/build.py
  if ($LASTEXITCODE -ne 0) { throw 'PDF build failed' }
  if ($SkipRender) {
    & $Python tools/verify.py
  } else {
    & $Python tools/verify.py --render
  }
  if ($LASTEXITCODE -ne 0) { throw 'PDF verification failed' }
} finally {
  Pop-Location
}
