<#
.SYNOPSIS
  Diagnostico seguro do Docker Desktop/WSL local.

.DESCRIPTION
  Faz apenas checagens de leitura:
  - WSL distros e estado do docker-desktop
  - PATH e localizacao do docker.exe
  - Docker context
  - Docker client/server version
  - Containers e volumes

  Nao executa prune, reset, down -v, remocao de volumes ou alteracoes de dados.

.PARAMETER FixPathForSession
  Adiciona temporariamente o binario oficial do Docker Desktop ao PATH da sessao.

.PARAMETER ShowVolumes
  Lista volumes Docker.

.EXAMPLE
  .\Check-DockerLocal.ps1
  .\Check-DockerLocal.ps1 -FixPathForSession -ShowVolumes
#>

[CmdletBinding()]
param(
    [switch] $FixPathForSession,
    [switch] $ShowVolumes
)

$DockerBin = 'C:\Program Files\Docker\Docker\resources\bin'

function Write-Section {
    param([string] $Title)
    Write-Host ''
    Write-Host "== $Title ==" -ForegroundColor Cyan
}

function Write-Ok {
    param([string] $Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnLine {
    param([string] $Message)
    Write-Host "[AVISO] $Message" -ForegroundColor Yellow
}

function Write-Bad {
    param([string] $Message)
    Write-Host "[ERRO] $Message" -ForegroundColor Red
}

function Run-Text {
    param([scriptblock] $Command)
    try {
        $text = (& $Command 2>&1 | Out-String)
    } catch {
        $text = ($_ | Out-String)
    }
    # Alguns comandos WSL no Windows podem retornar texto com NUL entre caracteres.
    return ($text -replace "`0", '').Trim()
}

Write-Host 'Diagnostico Docker/WSL local - seguro, sem apagar dados' -ForegroundColor Cyan

if ($FixPathForSession) {
    if (Test-Path $DockerBin) {
        $env:Path = "$DockerBin;$env:Path"
        Write-Ok "PATH da sessao ajustado: $DockerBin"
    } else {
        Write-WarnLine "DockerBin nao encontrado: $DockerBin"
    }
}

Write-Section 'WSL'
$wslOutput = Run-Text { wsl -l -v }
Write-Host $wslOutput

if ($wslOutput -match 'docker-desktop\s+Running\s+2') {
    Write-Ok 'docker-desktop esta Running no WSL2.'
} elseif ($wslOutput -match 'docker-desktop\s+Stopped\s+2') {
    Write-WarnLine 'docker-desktop esta Stopped. Abra/Reinicie o Docker Desktop.'
    Write-Host 'Sugestao segura: Quit Docker Desktop -> wsl --shutdown -> abrir Docker Desktop.'
} else {
    Write-WarnLine 'Nao identifiquei docker-desktop como Running no WSL.'
}

Write-Section 'Docker no PATH'
$dockerLocations = Run-Text { where.exe docker }
if ($dockerLocations) {
    Write-Host $dockerLocations
    if ($dockerLocations -match [regex]::Escape($DockerBin)) {
        Write-Ok 'Docker Desktop resources\bin aparece no PATH.'
    } else {
        Write-WarnLine "Docker Desktop resources\bin nao apareceu no PATH. Use: `$env:Path = `"$DockerBin;`" + `$env:Path"
    }
} else {
    Write-Bad 'docker.exe nao encontrado no PATH.'
    Write-Host "Use temporariamente: `$env:Path = `"$DockerBin;`" + `$env:Path"
}

Write-Section 'Docker Context'
$contextOutput = Run-Text { docker context ls }
Write-Host $contextOutput
if ($contextOutput -match 'desktop-linux\s+\*\s+Docker Desktop') {
    Write-Ok 'Contexto atual: desktop-linux.'
} elseif ($contextOutput -match 'desktop-linux') {
    Write-WarnLine 'Contexto desktop-linux existe, mas nao parece estar ativo.'
    Write-Host 'Comando: docker context use desktop-linux'
}

Write-Section 'Docker Version'
$versionOutput = Run-Text { docker version }
Write-Host $versionOutput

$hasClient = $versionOutput -match 'Client:'
$hasServer = $versionOutput -match 'Server:'

if ($hasClient -and $hasServer) {
    Write-Ok 'Docker client e server responderam.'
} elseif ($hasClient -and -not $hasServer) {
    Write-Bad 'Docker client respondeu, mas o engine/server nao respondeu.'
    Write-Host 'Sugestao segura: Quit Docker Desktop -> wsl --shutdown -> abrir Docker Desktop e aguardar Engine running.'
} else {
    Write-Bad 'Docker nao respondeu corretamente.'
}

if ($versionOutput -match 'Internal Server Error') {
    Write-Bad 'Engine retornou Internal Server Error.'
    Write-Host 'Nao rode reset/prune/down -v. Primeiro tente reiniciar Docker Desktop e WSL.'
}

Write-Section 'Containers'
$psOutput = Run-Text { docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' }
Write-Host $psOutput

if ($psOutput -match 'n8n-ssh-tunnel' -and $psOutput -match 'n8n-ssh-tunnel-reverse') {
    Write-Ok 'Os dois tuneis esperados aparecem na lista de containers.'
} else {
    Write-WarnLine 'Nao encontrei os dois tuneis na lista. Se o engine estiver OK, rode docker compose up -d.'
}

if ($ShowVolumes) {
    Write-Section 'Volumes'
    $volumeOutput = Run-Text { docker volume ls --format 'table {{.Name}}\t{{.Driver}}' }
    Write-Host $volumeOutput
    Write-Host 'Obs: apenas listagem. Nenhum volume foi removido.' -ForegroundColor DarkGray
}

Write-Section 'Resumo'
if ($hasClient -and $hasServer -and $wslOutput -match 'docker-desktop\s+Running\s+2') {
    Write-Ok 'Docker local parece funcional.'
} else {
    Write-WarnLine 'Docker local ainda precisa de atencao. Siga as sugestoes acima.'
}

