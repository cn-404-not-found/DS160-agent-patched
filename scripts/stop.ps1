Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$DryRun = $false
$ServerPort = 8765
$RemoteDebuggingPort = 9222
$ProfileDir = Join-Path $RootDir ".visible-browser-profile"

foreach ($arg in $args) {
    switch ($arg) {
        "--dry-run" { $DryRun = $true }
        default { throw "Unknown argument: $arg" }
    }
}

function Get-ServerPids {
    $connections = Get-NetTCPConnection -LocalPort $ServerPort -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        return @()
    }
    return $connections | Select-Object -ExpandProperty OwningProcess -Unique
}

function Get-ChromePids {
    $escapedProfile = [Regex]::Escape($ProfileDir)
    $escapedPort = [Regex]::Escape("--remote-debugging-port=$RemoteDebuggingPort")
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue
    if (-not $processes) {
        return @()
    }
    return $processes |
        Where-Object { $_.CommandLine -match $escapedPort -and $_.CommandLine -match $escapedProfile } |
        Select-Object -ExpandProperty ProcessId -Unique
}

if ($DryRun) {
    Write-Output "DRY RUN: scripts/stop.ps1"
    Write-Output "Would stop FastAPI listener on 127.0.0.1:$ServerPort"
    Write-Output "Would stop Chrome debug processes matching --remote-debugging-port=$RemoteDebuggingPort and profile $ProfileDir"
    exit 0
}

$serverPids = @(Get-ServerPids)
if ($serverPids.Count -gt 0) {
    $serverPids | ForEach-Object { Stop-Process -Id $_ -Force }
    Write-Output "Stopped FastAPI listener on port $ServerPort: $($serverPids -join ', ')"
} else {
    Write-Output "No FastAPI listener found on port $ServerPort."
}

$chromePids = @(Get-ChromePids)
if ($chromePids.Count -gt 0) {
    $chromePids | ForEach-Object { Stop-Process -Id $_ -Force }
    Write-Output "Stopped Chrome debug processes: $($chromePids -join ', ')"
} else {
    Write-Output "No Chrome debug process found for profile $ProfileDir."
}
