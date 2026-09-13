# lib1c.ps1 - helpers for driving the 1C file base over V83.COMConnector.
#
# Dot-source it from the other scripts in this folder:
#   . (Join-Path $PSScriptRoot 'lib1c.ps1')
#
# Everything here is ASCII-only on purpose. 32-bit PowerShell reads a .ps1
# without a UTF-8 BOM as ANSI and turns Cyrillic into garbage that late binding
# cannot resolve, and a BOM is one save-as away from being lost. Cyrillic names
# therefore travel through UTF-8 files instead: conn.txt (base, user, password),
# names.txt (extension, module and method names, COM aliases), settings.json
# (constant values).
#
# Traps this file works around, all verified on 8.3.27.2342 by the sibling
# project (tkgoldy.ru, migration/1c/lib1c.ps1):
#
#   1. Reading a property of a 1C COM object through dot notation silently
#      returns $null ($db.Catalogs is null). Only late binding works, hence
#      Get1C/Set1C/Call1C below. The connection object itself is the opposite:
#      $db.NewObject('Query') and $db.XMLString($ref) work through dot notation
#      and InvokeMember on the same names fails with DISP_E_UNKNOWNNAME.
#
#   2. A PowerShell function unrolls anything enumerable that it returns, and
#      1C collections are enumerable: a plain "return" hands the caller an
#      Object[] instead of the collection. Hence Write-Output -NoEnumerate.
#
#   3. Everything that travels through Write-Output comes back wrapped in a
#      PSObject, and reflection does not see through the wrapper. Unwrapping is
#      done by assignment from $x.PSObject.BaseObject at the top of each helper.
#
#   4. For some 1C objects .NET cannot build the member cache: the Russian and
#      English names collapse into one key and InvokeMember fails with an
#      ArgumentException. Those objects only answer to CallByName (IDispatch).
#
#   5. Member names of the COM interface are mixed: most platform members answer
#      to the English name, a few only to the Russian one. names.txt carries
#      "alias.<English>=<Russian>" lines and the helpers try the alias when the
#      English name is unknown - only then, so a method that ran and failed is
#      never run twice.
#
#   6. A function parameter must not be called $Args: that is the automatic
#      variable, and the collision silently strips the argument list.
#
#   7. The platform is 32-bit, so the COM class is registered for 32-bit
#      processes only. Run the scripts with
#      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe; the 64-bit
#      host fails on New-Object with "class not registered" (0x80040154).
#
#   8. An open COM connection holds the file base and the designer then fails
#      to log in, silently and with an empty log. Drop the connection variable
#      and call Disconnect1C before starting designer.ps1; the first connection
#      to the base takes up to a minute (a 19 GB file base warms up).

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName Microsoft.VisualBasic

$script:BF_GET    = [Reflection.BindingFlags]::GetProperty
$script:BF_SET    = [Reflection.BindingFlags]::SetProperty
$script:BF_METHOD = [Reflection.BindingFlags]::InvokeMethod
$script:Aliases   = @{}

# Reads a key=value file in UTF-8 (BOM or not) into a hashtable. Lines that are
# empty or start with # are skipped. "alias.X=Y" lines also register a COM
# member alias for the helpers below.
function Read-Names {
  param([string]$Path)
  $names = @{}
  foreach ($line in [IO.File]::ReadAllLines($Path, [Text.Encoding]::UTF8)) {
    $t = $line.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $i = $t.IndexOf('=')
    if ($i -lt 1) { throw ('names file: bad line "' + $t + '" in ' + $Path) }
    $k = $t.Substring(0, $i).Trim()
    $v = $t.Substring($i + 1).Trim()
    $names[$k] = $v
    if ($k.StartsWith('alias.')) { $script:Aliases[$k.Substring(6)] = $v }
  }
  return $names
}

function Connect1C {
  param([string]$ConnFile)
  if (-not (Test-Path $ConnFile)) {
    throw ('conn.txt not found: ' + $ConnFile + ' (copy conn.txt.example and fill it in)')
  }
  $cl = [IO.File]::ReadAllLines($ConnFile, [Text.Encoding]::UTF8)
  if ($cl.Length -lt 3) { throw 'conn.txt must have three lines: base path, user, password' }
  try {
    $conn = New-Object -ComObject 'V83.COMConnector'
  } catch {
    $hint = ''
    if ([IntPtr]::Size -eq 8) {
      $hint = ' The platform is 32-bit: run this under C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe.'
    }
    throw ('V83.COMConnector is not available: ' + $_.Exception.Message + $hint)
  }
  Write-Output -NoEnumerate $conn.Connect('File="' + $cl[0] + '";Usr="' + $cl[1] + '";Pwd="' + $cl[2] + '";')
}

# The caller must have dropped its own references first ($db = $null): a
# function cannot null out a variable in the caller's scope.
function Disconnect1C {
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}

# The full text of an error: InvokeMember wraps the 1C exception into a
# TargetInvocationException whose own message says nothing, so the chain of
# inner exceptions is what carries the text raised by the 1C module.
function Describe-Error {
  param($ErrorRecord)
  $parts = @()
  $e = $ErrorRecord.Exception
  while ($null -ne $e) {
    $m = $e.Message
    if ($m -ne '' -and -not ($parts -contains $m)) { $parts += $m }
    $e = $e.InnerException
  }
  return ($parts -join ' <- ')
}

function Test-UnknownName {
  param($Exception)
  $e = $Exception
  while ($null -ne $e) {
    if ($e -is [System.MissingMemberException]) { return $true }
    if ($e -is [System.Runtime.InteropServices.COMException] -and $e.HResult -eq -2147352570) { return $true }
    if ($e.Message -match 'DISP_E_UNKNOWNNAME|0x80020006') { return $true }
    $e = $e.InnerException
  }
  return $false
}

function Resolve-Names {
  param([string]$Name)
  $list = @($Name)
  if ($script:Aliases.ContainsKey($Name)) { $list += $script:Aliases[$Name] }
  return $list
}

function Get1C {
  param($Obj, [string]$Name)
  if ($null -ne $Obj) { $Obj = $Obj.PSObject.BaseObject }
  $last = $null
  foreach ($n in (Resolve-Names $Name)) {
    try {
      $v = $Obj.GetType().InvokeMember($n, $script:BF_GET, $null, $Obj, $null)
      Write-Output -NoEnumerate $v
      return
    } catch [ArgumentException] {
      $v = [Microsoft.VisualBasic.Interaction]::CallByName($Obj, $n, 'Get')
      Write-Output -NoEnumerate $v
      return
    } catch {
      $last = $_
      if (-not (Test-UnknownName $_.Exception)) { throw }
    }
  }
  throw ('Get1C: no member ' + ((Resolve-Names $Name) -join '/') + ': ' + (Describe-Error $last))
}

function Set1C {
  param($Obj, [string]$Name, $Value)
  if ($null -ne $Obj) { $Obj = $Obj.PSObject.BaseObject }
  $v = $Value
  if ($null -ne $v) { $v = $v.PSObject.BaseObject }
  $last = $null
  foreach ($n in (Resolve-Names $Name)) {
    try {
      try {
        [void]$Obj.GetType().InvokeMember($n, $script:BF_SET, $null, $Obj, @($v))
      } catch [ArgumentException] {
        [void][Microsoft.VisualBasic.Interaction]::CallByName($Obj, $n, 'Set', $v)
      }
      return
    } catch {
      $last = $_
      if (-not (Test-UnknownName $_.Exception)) {
        $vt = if ($null -eq $v) { '<null>' } else { $v.GetType().Name }
        throw ("Set1C '" + $n + "' (" + $vt + '): ' + (Describe-Error $_))
      }
    }
  }
  throw ('Set1C: no member ' + ((Resolve-Names $Name) -join '/') + ': ' + (Describe-Error $last))
}

# The parameter is deliberately not called $Args (trap 6). $MethodArgs on its
# own is not a truth test either: a one-element array is evaluated as that
# element, so @(0) reads as false - compare against $null explicitly.
function Call1C {
  param($Obj, [string]$Name, [object[]]$MethodArgs = @())
  if ($null -ne $Obj) { $Obj = $Obj.PSObject.BaseObject }
  $a = $null
  if ($null -ne $MethodArgs -and $MethodArgs.Count -gt 0) {
    $a = @()
    foreach ($x in $MethodArgs) {
      $y = $x
      if ($null -ne $y) { $y = $y.PSObject.BaseObject }
      $a += ,$y
    }
  }
  $last = $null
  foreach ($n in (Resolve-Names $Name)) {
    try {
      try {
        $v = $Obj.GetType().InvokeMember($n, $script:BF_METHOD, $null, $Obj, $a)
      } catch [ArgumentException] {
        if ($null -eq $a) {
          $v = [Microsoft.VisualBasic.Interaction]::CallByName($Obj, $n, 'Method')
        } else {
          $v = [Microsoft.VisualBasic.Interaction]::CallByName($Obj, $n, 'Method', $a)
        }
      }
      Write-Output -NoEnumerate $v
      return
    } catch {
      $last = $_
      if (-not (Test-UnknownName $_.Exception)) { throw }
    }
  }
  throw ('Call1C: no member ' + ((Resolve-Names $Name) -join '/') + ': ' + (Describe-Error $last))
}

# Console output mangles Cyrillic under the 32-bit host, so every script also
# writes its report to a UTF-8 file under out/.
function Write-Utf8 {
  param([string]$Path, [string]$Text)
  $dir = Split-Path -Parent $Path
  if ($dir -ne '' -and -not (Test-Path $dir)) { [void](New-Item -ItemType Directory $dir) }
  [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Get-OutDir {
  $dir = Join-Path $PSScriptRoot 'out'
  if (-not (Test-Path $dir)) { [void](New-Item -ItemType Directory $dir) }
  return $dir
}
