#!/bin/bash

# Script de configuração automática para resolver o problema de volumes do Airflow

set -e

echo "===== CONFIGURAÇÃO DO AIRFLOW 3 ====="
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Criar diretórios necessários
echo "1. Criando estrutura de diretórios..."
mkdir -p dags logs plugins ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
echo -e "${GREEN}✓${NC} Diretórios criados"

# 2. Verificar se existe algum projeto Melnick-Code no sistema
echo ""
echo "2. Buscando projetos Melnick-Code no sistema..."
POSSIBLE_PATHS=(
    "/home/$USER/Projetos/VS_Code/Melnick-Code"
    "/home/$USER/Documents/Projetos/Melnick-Code"
    "/mnt/e/Projetos/VS_Code/Melnick-Code"  # WSL Windows E:
    "/mnt/c/Users/$USER/Projetos/Melnick-Code"  # WSL Windows C:
)

FOUND_PATH=""
for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -d "$path" ]; then
        echo -e "${GREEN}✓${NC} Encontrado: $path"
        FOUND_PATH="$path"
        break
    fi
done

if [ -z "$FOUND_PATH" ]; then
    echo -e "${YELLOW}⚠${NC} Nenhum projeto encontrado automaticamente"
    echo "Você precisará copiar manualmente seus arquivos para:"
    echo "  ./ProjetosVS/Melnick-Code/"
else
    echo ""
    echo "Deseja criar um link simbólico ou copiar os arquivos?"
    echo "1) Link simbólico (recomendado - não duplica arquivos)"
    echo "2) Copiar arquivos"
    echo "3) Pular (fazer manualmente depois)"
    read -p "Escolha (1/2/3): " choice
    
    case $choice in
        1)
            ln -sf "$FOUND_PATH" ./ProjetosVS/Melnick-Code
            echo -e "${GREEN}✓${NC} Link simbólico criado"
            ;;
        2)
            cp -r "$FOUND_PATH"/* ./ProjetosVS/Melnick-Code/
            echo -e "${GREEN}✓${NC} Arquivos copiados"
            ;;
        3)
            echo -e "${YELLOW}⚠${NC} Pulado - você precisará copiar os arquivos manualmente"
            ;;
    esac
fi

# 3. Verificar se o arquivo principal existe
echo ""
echo "3. Verificando arquivo AutoBackoffice.py..."
if [ -f "./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py" ]; then
    echo -e "${GREEN}✓${NC} Arquivo AutoBackoffice.py encontrado"
else
    echo -e "${RED}✗${NC} Arquivo AutoBackoffice.py NÃO encontrado"
    echo "Você precisará copiar o arquivo para:"
    echo "  ./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py"
fi

# 4. Ajustar permissões
echo ""
echo "4. Ajustando permissões..."
chmod -R 755 ./ProjetosVS 2>/dev/null || true
chmod -R 755 ./dags ./logs ./plugins 2>/dev/null || true
echo -e "${GREEN}✓${NC} Permissões ajustadas"

# 5. Parar containers existentes
echo ""
echo "5. Parando containers existentes..."
if [ -f "docker-compose.yml" ]; then
    docker-compose down 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Containers parados"
else
    echo -e "${YELLOW}⚠${NC} Nenhum docker-compose.yml encontrado"
fi

# 6. Iniciar novo container
echo ""
echo "6. Iniciando Airflow..."
if [ -f "docker-compose.yml" ]; then
    docker-compose up -d
    echo -e "${GREEN}✓${NC} Airflow iniciado"
    echo ""
    echo "Aguardando inicialização (pode levar até 90 segundos)..."
    sleep 10
else
    echo -e "${RED}✗${NC} docker-compose.yml não encontrado"
    exit 1
fi

# 7. Exibir status
echo ""
echo "===== STATUS ====="
docker-compose ps

# 8. Instruções finais
echo ""
echo "===== PRÓXIMOS PASSOS ====="
echo ""
echo "1. Aguarde a inicialização completa do Airflow (até 90 segundos)"
echo "2. Acesse: http://localhost:8081"
echo "3. Login: admin / admin"
echo "4. Execute a DAG 'test_volumes' para verificar os volumes"
echo "5. Se tudo estiver OK, execute 'Atualiza_BackOffice'"
echo ""
echo "Para ver os logs em tempo real:"
echo "  docker-compose logs -f"
echo ""
echo "Para verificar volumes dentro do container:"
echo "  docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/"
echo ""
echo -e "${GREEN}✓${NC} Configuração concluída!"
