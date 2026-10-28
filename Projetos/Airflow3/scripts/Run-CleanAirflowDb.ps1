# Limpa apenas o historico de execucao do SQLite do Airflow.
# Preserva: conexoes (senhas), variaveis, usuarios e cadastro de DAGs no metadata.
# As DAGs em si ficam em Airflow3\dags\ (volume) e NAO sao tocadas.
#
# Uso:
#   .\Run-CleanAirflowDb.ps1
#   .\Run-CleanAirflowDb.ps1 -ContainerName meu-airflow
#   .\Run-CleanAirflowDb.ps1 -WhatIf

param(
    [string] $ContainerName = 'airflow3-standalone',
    [string] $DbPathInContainer = '/opt/airflow/airflow.db',
    [switch] $WhatIf
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir 'clean_airflow_db.py'
$backupDir = Join-Path $scriptDir 'backups'
$tmpDb = Join-Path $env:TEMP ("airflow_clean_{0}.db" -f (Get-Date -Format 'yyyyMMddHHmmss'))

function Resolve-Python {
    foreach ($cmd in @('python', 'py')) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) {
            if ($cmd -eq 'py') { return @('py', '-3') }
            return @('python')
        }
    }
    return $null
}

if (-not (Test-Path $pyScript)) {
    Write-Error "Nao encontrado: $pyScript"
    exit 1
}

$python = Resolve-Python
if (-not $python) {
    Write-Error "Python nao encontrado no PATH. Instale Python 3 ou use 'py -3'."
    exit 1
}

Write-Host ''
Write-Host '=== Limpeza do airflow.db (historico de execucao) ===' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Sera APAGADO:' -ForegroundColor Yellow
Write-Host '  log, task_instance, dag_run, job, xcom, etc. (historico de runs)'
Write-Host ''
Write-Host 'Sera PRESERVADO:' -ForegroundColor Green
Write-Host '  connection  -> senhas (postgres, postgres_otto, ...)'
Write-Host '  variable, ab_user, dag, serialized_dag'
Write-Host '  arquivos em PROJETOS\Airflow3\dags\  (volume Docker, fora do .db)'
Write-Host ''

if ($WhatIf) {
    Write-Host '[WhatIf] Nenhuma alteracao feita.' -ForegroundColor DarkGray
    exit 0
}

$confirm = Read-Host 'Continuar? (digite SIM para confirmar)'
if ($confirm -ne 'SIM') {
    Write-Host 'Cancelado.' -ForegroundColor Yellow
    exit 0
}

# Verifica Docker
$dockerOk = $false
try {
    docker version --format '{{.Server.Version}}' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    Write-Error "Docker nao esta respondendo. Abra o Docker Desktop e tente novamente."
    exit 1
}

$containerExists = docker ps -a --filter "name=^/${ContainerName}$" --format '{{.Names}}' 2>$null
if (-not $containerExists) {
    Write-Error "Container '$ContainerName' nao encontrado. Suba o stack com: docker compose up -d"
    exit 1
}

Write-Host ''
Write-Host "Parando container $ContainerName ..." -ForegroundColor Yellow
docker stop $ContainerName 2>&1 | Out-Null

Write-Host 'Copiando banco do container...' -ForegroundColor Yellow
docker cp "${ContainerName}:${DbPathInContainer}" $tmpDb
if (-not (Test-Path $tmpDb)) {
    Write-Error "Falha ao copiar banco. Verifique o caminho $DbPathInContainer."
    exit 1
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupDb = Join-Path $backupDir ("airflow_{0}.db" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Copy-Item -Force $tmpDb $backupDb
Write-Host "Backup salvo em: $backupDb" -ForegroundColor Green

Write-Host 'Executando limpeza (Python)...' -ForegroundColor Yellow
& @python $pyScript $tmpDb
if ($LASTEXITCODE -ne 0) {
    Write-Error "Script Python retornou erro. O banco no container NAO foi alterado."
    Remove-Item -Force $tmpDb -ErrorAction SilentlyContinue
    Write-Host "Restaurando container (banco original intacto)..." -ForegroundColor Yellow
    docker start $ContainerName | Out-Null
    exit 1
}

Write-Host 'Enviando banco de volta ao container...' -ForegroundColor Yellow
docker cp $tmpDb "${ContainerName}:${DbPathInContainer}"

Remove-Item -Force $tmpDb -ErrorAction SilentlyContinue

Write-Host 'Iniciando container...' -ForegroundColor Yellow
docker start $ContainerName | Out-Null
Start-Sleep -Seconds 5

# docker cp grava como root — o Airflow roda como usuario airflow e precisa escrever no .db
Write-Host 'Ajustando permissoes do banco (airflow:root)...' -ForegroundColor Yellow
docker exec -u root $ContainerName bash -c "chown airflow:root '$DbPathInContainer' && chmod 664 '$DbPathInContainer'; chown airflow:root '${DbPathInContainer}-wal' '${DbPathInContainer}-shm' 2>/dev/null; chmod 664 '${DbPathInContainer}-wal' '${DbPathInContainer}-shm' 2>/dev/null; true"

Write-Host ''
Write-Host 'Concluido. Conexoes e DAGs preservados.' -ForegroundColor Green
Write-Host "Se precisar reverter: copie o backup de volta com docker cp" -ForegroundColor DarkGray
Write-Host "  docker stop $ContainerName" -ForegroundColor DarkGray
Write-Host "  docker cp `"$backupDb`" ${ContainerName}:${DbPathInContainer}" -ForegroundColor DarkGray
Write-Host "  docker start $ContainerName" -ForegroundColor DarkGray
