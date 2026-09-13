# designer.ps1 - run the 1C DESIGNER in batch mode against the base in conn.txt.
#
# Why this exists: passing Cyrillic arguments (user name, extension name, paths
# with Cyrillic folders) through bash mangles them and the designer answers
# "user not identified". PowerShell hands them to CreateProcess as Unicode.
# The script itself stays ASCII-only; Cyrillic values come from conn.txt and
# from the parameters the caller passes.
#
# Commands (the extension name is passed as -Extension in every case):
#   LoadConfigFromFiles  -Target <folder with Configuration.xml>  [-UpdateDBCfg]
#       load the extension from XML sources; creates it when the base has none.
#       -UpdateDBCfg applies the change to the database (needed: the extension
#       owns constants, and those are tables).
#   DumpConfigToFiles    -Target <folder>
#       dump the extension back to XML, e.g. to diff with the sources.
#   DumpCfg              -Target <file.cfe>
#       build the .cfe to carry to the server copy.
#   LoadCfg              -Target <file.cfe>  [-UpdateDBCfg]
#       load a .cfe (the server-side counterpart of the first command).
#
# Usage (the extension name is Cyrillic; README shows the exact commands):
#   designer.ps1 -Command LoadConfigFromFiles -Target "..\ext\<Name>" -Extension <Name> -UpdateDBCfg
#   designer.ps1 -Command DumpCfg -Target "out\<Name>.cfe" -Extension <Name>
#
# The designer's own messages go to out\designer.log and are echoed after the
# run; an empty log with a non-zero exit usually means the base is held by an
# open COM connection or another designer (see lib1c.ps1, trap 8).
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('LoadConfigFromFiles', 'DumpConfigToFiles', 'DumpCfg', 'LoadCfg')]
  [string]$Command,
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$Extension,
  [string]$Exe = 'C:\Program Files (x86)\1cv8\8.3.27.2342\bin\1cv8.exe',
  [switch]$UpdateDBCfg
)
$ErrorActionPreference = 'Stop'

$connFile = Join-Path $PSScriptRoot 'conn.txt'
if (-not (Test-Path $connFile)) {
  throw ('conn.txt not found: ' + $connFile + ' (copy conn.txt.example and fill it in)')
}
$cl = [IO.File]::ReadAllLines($connFile, [Text.Encoding]::UTF8)
$db = $cl[0]; $usr = $cl[1]; $pw = $cl[2]

if (-not (Test-Path $Exe)) { throw ('1cv8.exe not found: ' + $Exe + ' (pass -Exe)') }

# Relative targets are resolved against the current directory, the way the
# designer would see them; the parent of a file target must already exist.
# Join-Path glues an absolute target onto the current directory and produces
# a path .NET refuses, hence the check.
if (-not [IO.Path]::IsPathRooted($Target)) {
  $Target = Join-Path (Get-Location).Path $Target
}
$Target = [IO.Path]::GetFullPath($Target)

$outDir = Join-Path $PSScriptRoot 'out'
if (-not (Test-Path $outDir)) { [void](New-Item -ItemType Directory $outDir) }
$log = Join-Path $outDir 'designer.log'
if (Test-Path $log) { Remove-Item $log -Force }

# One designer run. 1cv8.exe is a GUI-subsystem executable: the call operator
# does not wait for it and $LASTEXITCODE stays empty, so a script written that
# way reports "done" while the designer is still loading. Start-Process -Wait
# does wait; its argument list is joined with spaces and not quoted, hence the
# quoting (the base path and the target routinely contain spaces).
function Invoke-Designer([string[]]$Tail) {
  if (Test-Path $log) { Remove-Item $log -Force }
  $a = @('DESIGNER', "/F$db", "/N$usr", "/P$pw",
         '/DisableStartupDialogs', '/DisableStartupMessages', "/Out$log") + $Tail
  $quoted = $a | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }
  $proc = Start-Process -FilePath $Exe -ArgumentList $quoted -Wait -PassThru -NoNewWindow
  $text = ''
  if (Test-Path $log) { $text = [IO.File]::ReadAllText($log, [Text.Encoding]::UTF8).Trim() }
  # Write-Host, not Write-Output: the function's output stream is its return
  # value, and the exit code must come back alone.
  Write-Host ('EXIT=' + $proc.ExitCode)
  if ($text -ne '') { Write-Host ('LOG: ' + $text) }
  return $proc.ExitCode
}

$code = Invoke-Designer @("/$Command", $Target, '-Extension', $Extension)

# The database update is a second run on purpose: "/LoadConfigFromFiles ...
# /UpdateDBCfg -Extension X" on one command line is refused by the designer
# as a command-line error, while the same two steps one after the other work.
if ($UpdateDBCfg -and $code -eq 0) {
  $code = Invoke-Designer @('/UpdateDBCfg', '-Extension', $Extension)
}
exit $code
