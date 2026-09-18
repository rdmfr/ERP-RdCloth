$ErrorActionPreference = "Stop"
docker compose down
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to stop NexaBiz."
}
