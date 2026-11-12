param([Parameter(Mandatory=$true)][string]$FitbitCsv,[Parameter(Mandatory=$true)][string]$GymCsv)
$ErrorActionPreference = 'Stop'
$base=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$out=Join-Path $base 'data/raw'
[IO.Directory]::CreateDirectory($out) | Out-Null
# Only the two files selected by the operator. Never put these archives in git.
foreach($item in @(@($FitbitCsv,'dailyActivity_merged.csv'),@($GymCsv,'gym_members_exercise_tracking.csv'))){
    $src=(Resolve-Path -LiteralPath $item[0]).Path
    $dst=Join-Path $out $item[1]
    if(Test-Path -LiteralPath $dst){
        if((Get-FileHash -LiteralPath $src).Hash -ne (Get-FileHash -LiteralPath $dst).Hash){throw "El archivo de destino es distinto; elija el conjunto de estudio antes de sustituirlo."}
    }else{Copy-Item -LiteralPath $src -Destination $dst}
}
Write-Host 'Archivos preparados en data/raw (excluido de Git).'
