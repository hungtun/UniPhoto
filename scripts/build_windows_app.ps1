<#
.SYNOPSIS
    UniPhoto — Slim Standalone Windows 10/11 (.exe NSIS & .msi) One-Command Builder

.DESCRIPTION
    1. Verifies/creates .venv\Scripts\python.exe, checks Node.js (^20.19.0 || >=22.12.0) & Rust/Cargo,
       and installs slim runtime dependencies + PyInstaller (zero torch/scipy/matplotlib).
    2. Prepares offline bundled AI models in build\bundled-models\ (mobilenet_v2.onnx + face_landmarker.task).
    3. Builds uniphoto_backend.spec via PyInstaller --onedir -> build\pyinstaller\uniphoto-backend\uniphoto-backend.exe,
       runs --self-test, and smoke-tests HTTP GET /api/v1/health on an ephemeral loopback port.
    4. Runs frontend build (tsc && vite build) and Tauri v2 Windows installer build (--bundles nsis,msi)
       with src-tauri/tauri.windows.bundle.json.
    5. Prints the exact generated NSIS (.exe) and WiX (.msi) installer paths and sizes.
#>

[CmdletBinding()]
param(
    [switch]$RebuildBackend,
    [switch]$SkipInstallDeps,
    [switch]$CheckEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvDir = Join-Path $RootDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$BuildDir = Join-Path $RootDir "build"
$ModelsOutDir = Join-Path $BuildDir "bundled-models"
$PyiDistDir = Join-Path $BuildDir "pyinstaller"
$PyiWorkDir = Join-Path $BuildDir "pyinstaller-work"
$PyiCacheDir = Join-Path $BuildDir "pyinstaller-cache"
$BackendDir = Join-Path $PyiDistDir "uniphoto-backend"
$BackendBin = Join-Path $BackendDir "uniphoto-backend.exe"
$SpecFile = Join-Path $RootDir "uniphoto_backend.spec"
$RthStubFile = Join-Path $RootDir "scripts\pyi_rth_stub_unused.py"
$FrontendDir = Join-Path $RootDir "frontend"
$WinBundleRelConfig = "src-tauri/tauri.windows.bundle.json"
$WinBundleAbsConfig = Join-Path $FrontendDir "src-tauri\tauri.windows.bundle.json"

$SlimPackages = @(
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "SQLAlchemy",
    "pillow",
    "pillow_heif",
    "numpy",
    "opencv-python",
    "mediapipe",
    "pyinstaller"
)

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$StepName
    )
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE ($Exe $($Arguments -join ' '))"
    }
}

function Test-CompatibleNode {
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        return $false
    }
    $verRaw = (& node -v 2>$null)
    if (-not $verRaw) {
        return $false
    }
    $verClean = $verRaw.Trim().TrimStart("v")
    if ($verClean -notmatch '^(\d+)\.(\d+)\.(\d+)') {
        return $false
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    return (($major -gt 22) -or ($major -eq 22 -and $minor -ge 12) -or ($major -eq 20 -and $minor -ge 19))
}

function Format-SizeMB {
    param([Parameter(Mandatory = $true)][long]$Bytes)
    return "{0:N1} MB" -f ($Bytes / 1MB)
}

Write-Host "==> [1/5] Checking Windows build prerequisites (.venv Python, Node/npm, Rust/Cargo)..." -ForegroundColor Cyan

$cargoHomeBin = Join-Path $env:USERPROFILE ".cargo\bin"
if ((-not (Get-Command cargo -ErrorAction SilentlyContinue)) -and (Test-Path (Join-Path $cargoHomeBin "cargo.exe"))) {
    $env:PATH = "$cargoHomeBin;$env:PATH"
}

foreach ($tool in @("node", "npm", "cargo")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Required command '$tool' is not installed or not in PATH."
    }
}

if (-not (Test-CompatibleNode)) {
    $curNodeVer = (& node -v 2>$null)
    throw "Node.js version '$curNodeVer' does not satisfy Vite 8 (^20.19.0 || >=22.12.0). Please install Node.js 22 LTS."
}
Write-Host "    Using Node.js $(& node -v), npm $(& npm -v), $(& cargo --version)"

if (-not (Test-Path $VenvPython)) {
    Write-Host "    Creating Python virtual environment at $VenvDir..."
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Invoke-NativeChecked -Exe "python" -Arguments @("-m", "venv", $VenvDir) -StepName "Create .venv"
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-NativeChecked -Exe "py" -Arguments @("-3.12", "-m", "venv", $VenvDir) -StepName "Create .venv via py -3.12"
    }
    else {
        throw "Python 3.12+ was not found in PATH and $VenvPython does not exist."
    }
}

$needPipInstall = $false
if (-not $SkipInstallDeps) {
    & $VenvPython -c "import fastapi, uvicorn, pydantic, pydantic_settings, dotenv, sqlalchemy, PIL, pillow_heif, numpy, cv2, mediapipe, PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $needPipInstall = $true
    }
}

if ($needPipInstall) {
    Write-Host "    Installing slim runtime dependencies + PyInstaller into .venv..."
    Invoke-NativeChecked -Exe $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -StepName "Upgrade pip"
    Invoke-NativeChecked -Exe $VenvPython -Arguments (@("-m", "pip", "install") + $SlimPackages) -StepName "Install slim runtime packages"
}
else {
    Write-Host "    Verified slim Python runtime dependencies + PyInstaller in $VenvPython"
}

if ($CheckEnv) {
    Write-Host "    Environment check passed!" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "    Installing frontend npm dependencies..."
    if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
        Invoke-NativeChecked -Exe "npm" -Arguments @("--prefix", $FrontendDir, "ci") -StepName "npm ci (frontend)"
    }
    else {
        Invoke-NativeChecked -Exe "npm" -Arguments @("--prefix", $FrontendDir, "install") -StepName "npm install (frontend)"
    }
}

Write-Host "==> [2/5] Preparing offline bundled AI models in $ModelsOutDir..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $ModelsOutDir | Out-Null
$stalePth = Join-Path $ModelsOutDir "mobilenet_v2.pth"
if (Test-Path $stalePth) {
    Remove-Item -Force $stalePth
}

$MobilenetSrc = Join-Path $RootDir "data\models\mobilenet_v2.onnx"
$MobilenetDst = Join-Path $ModelsOutDir "mobilenet_v2.onnx"
if ((Test-Path $MobilenetSrc) -and ((Get-Item $MobilenetSrc).Length -gt 1000000)) {
    Copy-Item -Force -Path $MobilenetSrc -Destination $MobilenetDst
    Write-Host "    Copied mobilenet_v2.onnx ($(Format-SizeMB (Get-Item $MobilenetDst).Length))"
}
elseif ((Test-Path $MobilenetDst) -and ((Get-Item $MobilenetDst).Length -gt 1000000)) {
    Write-Host "    Reusing existing $MobilenetDst ($(Format-SizeMB (Get-Item $MobilenetDst).Length))"
}
else {
    throw "Required offline model 'data\models\mobilenet_v2.onnx' (>1 MB) not found at $MobilenetSrc."
}

$FaceTaskSrc = Join-Path $RootDir "data\models\face_landmarker.task"
$FaceTaskDst = Join-Path $ModelsOutDir "face_landmarker.task"
$FaceTaskUrl = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if ((Test-Path $FaceTaskSrc) -and ((Get-Item $FaceTaskSrc).Length -gt 10000)) {
    Copy-Item -Force -Path $FaceTaskSrc -Destination $FaceTaskDst
    Write-Host "    Copied face_landmarker.task ($(Format-SizeMB (Get-Item $FaceTaskDst).Length))"
}
elseif ((Test-Path $FaceTaskDst) -and ((Get-Item $FaceTaskDst).Length -gt 10000)) {
    Write-Host "    Reusing existing $FaceTaskDst ($(Format-SizeMB (Get-Item $FaceTaskDst).Length))"
}
else {
    Write-Host "    Downloading face_landmarker.task from Google MediaPipe storage..."
    Invoke-WebRequest -Uri $FaceTaskUrl -OutFile $FaceTaskDst -UseBasicParsing
    if ((-not (Test-Path $FaceTaskDst)) -or ((Get-Item $FaceTaskDst).Length -le 10000)) {
        throw "Downloaded face_landmarker.task at $FaceTaskDst is missing or incomplete."
    }
    Write-Host "    Downloaded face_landmarker.task ($(Format-SizeMB (Get-Item $FaceTaskDst).Length))"
}

Write-Host "==> [3/5] Building slim standalone Windows backend via PyInstaller (--onedir)..." -ForegroundColor Cyan
$needPyiBuild = $true
if ($RebuildBackend) {
    Write-Host "    -RebuildBackend specified; forcing clean PyInstaller build..."
}
elseif (Test-Path $BackendBin) {
    $binTime = (Get-Item $BackendBin).LastWriteTimeUtc
    $watchFiles = @(
        (Get-Item (Join-Path $RootDir "run.py")),
        (Get-Item $SpecFile),
        (Get-Item $RthStubFile)
    ) + @(Get-ChildItem -Path (Join-Path $RootDir "app") -Filter "*.py" -Recurse)

    $newerSource = $watchFiles | Where-Object { $_.LastWriteTimeUtc -gt $binTime } | Select-Object -First 1
    if (-not $newerSource) {
        $needPyiBuild = $false
    }
}

$MplTempDir = Join-Path ([System.IO.Path]::GetTempPath()) "uniphoto-mpl"
New-Item -ItemType Directory -Force -Path $MplTempDir | Out-Null

if ($needPyiBuild) {
    if (Test-Path $BackendDir) {
        Remove-Item -Recurse -Force $BackendDir
    }
    if (Test-Path $PyiWorkDir) {
        Remove-Item -Recurse -Force $PyiWorkDir
    }

    $prevMpl = $env:MPLCONFIGDIR
    $prevPyiCfg = $env:PYINSTALLER_CONFIG_DIR
    try {
        $env:MPLCONFIGDIR = $MplTempDir
        $env:PYINSTALLER_CONFIG_DIR = $PyiCacheDir
        Invoke-NativeChecked -Exe $VenvPython -Arguments @(
            "-m", "PyInstaller",
            "--distpath", $PyiDistDir,
            "--workpath", $PyiWorkDir,
            "--noconfirm",
            $SpecFile
        ) -StepName "PyInstaller build"
    }
    finally {
        $env:MPLCONFIGDIR = $prevMpl
        $env:PYINSTALLER_CONFIG_DIR = $prevPyiCfg
    }
}
else {
    Write-Host "    Reusing up-to-date PyInstaller bundle at $BackendBin (pass -RebuildBackend to force)"
}

if (-not (Test-Path $BackendBin)) {
    throw "Expected PyInstaller binary was not generated at $BackendBin"
}

$sidecarBytes = (Get-ChildItem -Path $BackendDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "    PyInstaller sidecar size: $(Format-SizeMB $sidecarBytes)"

Write-Host "    Verifying packaged backend imports & offline AI models (--self-test)..."
$SmokeDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("uniphoto-win-smoke-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $SmokeDataDir | Out-Null

$savedEnv = @{
    HOST                = $env:HOST
    PORT                = $env:PORT
    DEBUG               = $env:DEBUG
    UNIPHOTO_PACKAGED   = $env:UNIPHOTO_PACKAGED
    UNIPHOTO_DATA_DIR   = $env:UNIPHOTO_DATA_DIR
    UNIPHOTO_MODELS_DIR = $env:UNIPHOTO_MODELS_DIR
    MPLCONFIGDIR        = $env:MPLCONFIGDIR
    PYTHONUNBUFFERED    = $env:PYTHONUNBUFFERED
}

try {
    $env:HOST = "127.0.0.1"
    $env:PORT = "8000"
    $env:DEBUG = "False"
    $env:UNIPHOTO_PACKAGED = "1"
    $env:UNIPHOTO_DATA_DIR = $SmokeDataDir
    $env:UNIPHOTO_MODELS_DIR = $ModelsOutDir
    $env:MPLCONFIGDIR = $MplTempDir
    $env:PYTHONUNBUFFERED = "1"

    $selfTestOut = (& $BackendBin --self-test 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or ($selfTestOut -notmatch "SELF_TEST_OK")) {
        throw "Packaged uniphoto-backend.exe --self-test failed:`n$selfTestOut"
    }
    Write-Host "    Self-test passed ($((($selfTestOut -split "`r?`n") | Where-Object { $_ -match 'APP_IMPORT_OK|SELF_TEST_OK' }) -join ' '))"

    Write-Host "    Smoke-testing packaged backend HTTP server on an ephemeral port..."
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $smokePort = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()

    $env:PORT = "$smokePort"
    $smokeOutLog = Join-Path ([System.IO.Path]::GetTempPath()) ("uniphoto-smoke-out-" + [System.Guid]::NewGuid().ToString("N") + ".log")
    $smokeErrLog = Join-Path ([System.IO.Path]::GetTempPath()) ("uniphoto-smoke-err-" + [System.Guid]::NewGuid().ToString("N") + ".log")
    $smokeProc = $null

    try {
        $smokeProc = Start-Process -FilePath $BackendBin `
            -WorkingDirectory $SmokeDataDir `
            -RedirectStandardOutput $smokeOutLog `
            -RedirectStandardError $smokeErrLog `
            -WindowStyle Hidden `
            -PassThru

        $healthUrl = "http://127.0.0.1:$smokePort/api/v1/health"
        $smokeOk = $false
        for ($i = 0; $i -lt 180; $i++) {
            if ($smokeProc.HasExited) {
                $outTxt = if (Test-Path $smokeOutLog) { Get-Content $smokeOutLog -Raw } else { "" }
                $errTxt = if (Test-Path $smokeErrLog) { Get-Content $smokeErrLog -Raw } else { "" }
                throw "uniphoto-backend.exe exited prematurely (code $($smokeProc.ExitCode)) during HTTP smoke test.`nSTDOUT:`n$outTxt`nSTDERR:`n$errTxt"
            }
            try {
                $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
                if ($resp -and $resp.status -eq "ok") {
                    $smokeOk = $true
                    break
                }
            }
            catch {
                Start-Sleep -Milliseconds 500
            }
        }

        if (-not $smokeOk) {
            $outTxt = if (Test-Path $smokeOutLog) { Get-Content $smokeOutLog -Raw } else { "" }
            $errTxt = if (Test-Path $smokeErrLog) { Get-Content $smokeErrLog -Raw } else { "" }
            throw "Packaged uniphoto-backend.exe did not respond on $healthUrl within 90s.`nSTDOUT:`n$outTxt`nSTDERR:`n$errTxt"
        }
        Write-Host "    HTTP smoke test passed (GET /api/v1/health -> 200 OK on port $smokePort)!"
    }
    finally {
        if ($smokeProc -and (-not $smokeProc.HasExited)) {
            Stop-Process -Id $smokeProc.Id -Force -ErrorAction SilentlyContinue
            $null = $smokeProc.WaitForExit(5000)
        }
        Start-Sleep -Milliseconds 300
        Remove-Item -Force $smokeOutLog, $smokeErrLog -ErrorAction SilentlyContinue
    }
}
finally {
    foreach ($kv in $savedEnv.GetEnumerator()) {
        if ($null -eq $kv.Value) {
            Remove-Item "Env:\$($kv.Key)" -ErrorAction SilentlyContinue
        }
        else {
            Set-Item "Env:\$($kv.Key)" -Value $kv.Value
        }
    }
    Remove-Item -Recurse -Force $SmokeDataDir -ErrorAction SilentlyContinue
}

Write-Host "==> [4/5] Building frontend & Tauri Windows installers (NSIS .exe + WiX .msi)..." -ForegroundColor Cyan
if (-not (Test-Path $WinBundleAbsConfig)) {
    throw "Windows Tauri bundle config not found at $WinBundleAbsConfig"
}

Write-Host "    Building frontend assets (tsc && vite build)..."
Invoke-NativeChecked -Exe "npm" -Arguments @("--prefix", $FrontendDir, "run", "build") -StepName "Frontend build"

Write-Host "    Packaging Tauri Windows installers (--bundles nsis,msi --config $WinBundleRelConfig)..."
Invoke-NativeChecked -Exe "npm" -Arguments @(
    "--prefix", $FrontendDir,
    "run", "tauri", "build", "--",
    "--bundles", "nsis,msi",
    "--config", $WinBundleRelConfig
) -StepName "Tauri Windows build"

Write-Host "==> [5/5] Verifying generated Windows installer artifacts..." -ForegroundColor Cyan
$BundleRoot = Join-Path $FrontendDir "src-tauri\target\release\bundle"
$NsisInstallers = @(Get-ChildItem -Path (Join-Path $BundleRoot "nsis") -Filter "*.exe" -File -ErrorAction SilentlyContinue)
$MsiInstallers = @(Get-ChildItem -Path (Join-Path $BundleRoot "msi") -Filter "*.msi" -File -ErrorAction SilentlyContinue)

if (($NsisInstallers.Count -eq 0) -and ($MsiInstallers.Count -eq 0)) {
    throw "No Windows installer artifacts (.exe or .msi) were found under $BundleRoot"
}

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "UniPhoto Windows 10/11 Standalone Build Complete!" -ForegroundColor Green
foreach ($exe in $NsisInstallers) {
    Write-Host "  NSIS Setup (.exe) : $($exe.FullName) ($(Format-SizeMB $exe.Length))"
}
foreach ($msi in $MsiInstallers) {
    Write-Host "  WiX Package (.msi): $($msi.FullName) ($(Format-SizeMB $msi.Length))"
}
Write-Host "==============================================================================" -ForegroundColor Green
