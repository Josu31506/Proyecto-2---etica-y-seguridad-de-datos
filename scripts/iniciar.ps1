$ErrorActionPreference = 'Stop'
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Ejecuta primero .\scripts\preparar.ps1' }
& $pythonExe (Join-Path $PSScriptRoot 'demo.py')
exit $LASTEXITCODE
