param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('host', 'client')][string]$Role,
    [string]$LogDirectory = (Join-Path $env:APPDATA 'AzaharPlus/log'),
    [string]$Destination = (Join-Path $PSScriptRoot 'captures')
)
$ErrorActionPreference = 'Stop'
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$taskCapture = Join-Path $Destination "$taskStamp-$Role"
New-Item -ItemType Directory -Path $taskCapture -Force | Out-Null
foreach ($taskLog in @('azahar_log.txt', 'azahar_log.old.txt')) {
    $taskSource = Join-Path $LogDirectory $taskLog
    if (Test-Path -LiteralPath $taskSource) {
        Copy-Item -LiteralPath $taskSource -Destination $taskCapture
    }
}
if (!(Test-Path -LiteralPath (Join-Path $taskCapture 'azahar_log.txt'))) {
    throw "No azahar_log.txt in $LogDirectory. For portable mode pass the user/log directory."
}
Get-ChildItem -LiteralPath $taskCapture -File | Get-FileHash -Algorithm SHA256 |
    Select-Object Path,Hash | ConvertTo-Json | Set-Content (Join-Path $taskCapture 'sha256.json')
Write-Output "Captured $Role logs: $taskCapture"
