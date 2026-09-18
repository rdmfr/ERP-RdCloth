param(
  [Parameter(Mandatory=$true)][string]$Backup,
  [string]$MongoUrl = $env:MONGO_URL,
  [string]$Database = $(if ($env:DB_NAME) { $env:DB_NAME } else { "nexabiz" }),
  [string]$Attachments = $(if ($env:ATTACHMENTS_DIR) { $env:ATTACHMENTS_DIR } else { ".\data\attachments" })
)
if (-not $MongoUrl) { throw "Set MONGO_URL before running restore." }
$mongoDump = Join-Path $Backup "mongo\$Database"
if (-not (Test-Path $mongoDump)) { throw "Backup database folder not found: $mongoDump" }
mongorestore --uri $MongoUrl --db $Database --drop $mongoDump
$savedAttachments = Join-Path $Backup "attachments"
if (Test-Path $savedAttachments) { New-Item -ItemType Directory -Force -Path $Attachments | Out-Null; Copy-Item "$savedAttachments\*" $Attachments -Recurse -Force }
Write-Output "Restore completed from $Backup"
