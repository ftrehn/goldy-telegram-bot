# run_export.ps1 - run the catalog export to the bot by hand, over COM, and
# print the report the module returns.
#
# Calls gb_ExchangeWithBot.ExportCatalog() (names from names.txt) in the
# session of the conn.txt user - the same code the scheduled job runs, minus
# the event-log wrapper, so the report or the error text comes back here
# instead of the event log. Nothing else is needed: the module reads its five
# constants itself and talks to the receiver on its own.
#
# -Ping calls CheckConnection() instead: one GET /catalog/ping with the
# configured address and token, answer "HTTP <code>: <body>". Use it before
# the first export and whenever the export fails on the first batch - it tells
# the network problem apart from a data problem in seconds instead of minutes.
#
# The report goes to the console and to out\report.txt (UTF-8: the console of
# the 32-bit host mangles Cyrillic). Exit code 1 when the module raised.
#
# Disable the scheduled job before a manual run and enable it back after: two
# runs at once sweep each other's rows, because each finalization removes
# whatever carries the other run's batch_id. The module refuses to start while
# the job is already running, but it cannot notice a job that starts during
# this run - a COM session is not a background job to the platform (README,
# section on running by hand).
#
# Usage (32-bit PowerShell, see README):
#   run_export.ps1
#   run_export.ps1 -Ping
param(
  [switch]$Ping
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib1c.ps1')

$names = Read-Names (Join-Path $PSScriptRoot 'names.txt')
$method = if ($Ping) { $names['ping'] } else { $names['export'] }

$db = Connect1C (Join-Path $PSScriptRoot 'conn.txt')
$status = 0
$t0 = Get-Date
try {
  $mod = Get1C $db $names['module']
  $result = Call1C $mod $method @()
  $text = [string]$result
} catch {
  $text = 'ERROR: ' + (Describe-Error $_)
  $status = 1
}
$elapsed = [int]((Get-Date) - $t0).TotalSeconds
$text = $text.TrimEnd() + "`r`n" + '--- ' + $method + ' finished in ' + $elapsed + ' s, exit ' + $status + "`r`n"

Write-Utf8 (Join-Path (Get-OutDir) 'report.txt') $text
Write-Output $text
$mod = $null; $result = $null
$db = $null
Disconnect1C
exit $status
