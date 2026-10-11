param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('diagnostics-only', 'pull-result-fix')][string]$Kind,
    [string]$BuildDirectory = 'build-uds',
    [string]$OutputRoot = (Join-Path $PSScriptRoot '../../../artifacts')
)
$ErrorActionPreference = 'Stop'
$taskRepo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskBundle = Join-Path $taskRepo "$BuildDirectory/bundle"
if (!(Test-Path -LiteralPath (Join-Path $taskBundle 'azahar.exe'))) {
    throw "Build the bundle first: $taskBundle"
}
$taskName = "azaharplus-f1-cf9068844-$Kind-win64"
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$taskPackage = Join-Path $OutputRoot $taskName
if (Test-Path -LiteralPath $taskPackage) { throw "Package already exists: $taskPackage" }
New-Item -ItemType Directory -Path $taskPackage | Out-Null
Copy-Item -Path "$taskBundle/*" -Destination $taskPackage -Recurse
foreach ($taskHelper in @('README.md', 'capture-logs.ps1', 'analyze-logs.py')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskHelper) -Destination $taskPackage
}
$taskSource = Join-Path $taskPackage 'source'
$taskSourceHelpers = Join-Path $taskSource 'tools/uds_diagnostics'
New-Item -ItemType Directory -Path $taskSourceHelpers -Force | Out-Null
foreach ($taskHelper in @('dynarmic-clang23.patch', 'build-windows.ps1', 'verify_pull_packet.py',
                          'package-windows.ps1', 'capture-logs.ps1', 'analyze-logs.py',
                          'verify-bundle.py', 'README.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskHelper) -Destination $taskSourceHelpers
}
Copy-Item -LiteralPath (Join-Path $taskRepo 'license.txt') -Destination $taskPackage
& git -C $taskRepo diff cf9068844 -- src/core/hle/service/nwm/nwm_uds.cpp src/core/hle/service/nwm/nwm_uds.h src/network/artic_base/artic_base_client.h externals/httplib/httplib.h |
    Set-Content (Join-Path $taskSource 'nwm-uds.patch') -Encoding utf8NoBOM
if ($LASTEXITCODE) { throw 'Could not export UDS source patch.' }
$taskFileList = Get-ChildItem -LiteralPath $taskPackage -Recurse -File | ForEach-Object {
    [ordered]@{
        path = [IO.Path]::GetRelativePath($taskPackage, $_.FullName).Replace('\', '/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}
$taskManifest = [ordered]@{
    kind = $Kind
    base = 'cf9068844820f819a6eabbeeeb6a70d546e3e85a'
    repository = 'https://github.com/AzaharPlus/AzaharPlus'
    local_commit = (& git -C $taskRepo rev-parse HEAD)
    uds_source_sha256 = (Get-FileHash -LiteralPath (Join-Path $taskRepo 'src/core/hle/service/nwm/nwm_uds.cpp')).Hash
    created_utc = [DateTime]::UtcNow.ToString('o')
    files = @($taskFileList)
}
$taskManifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $taskPackage 'manifest.json') -Encoding utf8NoBOM
$taskZip = Join-Path $OutputRoot "$taskName.zip"
Compress-Archive -LiteralPath $taskPackage -DestinationPath $taskZip
$taskZipHash = (Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash
"$taskZipHash  $taskName.zip" | Set-Content "$taskZip.sha256" -Encoding ascii
Write-Output "Package: $taskZip"
Write-Output "SHA256: $taskZipHash"
