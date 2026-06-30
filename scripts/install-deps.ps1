Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$VenvDir = Join-Path $RootDir ".venv"
$PythonBin = $null

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--python" {
            if ($i + 1 -ge $args.Count) {
                throw "Missing value for --python"
            }
            $PythonBin = $args[$i + 1]
            $i++
        }
        default {
            throw "Unknown argument: $($args[$i])"
        }
    }
}

function Resolve-PythonBin {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        $command = Get-Command $RequestedPython -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
        if (Test-Path $RequestedPython) {
            return (Resolve-Path $RequestedPython).Path
        }
        throw "Python not found for --python: $RequestedPython"
    }

    foreach ($candidate in @("py.exe", "python.exe")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "Python not found. Install Python 3.10+ first."
}

function Test-PythonVersion {
    param([string]$PythonPath)

    $versionArgs = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)")
    if ($PythonPath -like "*py.exe") {
        $versionArgs = @("-3") + $versionArgs
    }
    & $PythonPath @versionArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10+ is required."
    }
}

function New-Venv {
    param([string]$PythonPath)

    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        Write-Output "Using uv to create/update .venv"
        & $uvCommand.Source "venv" $VenvDir "--python" $PythonPath
        return
    }

    Write-Output "Using stdlib venv to create/update .venv"
    $venvArgs = @("-m", "venv", $VenvDir)
    if ($PythonPath -like "*py.exe") {
        $venvArgs = @("-3") + $venvArgs
    }
    & $PythonPath @venvArgs
}

function Install-Packages {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if ($uvCommand) {
        Write-Output "Installing Python packages with uv"
        & $uvCommand.Source "pip" "install" "--python" $venvPython "-r" (Join-Path $RootDir "requirements.txt")
        return
    }

    Write-Output "Installing Python packages with pip"
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $RootDir "requirements.txt")
}

function Verify-RuntimeImports {
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    & $venvPython -c "import fastapi, uvicorn; print('Python runtime deps OK:', fastapi.__name__, uvicorn.__name__)"
}

$ResolvedPython = Resolve-PythonBin $PythonBin
Test-PythonVersion $ResolvedPython
Set-Location $RootDir
New-Venv $ResolvedPython
Install-Packages
Verify-RuntimeImports

@"

Dependency install complete.

Next steps:
1. .\.venv\Scripts\Activate.ps1
2. .\scripts\start.ps1
"@ | Write-Output
