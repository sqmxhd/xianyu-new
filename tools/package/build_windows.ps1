param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $ProjectRoot

if (-not (Test-Path "apps/admin/dist/index.html")) {
    npm --prefix apps/admin ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm --prefix apps/admin run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
}

$BuildVenv = Join-Path $ProjectRoot "artifacts/.package-venv-windows"
if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv $BuildVenv
} else {
    python -m venv $BuildVenv
}
if ($LASTEXITCODE -ne 0) { throw "python venv creation failed" }

$Python = Join-Path $BuildVenv "Scripts/python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install `
    -r apps/api/requirements.txt `
    -r integrations/xianyu_core/requirements.txt `
    -r tools/package/requirements.txt

$Arguments = @("tools/package/build.py", "--platform", "windows-x64")
if ($Version) {
    $Arguments += @("--version", $Version)
}
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw "Windows package build failed" }
