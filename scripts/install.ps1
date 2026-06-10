$ErrorActionPreference = "Stop"

$EnvName = "skin_microbiome"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "==> Creating Conda environment: $EnvName"
$existing = conda env list | Select-String "^${EnvName} "
if ($existing) {
    Write-Host "    Environment '$EnvName' already exists, skipping creation."
} else {
    conda create -n $EnvName python=3.10 -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create Conda environment." -ForegroundColor Red
        exit 1
    }
}

Write-Host "==> Activating environment and installing dependencies"
conda activate $EnvName
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to activate Conda environment." -ForegroundColor Red
    exit 1
}
python -m pip install --upgrade pip
pip install -r "$ProjectDir\requirements.txt"
pip install -e "$ProjectDir"

Write-Host ""
Write-Host "==> Checking external tools in PATH"

function Check-Tool {
    param([string]$Name)
    $found = Get-Command $Name -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "    [OK] $Name found: $($found.Source)"
    } else {
        Write-Host "    [WARN] $Name not found in PATH. Please install it manually if needed."
    }
}

Check-Tool "fastq-dump"       # sra-tools
Check-Tool "enaBrowserTools"  # enaBrowserTools (enaDataGet / enaGroupGet)

Write-Host ""
Write-Host "==> Installation complete."
Write-Host "Activate with: conda activate $EnvName"
Write-Host "Run: skinmicrobiome"
