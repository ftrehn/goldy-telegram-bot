# set_constants.ps1 - write the five gb_* constants of the bot extension from
# settings.json over COM, then read them back.
#
# Why a script: the extension ships no form for its constants, so in the
# client they are edited through "All functions - Constants", one at a time,
# and the token is typed by hand into a password field. A JSON file next to
# the scripts is repeatable and can be diffed against .env of the receiver.
#
# settings.json (copy settings.json.example) maps a constant name to its
# value; the keys are the Cyrillic constant names, which is why the names are
# not in this ASCII source. A value may be a JSON array of strings - it is
# joined with ", " (handy for the list of price types).
#
# Usage (32-bit PowerShell, see README):
#   set_constants.ps1                       # scripts\settings.json
#   set_constants.ps1 -Settings other.json
param(
  [string]$Settings = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib1c.ps1')

if ($Settings -eq '') { $Settings = Join-Path $PSScriptRoot 'settings.json' }
if (-not (Test-Path $Settings)) {
  throw ('settings file not found: ' + $Settings + ' (copy settings.json.example and fill it in)')
}
$names = Read-Names (Join-Path $PSScriptRoot 'names.txt')
$secret = $names['secret']

# -InputObject rather than the pipeline: piped, ConvertFrom-Json unrolls a
# top-level array and turns an object with one property into that property.
$raw = [IO.File]::ReadAllText($Settings, [Text.Encoding]::UTF8)
$cfg = ConvertFrom-Json -InputObject $raw
$props = @($cfg.PSObject.Properties)
if ($props.Count -eq 0) { throw ('settings file has no constants: ' + $Settings) }

$report = New-Object Text.StringBuilder
function Say($t) { [void]$report.AppendLine($t); Write-Output $t }

$db = Connect1C (Join-Path $PSScriptRoot 'conn.txt')
$status = 0
try {
  $consts = Get1C $db 'Constants'
  foreach ($p in $props) {
    $name = $p.Name
    $value = $p.Value
    if ($null -eq $value) { $value = '' }
    if ($value -is [array]) { $value = (@($value) -join ', ') }
    $value = [string]$value
    try {
      $mgr = Get1C $consts $name
      Call1C $mgr 'Set' @($value) | Out-Null
      $back = [string](Call1C $mgr 'Get' @())
      if ($name -eq $secret) {
        $shown = '<hidden, ' + $back.Length + ' chars>'
      } else {
        $shown = '"' + $back + '"'
      }
      $mark = if ($back -eq $value) { 'ok' } else { 'MISMATCH (stored value differs from the file)' }
      Say ($name + ' = ' + $shown + ' ' + $mark)
      if ($back -ne $value) { $status = 1 }
    } catch {
      Say ($name + ' ERROR: ' + (Describe-Error $_))
      $status = 1
    }
  }
} catch {
  Say ('ERROR: ' + (Describe-Error $_))
  $status = 1
}

Write-Utf8 (Join-Path (Get-OutDir) 'constants.txt') $report.ToString()
$mgr = $null; $consts = $null
$db = $null
Disconnect1C
exit $status
