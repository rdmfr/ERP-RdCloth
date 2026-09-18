param(
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required. Install Docker Desktop or Docker Engine first."
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item ".env.docker.example" $EnvFile
    Write-Host "Created $EnvFile. Update JWT_SECRET and OWNER_PASSWORD, then run this script again."
    exit 0
}

docker compose --env-file $EnvFile up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start NexaBiz."
}

Write-Host "NexaBiz is running at http://localhost (or the configured PORT)."
