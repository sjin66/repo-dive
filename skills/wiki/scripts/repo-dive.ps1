# Version-pinned Repo Dive runtime bootstrap for Windows x64.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Operation,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardedArguments
)
$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    [Console]::Error.WriteLine("repo-dive bootstrap: $Message")
    exit 1
}

$RuntimeInformation = [System.Runtime.InteropServices.RuntimeInformation]
$Windows = [System.Runtime.InteropServices.OSPlatform]::Windows
if (-not $RuntimeInformation::IsOSPlatform($Windows) -or $RuntimeInformation::OSArchitecture -ne "X64") {
    Fail "unsupported platform; supported targets are macOS ARM64, macOS x64, and Windows x64"
}
$Target = "windows-x64"
$MetadataPath = Join-Path $PSScriptRoot "../references/release.json"
try { $Release = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json }
catch { Fail "release metadata is missing or invalid" }
$Item = $Release.targets.$Target
if ($Release.schema_version -ne "1.0" -or $null -eq $Item -or $Release.tag -ne "v$($Release.version)") {
    Fail "release metadata is invalid"
}
if ($Release.version -notmatch '^[0-9A-Za-z](?:[0-9A-Za-z.-]*[0-9A-Za-z])?$' -or
    $Release.version.Contains("..") -or
    $Release.repository -ne "https://github.com/sjin66/repo-dive" -or
    $Item.archive -ne "repo-dive-v$($Release.version)-$Target.zip" -or
    $Item.archive_type -ne "zip" -or
    $Item.top_level -ne "repo-dive" -or
    $Item.executable -ne "repo-dive.exe") {
    Fail "release metadata contains an unsafe target entry"
}
$CacheRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Fail "LOCALAPPDATA is required" }
$CacheDirectory = Join-Path $CacheRoot "repo-dive/$($Release.version)/$Target"
$Runtime = Join-Path $CacheDirectory $Item.executable
$Marker = Join-Path $CacheDirectory ".complete"

if ($Operation -ne "--install") {
    if (-not (Test-Path -LiteralPath $Marker -PathType Leaf) -or -not (Test-Path -LiteralPath $Runtime -PathType Leaf)) {
        Fail "runtime $($Release.version) for $Target is not installed; obtain consent, then run this launcher with --install"
    }
    $Arguments = @()
    if ($Operation) { $Arguments += $Operation }
    if ($ForwardedArguments) { $Arguments += $ForwardedArguments }
    & $Runtime @Arguments
    exit $LASTEXITCODE
}
if ($ForwardedArguments.Count -gt 0) { Fail "--install does not accept CLI arguments" }
if ((Test-Path -LiteralPath $Marker) -and (Test-Path -LiteralPath $Runtime)) {
    [Console]::Error.WriteLine("repo-dive bootstrap: reused verified repo-dive $($Release.version) at $CacheDirectory")
    exit 0
}

$Parent = Split-Path -Parent $CacheDirectory
[System.IO.Directory]::CreateDirectory($Parent) | Out-Null
$LockDirectory = "$CacheDirectory.lock"
try { New-Item -ItemType Directory -Path $LockDirectory -ErrorAction Stop | Out-Null }
catch {
    if ((Test-Path -LiteralPath $Marker -PathType Leaf) -and (Test-Path -LiteralPath $Runtime -PathType Leaf)) {
        [Console]::Error.WriteLine("repo-dive bootstrap: reused verified repo-dive $($Release.version) at $CacheDirectory")
        exit 0
    }
    Fail "another installer is publishing this runtime; retry after it finishes"
}
if (Test-Path -LiteralPath $CacheDirectory) {
    Remove-Item -LiteralPath $LockDirectory -Force
    Fail "an incomplete cache already exists at $CacheDirectory; inspect and remove it before retrying"
}
$Work = Join-Path $Parent (".install." + [Guid]::NewGuid().ToString("N"))
[System.IO.Directory]::CreateDirectory($Work) | Out-Null
try {
    $BaseUrl = "$($Release.repository)/releases/download/$($Release.tag)"
    $ArchivePath = Join-Path $Work $Item.archive
    $ChecksumsPath = Join-Path $Work "SHA256SUMS"
    Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/SHA256SUMS" -OutFile $ChecksumsPath
    Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/$($Item.archive)" -OutFile $ArchivePath
    $EscapedName = [Regex]::Escape($Item.archive)
    $Matches = @(Get-Content -LiteralPath $ChecksumsPath | Where-Object { $_ -match "^([0-9A-Fa-f]{64})[ \t]+\*?$EscapedName$" })
    if ($Matches.Count -ne 1) { Fail "checksum manifest must contain exactly one valid archive entry" }
    $Expected = ([Regex]::Match($Matches[0], '^([0-9A-Fa-f]{64})')).Groups[1].Value.ToLowerInvariant()
    $Actual = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) { Fail "SHA-256 verification failed for $($Item.archive)" }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        if ($Zip.Entries.Count -eq 0) { Fail "archive is empty" }
        $Names = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($Entry in $Zip.Entries) {
            $Name = $Entry.FullName.Replace('\', '/')
            if ($Name.StartsWith('/') -or $Name.Contains(':') -or $Name -match '(^|/)\.\.(/|$)' -or -not ($Name -eq $Item.top_level -or $Name.StartsWith("$($Item.top_level)/"))) {
                Fail "archive contains an unsafe entry: $Name"
            }
            if (-not $Names.Add($Name.TrimEnd('/'))) { Fail "archive contains a duplicate entry: $Name" }
            $UnixType = ($Entry.ExternalAttributes -shr 16) -band 0xF000
            if ($UnixType -ne 0 -and $UnixType -ne 0x4000 -and $UnixType -ne 0x8000) {
                Fail "archive contains a link or special entry"
            }
        }
    } finally { $Zip.Dispose() }

    $Unpack = Join-Path $Work "unpack"
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $Unpack)
    $Staged = Join-Path $Unpack $Item.top_level
    $StagedRuntime = Join-Path $Staged $Item.executable
    if (-not (Test-Path -LiteralPath $StagedRuntime -PathType Leaf)) { Fail "bundled executable is missing" }
    & $StagedRuntime --version *> $null
    if ($LASTEXITCODE -ne 0) { Fail "bundled executable smoke test failed" }
    Set-Content -LiteralPath (Join-Path $Staged ".complete") -Value "$Actual  $($Item.archive)" -Encoding ASCII
    try { [System.IO.Directory]::Move($Staged, $CacheDirectory) }
    catch {
        if (-not ((Test-Path -LiteralPath $Marker) -and (Test-Path -LiteralPath $Runtime))) {
            Fail "could not publish the verified runtime atomically"
        }
    }
    [Console]::Error.WriteLine("repo-dive bootstrap: installed repo-dive $($Release.version) at $CacheDirectory")
} finally {
    if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
    if (Test-Path -LiteralPath $LockDirectory) { Remove-Item -LiteralPath $LockDirectory -Force }
}
