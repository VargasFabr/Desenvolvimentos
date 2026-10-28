# Instala/atualiza o plugin dacoes no perfil Hermes indicado (padrao: dacoes).
param(
    [string]$ProfileName = "dacoes",
    [string]$HermesHome = "$env:LOCALAPPDATA\hermes"
)

$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "hermes_plugin"
$target = Join-Path $HermesHome "profiles\$ProfileName\plugins\dacoes"

if (-not (Test-Path $source)) {
    throw "Pasta do plugin nao encontrada: $source"
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

$melnickCode = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$profileEnv = Join-Path $HermesHome "profiles\$ProfileName\.env"
if (Test-Path $profileEnv) {
    $envContent = Get-Content $profileEnv -Raw
    if ($envContent -notmatch '(?m)^MELNICK_CODE_PATH=') {
        Add-Content -Path $profileEnv -Value "`nMELNICK_CODE_PATH=$melnickCode"
        Write-Host "MELNICK_CODE_PATH adicionado ao .env do perfil '$ProfileName'."
    }
} else {
    Set-Content -Path $profileEnv -Value "MELNICK_CODE_PATH=$melnickCode"
    Write-Host "Criado .env do perfil com MELNICK_CODE_PATH."
}

$hermesVenvPip = Join-Path $HermesHome "hermes-agent\venv\Scripts\pip.exe"
$requirements = Join-Path $PSScriptRoot "requirements.txt"
if ((Test-Path $hermesVenvPip) -and (Test-Path $requirements)) {
    & $hermesVenvPip install -r $requirements -q
    Write-Host "Dependencias Python instaladas no venv do Hermes."
}

Write-Host "Plugin instalado em: $target"
Write-Host "Reinicie o gateway Hermes do perfil '$ProfileName' para carregar as tools."
