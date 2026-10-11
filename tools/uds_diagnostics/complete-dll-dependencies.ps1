param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [string]$MsysRoot = (Join-Path $PSScriptRoot '../../../tools/msys64')
)
$ErrorActionPreference = 'Stop'
$taskBundle = [IO.Path]::GetFullPath($Bundle)
$taskMsys = [IO.Path]::GetFullPath($MsysRoot)
$taskObjdump = Join-Path $taskMsys 'clang64/bin/llvm-objdump.exe'
$taskQueue = [Collections.Generic.Queue[IO.FileInfo]]::new()
$taskKnown = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
Get-ChildItem -LiteralPath $taskBundle -File | ForEach-Object { [void]$taskKnown.Add($_.Name) }
Get-ChildItem -LiteralPath $taskBundle -Recurse -File | Where-Object {
    $_.Extension -in @('.dll', '.exe')
} | ForEach-Object { $taskQueue.Enqueue($_) }
$taskAdded = 0
while ($taskQueue.Count) {
    $taskPe = $taskQueue.Dequeue()
    $taskDump = & $taskObjdump -p $taskPe.FullName
    if ($LASTEXITCODE) { throw "Cannot inspect PE imports: $($taskPe.FullName)" }
    foreach ($taskLine in $taskDump) {
        if ($taskLine -cnotmatch '^\s*DLL Name:\s*(\S+)') { continue }
        $taskImport = $Matches[1]
        if ($taskImport -match '^(api-ms-|ext-ms-)' -or $taskKnown.Contains($taskImport) -or
            (Test-Path -LiteralPath (Join-Path $taskPe.DirectoryName $taskImport)) -or
            (Test-Path -LiteralPath (Join-Path "$env:SystemRoot/System32" $taskImport))) {
            continue
        }
        $taskDependency = Join-Path "$taskMsys/clang64/bin" $taskImport
        if (!(Test-Path -LiteralPath $taskDependency)) {
            throw "Missing dependency $taskImport imported by $($taskPe.Name)"
        }
        Copy-Item -LiteralPath $taskDependency -Destination $taskBundle
        [void]$taskKnown.Add($taskImport)
        $taskQueue.Enqueue((Get-Item -LiteralPath (Join-Path $taskBundle $taskImport)))
        ++$taskAdded
    }
}
Write-Output "Completed transitive runtime dependencies: $taskAdded DLLs added."
