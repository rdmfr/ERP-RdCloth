param(
  [string]$MongoUrl = $env:MONGO_URL,
  [string]$Database = $(if ($env:DB_NAME) { $env:DB_NAME } else { "nexabiz" }),
  [string]$Attachments = $(if ($env:ATTACHMENTS_DIR) { $env:ATTACHMENTS_DIR } else { ".\data\attachments" }),
  [string]$Output = ".\backups"
)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $Output $stamp
New-Item -ItemType Directory -Force -Path $target | Out-Null
if (-not $MongoUrl) { throw "Set MONGO_URL before running backup." }
mongodump --uri $MongoUrl --db $Database --out (Join-Path $target "mongo")
if (Test-Path $Attachments) { Copy-Item $Attachments (Join-Path $target "attachments") -Recurse }
Write-Output "Backup created at $target"
