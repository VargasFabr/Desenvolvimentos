[CmdletBinding()]
param(
    [string] $ContainerName = 'airflow3-standalone',
    [switch] $SkipDockerVersionCheck,
    [switch] $RestartOnly
)

$ErrorActionPreference = 'Continue'

function Show-DockerTroubleshoot {
    Write-Host ''
    Write-Host 'Docker engine returned an error (Internal Server Error on dockerDesktopLinuxEngine).' -ForegroundColor Yellow
    Write-Host 'Try this order:' -ForegroundColor Yellow
    Write-Host '  1) Docker Desktop -> Restart' -ForegroundColor White
    Write-Host '  2) PowerShell: wsl --shutdown (then open Docker Desktop again)' -ForegroundColor White
    Write-Host '  3) Update Docker Desktop' -ForegroundColor White
    Write-Host '  4) Current session workaround:' -ForegroundColor White
    Write-Host "     `$env:DOCKER_API_VERSION = '1.52'" -ForegroundColor Gray
    Write-Host ''
}

function Test-DockerEngine {
    param([switch] $SkipVersion)

    if ($SkipVersion) {
        $null = & docker ps -q 2>&1
        return ($LASTEXITCODE -eq 0)
    }

    $verOut = & docker version 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Warning 'docker version failed. Trying docker ps...'
    $null = & docker ps -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'docker ps OK, continuing.' -ForegroundColor DarkGray
        return $true
    }

    Write-Host $verOut -ForegroundColor Red
    Show-DockerTroubleshoot
    return $false
}

function Get-DagIdsFromContainer {
    param([string] $Name)

    $jsonOut = & docker exec $Name airflow dags list -o json 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $jsonOut -match 'dag_id|"dag_id"') {
        try {
            $arr = $jsonOut | ConvertFrom-Json
            if ($arr -is [System.Array]) {
                return @($arr | ForEach-Object { $_.dag_id } | Where-Object { $_ })
            }
            if ($arr.dag_id) { return @($arr.dag_id) }
        } catch {
        }
    }

    $plain = & docker exec $Name airflow dags list -o plain 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw ('Failed to list DAGs: ' + $plain)
    }

    $ids = New-Object System.Collections.Generic.HashSet[string]
    $lines = @($plain -split "`n")
    foreach ($line in $lines) {
        $t = $line.Trim()
        if (-not $t) { continue }
        if ($t -match '^\s*dag_id\s') { continue }
        if ($t -match '^docker\s*:') { continue }
        if ($t -match '^At\s+') { continue }
        if ($t -match '^\+{1}\s') { continue }
        if ($t -match '^Error:') { continue }
        if ($t -match '^CategoryInfo') { continue }
        if ($t -match '^FullyQualifiedErrorId') { continue }
        $parts = $t -split '\s+', 2
        $id = $parts[0]
        if ($id -and $id -ne 'dag_id' -and $id -match '^[A-Za-z0-9_.-]+$') {
            $null = $ids.Add($id)
        }
    }
    return @($ids.ToArray() | Sort-Object)
}

Write-Host '== Airflow: pause all DAGs + restart container ==' -ForegroundColor Cyan
Write-Host ('Container: ' + $ContainerName)

if (-not (Test-DockerEngine -SkipVersion:$SkipDockerVersionCheck)) {
    if ($RestartOnly) {
        Write-Host ('Trying restart anyway: docker restart ' + $ContainerName) -ForegroundColor Yellow
        & docker restart $ContainerName 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host 'Restart completed.' -ForegroundColor Green
            exit 0
        }
    }
    exit 1
}

if ($RestartOnly) {
    Write-Host ('[RestartOnly] Restarting ' + $ContainerName + ' ...') -ForegroundColor Yellow
    & docker restart $ContainerName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error ('Failed: docker restart ' + $ContainerName)
        exit 1
    }
    Write-Host 'Done.' -ForegroundColor Green
    exit 0
}

$running = (& docker ps --filter "name=^/${ContainerName}$" --format '{{.Names}}' 2>&1 | Out-String).Trim()
if (-not $running -or $running -notmatch [regex]::Escape($ContainerName)) {
    Write-Error ("Container '" + $ContainerName + "' is not running. Start with: docker compose up -d")
    exit 1
}

Write-Host '[1/3] Listing DAGs...' -ForegroundColor Yellow
try {
    $dagIds = @(Get-DagIdsFromContainer -Name $ContainerName)
} catch {
    Write-Warning ('Could not list/pause DAGs: ' + $_)
    Write-Host 'Restarting container only to kill workers...' -ForegroundColor Yellow
    & docker restart $ContainerName 2>&1
    if ($LASTEXITCODE -eq 0) { exit 0 } else { exit 1 }
}

if ($dagIds.Count -eq 0) {
    Write-Warning 'No DAG found. Restarting anyway.'
} else {
    Write-Host ('Found DAGs: ' + $dagIds.Count)
}

Write-Host '[2/3] Pausing DAGs...' -ForegroundColor Yellow
$ok = 0
$fail = 0
foreach ($dag in $dagIds) {
    $null = & docker exec $ContainerName airflow dags pause $dag 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ok++
        Write-Host ('  paused: ' + $dag) -ForegroundColor Green
    } else {
        $null = & docker exec $ContainerName airflow dags pause $dag --yes 2>&1
        if ($LASTEXITCODE -eq 0) {
            $ok++
            Write-Host ('  paused: ' + $dag + ' (using --yes)') -ForegroundColor Green
        } else {
            $fail++
            Write-Host ('  FAILED to pause: ' + $dag) -ForegroundColor Red
        }
    }
}

Write-Host '[3/3] Restarting container...' -ForegroundColor Yellow
& docker restart $ContainerName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error ('Failed: docker restart ' + $ContainerName)
    exit 1
}

Write-Host ('Done. Paused OK: ' + $ok + ' | Failed: ' + $fail) -ForegroundColor Cyan
Write-Host 'To resume: airflow dags unpause DAG_NAME' -ForegroundColor DarkGray
