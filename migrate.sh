#!/bin/bash

# Script de migração do ambiente antigo (Windows) para Linux

set -e

echo "===== MIGRAÇÃO DE AMBIENTE AIRFLOW ====="
echo ""
echo "Este script irá migrar seu ambiente Airflow de Windows para Linux"
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Verificar se está no ambiente correto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}✗ docker-compose.yml não encontrado${NC}"
    echo "Execute este script no diretório onde está o docker-compose.yml"
    exit 1
fi

# 1. Fazer backup do docker-compose antigo
echo -e "${BLUE}1. Fazendo backup do docker-compose.yml antigo...${NC}"
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}✓${NC} Backup criado"
else
    echo -e "${YELLOW}⚠${NC} Nenhum arquivo para fazer backup"
fi

# 2. Parar containers existentes
echo ""
echo -e "${BLUE}2. Parando containers existentes...${NC}"
docker-compose down 2>/dev/null || true
echo -e "${GREEN}✓${NC} Containers parados"

# 3. Perguntar onde estão os arquivos
echo ""
echo -e "${BLUE}3. Localização dos arquivos${NC}"
echo ""
echo "Onde estão seus arquivos Melnick-Code?"
echo ""
echo "Opções comuns:"
echo "1) /mnt/e/Projetos/VS_Code/Melnick-Code (WSL - E:)"
echo "2) /mnt/c/Users/$USER/Projetos/Melnick-Code (WSL - C:)"
echo "3) /home/$USER/Projetos/Melnick-Code (Linux nativo)"
echo "4) Outro caminho (você digitará)"
echo "5) Copiar manualmente depois"
echo ""

read -p "Escolha uma opção (1-5): " choice

SOURCE_PATH=""

case $choice in
    1)
        SOURCE_PATH="/mnt/e/Projetos/VS_Code/Melnick-Code"
        ;;
    2)
        SOURCE_PATH="/mnt/c/Users/$USER/Projetos/Melnick-Code"
        ;;
    3)
        SOURCE_PATH="/home/$USER/Projetos/Melnick-Code"
        ;;
    4)
        read -p "Digite o caminho completo: " SOURCE_PATH
        ;;
    5)
        echo -e "${YELLOW}⚠${NC} Você precisará copiar os arquivos manualmente"
        SOURCE_PATH=""
        ;;
    *)
        echo -e "${RED}✗ Opção inválida${NC}"
        exit 1
        ;;
esac

# 4. Criar estrutura de diretórios
echo ""
echo -e "${BLUE}4. Criando estrutura de diretórios...${NC}"
mkdir -p dags logs plugins ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
echo -e "${GREEN}✓${NC} Diretórios criados"

# 5. Copiar ou linkar arquivos
if [ -n "$SOURCE_PATH" ]; then
    echo ""
    echo -e "${BLUE}5. Copiando/linkando arquivos...${NC}"
    
    if [ ! -d "$SOURCE_PATH" ]; then
        echo -e "${RED}✗ Diretório não encontrado: $SOURCE_PATH${NC}"
        echo "Você precisará copiar os arquivos manualmente para:"
        echo "  ./ProjetosVS/Melnick-Code/"
    else
        echo "Como você quer adicionar os arquivos?"
        echo "1) Link simbólico (recomendado - não duplica arquivos)"
        echo "2) Copiar (cria cópia local)"
        read -p "Escolha (1/2): " link_choice
        
        case $link_choice in
            1)
                ln -sf "$SOURCE_PATH" ./ProjetosVS/Melnick-Code
                echo -e "${GREEN}✓${NC} Link simbólico criado"
                ;;
            2)
                cp -r "$SOURCE_PATH"/* ./ProjetosVS/Melnick-Code/
                echo -e "${GREEN}✓${NC} Arquivos copiados"
                ;;
            *)
                echo -e "${RED}✗ Opção inválida${NC}"
                ;;
        esac
    fi
else
    echo ""
    echo -e "${YELLOW}⚠${NC} Copie seus arquivos manualmente para: ./ProjetosVS/Melnick-Code/"
fi

# 6. Verificar estrutura
echo ""
echo -e "${BLUE}6. Verificando estrutura...${NC}"

if [ -f "./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py" ]; then
    echo -e "${GREEN}✓${NC} Arquivo AutoBackoffice.py encontrado"
    STRUCTURE_OK=true
else
    echo -e "${YELLOW}⚠${NC} Arquivo AutoBackoffice.py não encontrado"
    echo "Certifique-se de copiar o arquivo para:"
    echo "  ./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py"
    STRUCTURE_OK=false
fi

# 7. Ajustar permissões
echo ""
echo -e "${BLUE}7. Ajustando permissões...${NC}"
chmod -R 755 ./ProjetosVS ./dags ./logs ./plugins 2>/dev/null || true
echo -e "${GREEN}✓${NC} Permissões ajustadas"

# 8. Copiar DAGs migradas
echo ""
echo -e "${BLUE}8. Verificando DAGs...${NC}"
if [ ! -f "./dags/AtualizaBackOffice.py" ]; then
    echo -e "${YELLOW}⚠${NC} DAG AtualizaBackOffice.py não encontrada"
    echo "A DAG será criada automaticamente"
else
    echo -e "${GREEN}✓${NC} DAGs encontradas"
fi

# 9. Atualizar docker-compose.yml se necessário
echo ""
echo -e "${BLUE}9. Verificando docker-compose.yml...${NC}"
if grep -q "E:/Projetos" docker-compose.yml 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} docker-compose.yml ainda tem caminhos Windows"
    echo "Será necessário atualizar manualmente ou executar ./setup.sh"
else
    echo -e "${GREEN}✓${NC} docker-compose.yml OK"
fi

# 10. Iniciar novo ambiente
echo ""
echo -e "${BLUE}10. Deseja iniciar o Airflow agora?${NC}"
read -p "Iniciar? (s/n): " start_now

if [[ "$start_now" =~ ^[Ss]$ ]]; then
    echo ""
    echo "Iniciando Airflow..."
    docker-compose up -d
    echo -e "${GREEN}✓${NC} Airflow iniciado"
    echo ""
    echo "Aguardando inicialização..."
    sleep 10
fi

# Resumo final
echo ""
echo "===== RESUMO DA MIGRAÇÃO ====="
echo ""

if [ "$STRUCTURE_OK" = true ]; then
    echo -e "${GREEN}✓ Estrutura de arquivos OK${NC}"
else
    echo -e "${YELLOW}⚠ Você precisa copiar os arquivos manualmente${NC}"
fi

echo ""
echo "Estrutura esperada:"
echo "/workspace/"
echo "├── docker-compose.yml"
echo "├── dags/"
echo "│   ├── AtualizaBackOffice.py"
echo "│   └── test_volumes.py"
echo "├── logs/"
echo "├── plugins/"
echo "└── ProjetosVS/"
echo "    └── Melnick-Code/"
echo "        └── Projetos/"
echo "            └── AutoBackoffice/"
echo "                └── AutoBackoffice.py"

echo ""
echo "===== PRÓXIMOS PASSOS ====="
echo ""
echo "1. Execute './verify.sh' para verificar o ambiente"
echo "2. Acesse http://localhost:8081 (usuário: admin / senha: admin)"
echo "3. Execute a DAG 'test_volumes' para testar os volumes"
echo "4. Se tudo OK, execute 'Atualiza_BackOffice'"
echo ""
echo "Para ver logs:"
echo "  docker-compose logs -f"
echo ""
echo -e "${GREEN}✓ Migração concluída!${NC}"
