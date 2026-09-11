<#
.SYNOPSIS
    Loads a .env-style file into the environment, then starts one of goldy's
    own processes.

.DESCRIPTION
    goldy reads configuration straight from the OS environment at startup —
    there is no dotenv loader anywhere in the project. That makes the classic
    "cp .env.example .env" instruction incomplete on its own: the file gets
    created, but a plain `python -m goldy.telegram_bot` run afterwards in the
    same shell still sees no TELEGRAM_BOT_TOKEN, because nothing ever reads
    the file into the process. This script is the missing step.

    It parses KEY=VALUE lines from -EnvFile (blank lines and lines starting
    with `#` are skipped), sets each as an environment variable of the
    current PowerShell process, and then starts the process named by
    -Process. Because a .ps1 script runs in the same OS process as the
    session that called it — PowerShell only gives it a new variable scope,
    not a new process — the variables are still set after this script
    returns too, in case you want to run something else by hand afterwards.

    Picking the process by name rather than accepting an arbitrary command
    line is deliberate: PowerShell's own parameter binder tries to match
    every "-something" token against this script's parameters before your
    command ever sees it, so a passed-through flag as ordinary as `-c` can be
    silently swallowed as an abbreviation of one of this script's own
    parameters. A closed set of known processes sidesteps that trap entirely.

.PARAMETER Process
    Which of goldy's processes to start: bot, worker, scheduler, or seed.

.PARAMETER EnvFile
    Path to the env file to load. Defaults to ".env" in the current directory.

.PARAMETER CatalogFile
    Required, and only meaningful, when -Process is "seed": the JSON catalog
    snapshot to import.

.EXAMPLE
    .\scripts\run-with-env.ps1 -Process bot -EnvFile .env.dev.example

.EXAMPLE
    .\scripts\run-with-env.ps1 -Process worker -EnvFile .env.dev.example

.EXAMPLE
    .\scripts\run-with-env.ps1 -Process scheduler -EnvFile .env.dev.example

.EXAMPLE
    .\scripts\run-with-env.ps1 -Process seed -EnvFile .env.dev.example -CatalogFile docs/design/catalog-snapshot.example.json
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('bot', 'worker', 'scheduler', 'seed')]
    [string]$Process,

    [string]$EnvFile = ".env",

    [string]$CatalogFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Write-Error "Env file not found: $EnvFile"
    exit 1
}

if ($Process -eq 'seed' -and [string]::IsNullOrWhiteSpace($CatalogFile)) {
    Write-Error "-Process seed needs -CatalogFile <path to a JSON snapshot>"
    exit 1
}

$loadedCount = 0

foreach ($rawLine in Get-Content -LiteralPath $EnvFile) {
    $line = $rawLine.Trim()

    if ($line -eq '' -or $line.StartsWith('#')) {
        continue
    }

    $separatorIndex = $line.IndexOf('=')
    if ($separatorIndex -lt 0) {
        Write-Warning "Skipping line without '=': $line"
        continue
    }

    $key = $line.Substring(0, $separatorIndex).Trim()
    $value = $line.Substring($separatorIndex + 1).Trim()

    # Strip one layer of matching quotes, the way a shell's own `.` would.
    $isQuoted = $value.Length -ge 2 -and (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    )
    if ($isQuoted) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    if ($key -eq '') {
        Write-Warning "Skipping line with an empty key: $line"
        continue
    }

    [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
    $loadedCount++
}

Write-Host "run-with-env: loaded $loadedCount variable(s) from $EnvFile" -ForegroundColor DarkGray

# Run through `uv run --active` rather than a bare `python`/`taskiq`: those
# resolve against whatever is first on PATH, which on a machine with more
# than one Python is not reliably this project's own .venv.
switch ($Process) {
    'bot' {
        $executable = 'uv'
        $executableArgs = @('run', '--active', 'python', '-m', 'goldy.telegram_bot')
    }
    'worker' {
        $executable = 'uv'
        $executableArgs = @('run', '--active', 'taskiq', 'worker', 'goldy.worker_app:create_worker_taskiq_app')
    }
    'scheduler' {
        $executable = 'uv'
        $executableArgs = @('run', '--active', 'taskiq', 'scheduler', 'goldy.scheduler_app:create_scheduler_taskiq_app')
    }
    'seed' {
        $executable = 'uv'
        $executableArgs = @('run', '--active', 'python', '-m', 'goldy.catalog_seed_app', '--file', $CatalogFile)
    }
}

Write-Host "run-with-env: starting $executable $($executableArgs -join ' ')" -ForegroundColor DarkGray

& $executable @executableArgs
exit $LASTEXITCODE
