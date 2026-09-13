# dump_batches.ps1 - build the catalog batches without sending them: every
# batch and every finalization lands as a JSON file in a folder.
#
# Calls gb_ExchangeWithBot.ExportCatalogToFiles(folder) (names from
# names.txt): the same walk over the base as the real export, with the HTTP
# sender replaced by a file writer. Files are named <NNN>-<scope>[-<id>].json
# and <NNN>-finalize-<scope>.json in the order they would have been sent.
#
# When to use it: to look at what 1C would send before pointing it at the
# bot; to feed one batch to the receiver by hand with curl and see its answer;
# to compare a batch with docs/design/catalog-snapshot.example.json when the
# receiver answers 400. The receiver's own dry run is `just seed <file>`.
#
# The numbering restarts at 001 on every run and the module never deletes
# anything, so a shorter run would leave the tail of a longer one behind and
# the listing below would report yesterday's batches as today's. The default
# folder is ours: its *.json are removed before the module runs. A folder
# given with -OutDir is not ours, so it must be free of *.json or the script
# refuses to run rather than delete somebody else's files.
#
# Usage (32-bit PowerShell, see README):
#   dump_batches.ps1                     # into scripts\out\batches
#   dump_batches.ps1 -OutDir D:\tmp\gb   # elsewhere (created when missing)
param(
  [string]$OutDir = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib1c.ps1')

$names = Read-Names (Join-Path $PSScriptRoot 'names.txt')
if ($OutDir -eq '') { $OutDir = Join-Path (Get-OutDir) 'batches' }
if (-not (Test-Path $OutDir)) { [void](New-Item -ItemType Directory $OutDir) }
# 1C needs an absolute path: its working directory is not this folder.
$OutDir = (Resolve-Path $OutDir).Path

$stale = @(Get-ChildItem -Path $OutDir -Filter '*.json' -File)
if ($stale.Count -gt 0) {
  if ($PSBoundParameters.ContainsKey('OutDir')) {
    throw ('Folder ' + $OutDir + ' already holds ' + $stale.Count + ' *.json file(s); use an empty folder')
  }
  $stale | Remove-Item -Force
}

$db = Connect1C (Join-Path $PSScriptRoot 'conn.txt')
$status = 0
$t0 = Get-Date
try {
  $mod = Get1C $db $names['module']
  $result = Call1C $mod $names['export_files'] @($OutDir)
  $text = [string]$result
} catch {
  $text = 'ERROR: ' + (Describe-Error $_)
  $status = 1
}
$elapsed = [int]((Get-Date) - $t0).TotalSeconds
$files = @(Get-ChildItem -Path $OutDir -Filter '*.json' -File | Sort-Object Name)
$text = $text.TrimEnd() + "`r`n" + '--- ' + $files.Count + ' file(s) in ' + $OutDir +
        ', finished in ' + $elapsed + ' s, exit ' + $status + "`r`n"
foreach ($f in $files) { $text += ('  ' + $f.Name + "`t" + $f.Length + "`r`n") }

Write-Utf8 (Join-Path (Get-OutDir) 'report-files.txt') $text
Write-Output $text
$mod = $null; $result = $null
$db = $null
Disconnect1C
exit $status
