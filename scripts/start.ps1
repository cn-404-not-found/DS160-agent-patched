Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$DryRun = $false
$RemoteDebuggingPort = 9222
$ServerPort = 8765
$CeacUrl = "https://ceac.state.gov/genniv/"
$ProfileDir = Join-Path $RootDir ".visible-browser-profile"
$LogDir = Join-Path $RootDir ".logs"
$ServerLog = Join-Path $LogDir "server.log"
$PowerShellHost = (Get-Process -Id $PID).Path

foreach ($arg in $args) {
    switch ($arg) {
        "--dry-run" { $DryRun = $true }
        default { throw "Unknown argument: $arg" }
    }
}

function Get-FileUrl {
    param([string]$Path)
    return ([System.Uri] (Resolve-Path $Path)).AbsoluteUri
}

function Test-ServerUp {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$ServerPort/status" -UseBasicParsing | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Resolve-PythonBin {
    $venvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        return $pyCommand.Source
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python not found. Run scripts\install-deps.ps1 first."
}

function Resolve-ChromePath {
    $candidates = @(
        "$Env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${Env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$Env:LocalAppData\Google\Chrome\Application\chrome.exe",
        "$Env:ProgramFiles\Chromium\Application\chrome.exe",
        "${Env:ProgramFiles(x86)}\Chromium\Application\chrome.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $command = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "Google Chrome/Chromium not found. Install Chrome for DS-160 autofill."
}

function Start-ChromeDebug {
    $chromePath = "chrome.exe"
    if (-not $DryRun) {
        $chromePath = Resolve-ChromePath
    }

    $chromeArgs = @(
        "--remote-debugging-port=$RemoteDebuggingPort",
        "--user-data-dir=$ProfileDir",
        "--no-first-run",
        "--disable-extensions",
        $CeacUrl
    )

    if ($DryRun) {
        Write-Output "DRY RUN: chrome debug launch"
        Write-Output ('"{0}" {1}' -f $chromePath, ($chromeArgs -join " "))
        return
    }

    New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
    Start-Process -FilePath $chromePath -ArgumentList $chromeArgs | Out-Null
    Write-Output "Chrome debug window launched on port $RemoteDebuggingPort."
}

function Start-Server {
    $pythonBin = "python.exe"
    $pythonArgs = @("-m", "visa_agent.server")
    if (-not $DryRun) {
        $pythonBin = Resolve-PythonBin
        if ($pythonBin -like "*py.exe") {
            $pythonArgs = @("-3", "-m", "visa_agent.server")
        }
    }

    if ($DryRun) {
        Write-Output "DRY RUN: server launch"
        Write-Output ('set PYTHONPATH={0}\src && "{1}" {2}' -f $RootDir, $pythonBin, ($pythonArgs -join " "))
        return
    }

    if (Test-ServerUp) {
        Write-Output "FastAPI server is already running on http://127.0.0.1:$ServerPort"
        return
    }

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $escapedRootDir = $RootDir.Replace("'", "''")
    $escapedPythonPath = (Join-Path $RootDir "src").Replace("'", "''")
    $escapedPythonBin = $pythonBin.Replace("'", "''")
    $escapedServerLog = $ServerLog.Replace("'", "''")
    $pythonArgsLiteral = ($pythonArgs | ForEach-Object { "'{0}'" -f ($_.Replace("'", "''")) }) -join ", "
    $serverCommand = "& { Set-Location '$escapedRootDir'; `$env:PYTHONPATH = '$escapedPythonPath'; & '$escapedPythonBin' @($pythonArgsLiteral) *> '$escapedServerLog' }"

    $serverProcess = Start-Process `
        -FilePath $PowerShellHost `
        -ArgumentList @("-NoProfile", "-Command", $serverCommand) `
        -WorkingDirectory $RootDir `
        -PassThru

    Write-Output "Starting FastAPI server (pid $($serverProcess.Id)), log: $ServerLog"

    for ($i = 0; $i -lt 15; $i++) {
        if (Test-ServerUp) {
            return
        }
        Start-Sleep -Seconds 1
    }

    Write-Error "FastAPI server did not become ready. Recent log output:`n$((Get-Content -Path $ServerLog -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine)"
}

$LandingUrl = "http://127.0.0.1:${ServerPort}"

if ($DryRun) {
    Start-ChromeDebug
    Start-Server
    Write-Output "DRY RUN: open landing page $LandingUrl"
    exit 0
}

Start-ChromeDebug
Start-Server
Start-Sleep -Seconds 2
Start-Process $LandingUrl | Out-Null

@"
Windows startup complete.

  DS-160 visa helper: $LandingUrl
  FastAPI service:     http://127.0.0.1:$ServerPort
  Chrome CDP:          http://127.0.0.1:$RemoteDebuggingPort/json/version
"@ | Write-Output
