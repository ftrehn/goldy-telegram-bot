# extension_mode.ps1 - list the extensions installed in the base and, for the
# bot extension, switch off safe mode and the protection from dangerous actions.
#
# Why: an extension loaded from files lands in safe mode, and in safe mode the
# platform refuses outgoing network connections from the extension's code -
# HTTPConnection is on the list. The catalog export is exactly such a
# connection, so the scheduled job would fail on its first request until this
# has been done once. The designer has the same two switches in the list of
# extensions (Configuration - Configuration extensions); this script makes the
# step repeatable and visible in a log.
#
# What it changes on the extension named in names.txt (or -Name):
#   SafeMode                 = false   (allowed to leave the sandbox)
#   UnsafeActionProtection   = no warnings (no interactive question that a
#                                          background job can never answer)
#   Active                   = true    (a loaded but inactive extension does
#                                       nothing, silently)
# then Write() - properties only, the extension data is left as loaded.
# The change applies to sessions started after it, including the next COM
# connection and the next run of the scheduled job.
#
# Usage (32-bit PowerShell, see README):
#   extension_mode.ps1             list every extension, then fix the bot one
#   extension_mode.ps1 -ListOnly   list only, change nothing
#   extension_mode.ps1 -Name X     act on another extension from the list
param(
  [string]$Name = '',
  [switch]$ListOnly
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib1c.ps1')

$names = Read-Names (Join-Path $PSScriptRoot 'names.txt')
if ($Name -eq '') { $Name = $names['extension'] }

$report = New-Object Text.StringBuilder
function Say($t) { [void]$report.AppendLine($t); Write-Output $t }

function Describe-Extension($e) {
  $prot = Get1C $e 'UnsafeActionProtection'
  $warn = Get1C $prot 'UnsafeOperationWarnings'
  return ('name=' + (Get1C $e 'Name') + ' | version=' + (Get1C $e 'Version') +
          ' | active=' + (Get1C $e 'Active') + ' | safeMode=' + (Get1C $e 'SafeMode') +
          ' | unsafeActionWarnings=' + $warn)
}

$db = Connect1C (Join-Path $PSScriptRoot 'conn.txt')
$status = 0
try {
  $mgr = Get1C $db 'ConfigurationExtensions'
  # ConfigurationExtensions.Get() comes back as a 1C array (a COM enumerable,
  # not a .NET array): .Length on it is evaluated per element and gives a list
  # of ones. Only the pipeline enumerates it, hence the ForEach-Object.
  $list = @((Call1C $mgr 'Get' @()) | ForEach-Object { $_ })
  $n = $list.Length
  Say ('EXTENSIONS=' + $n)
  $target = $null
  for ($i = 0; $i -lt $n; $i++) {
    $e = $list[$i]
    Say ('  ' + (Describe-Extension $e))
    if ((Get1C $e 'Name') -eq $Name) { $target = $e }
  }

  if ($null -eq $target) {
    Say ('TARGET NOT FOUND: ' + $Name + ' (load it first with designer.ps1)')
    $status = 2
  } elseif ($ListOnly) {
    Say ('TARGET (unchanged): ' + (Describe-Extension $target))
  } else {
    $changed = @()
    if ((Get1C $target 'SafeMode') -ne $false) {
      Set1C $target 'SafeMode' $false
      $changed += 'SafeMode=false'
    }
    $prot = Get1C $target 'UnsafeActionProtection'
    if ((Get1C $prot 'UnsafeOperationWarnings') -ne $false) {
      # The descriptor may be a copy, so it is assigned back after the change.
      Set1C $prot 'UnsafeOperationWarnings' $false
      Set1C $target 'UnsafeActionProtection' $prot
      $changed += 'UnsafeOperationWarnings=false'
    }
    if ((Get1C $target 'Active') -ne $true) {
      Set1C $target 'Active' $true
      $changed += 'Active=true'
    }
    if ($changed.Count -eq 0) {
      Say ('TARGET already in the right mode: ' + (Describe-Extension $target))
    } else {
      Call1C $target 'Write' @() | Out-Null
      Say ('CHANGED: ' + ($changed -join ', '))
      # Re-read from the base: what Write() actually stored, not what was set.
      $list2 = @((Call1C $mgr 'Get' @()) | ForEach-Object { $_ })
      for ($i = 0; $i -lt $list2.Length; $i++) {
        if ((Get1C $list2[$i] 'Name') -eq $Name) { Say ('TARGET now: ' + (Describe-Extension $list2[$i])) }
      }
    }
  }
} catch {
  Say ('ERROR: ' + (Describe-Error $_))
  $status = 1
}

Write-Utf8 (Join-Path (Get-OutDir) 'extensions.txt') $report.ToString()
$mgr = $null; $list = $null; $list2 = $null; $target = $null; $prot = $null; $e = $null
$db = $null
Disconnect1C
exit $status
