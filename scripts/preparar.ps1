$ErrorActionPreference = 'Stop'
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectDir
try {
    if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE) { throw 'Instala Python 3.12 con el lanzador py.' }
    }
    & .venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
    if ($LASTEXITCODE) { throw 'No se completó la instalación de Python.' }
    & npm.cmd --prefix frontend ci --no-audit
    if ($LASTEXITCODE) { throw 'No se completó npm ci. Usa Node 22.' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE) { throw 'Next.js no compiló.' }
    Write-Host 'Preparado. Inicia con .\scripts\iniciar.ps1'
} finally { Pop-Location }
