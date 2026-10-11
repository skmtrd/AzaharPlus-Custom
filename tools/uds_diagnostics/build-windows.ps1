param(
    [string]$MsysRoot = (Join-Path $PSScriptRoot '../../../tools/msys64'),
    [string]$BuildDirectory = 'build-uds',
    [int]$Jobs = 6,
    [switch]$SkipConfigure
)
$ErrorActionPreference = 'Stop'
$taskRepo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskMsys = [IO.Path]::GetFullPath($MsysRoot)
$taskBuild = Join-Path $taskRepo $BuildDirectory
$taskCmake = Join-Path $taskMsys 'clang64/bin/cmake.exe'
if (!(Test-Path -LiteralPath $taskCmake)) {
    throw 'Install the MSYS2 CLANG64 dependencies listed in README.md first.'
}
$env:PATH = "$taskMsys\clang64\bin;$taskMsys\usr\bin;$env:PATH"
if (!$SkipConfigure) {
    & $taskCmake -S $taskRepo -B $taskBuild -G Ninja `
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ `
        '-DCMAKE_POLICY_VERSION_MINIMUM=3.5' -DENABLE_LTO=OFF `
        -DENABLE_FFMPEG=OFF -DENABLE_TESTS=OFF -DUSE_SYSTEM_LIBUSB=OFF `
        -DENABLE_QT_TRANSLATION=ON -DCITRA_WARNINGS_AS_ERRORS=OFF
    if ($LASTEXITCODE) { throw "CMake configure failed ($LASTEXITCODE)" }
}
& $taskCmake --build $taskBuild --parallel $Jobs
if ($LASTEXITCODE) { throw "Compilation failed ($LASTEXITCODE)" }
& $taskCmake --build $taskBuild --target bundle
if ($LASTEXITCODE) { throw "Bundling failed ($LASTEXITCODE)" }
Write-Output "Windows bundle: $taskBuild/bundle"
