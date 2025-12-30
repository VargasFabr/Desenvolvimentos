#!/bin/bash

# Script de verificação rápida do ambiente Airflow

echo "===== VERIFICAÇÃO DO AMBIENTE AIRFLOW ====="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Contador de problemas
ISSUES=0

# 1. Verificar se docker-compose existe
echo -n "1. docker-compose.yml... "
if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

# 2. Verificar estrutura de diretórios
echo -n "2. Diretório dags/... "
if [ -d "dags" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

echo -n "3. Diretório logs/... "
if [ -d "logs" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

echo -n "4. Diretório plugins/... "
if [ -d "plugins" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

echo -n "5. Diretório ProjetosVS/... "
if [ -d "ProjetosVS" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Não encontrado (será criado)${NC}"
fi

# 3. Verificar DAGs
echo -n "6. DAG AtualizaBackOffice.py... "
if [ -f "dags/AtualizaBackOffice.py" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

echo -n "7. DAG test_volumes.py... "
if [ -f "dags/test_volumes.py" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Não encontrado${NC}"
    ((ISSUES++))
fi

# 4. Verificar projeto
echo -n "8. Projeto AutoBackoffice.py... "
if [ -f "ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Não encontrado (precisa ser copiado)${NC}"
fi

# 5. Verificar Docker
echo -n "9. Docker instalado... "
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Docker não encontrado${NC}"
    ((ISSUES++))
fi

echo -n "10. Docker Compose instalado... "
if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Docker Compose não encontrado${NC}"
    ((ISSUES++))
fi

# 6. Verificar container
echo -n "11. Container Airflow rodando... "
if docker ps | grep -q "airflow3-standalone"; then
    echo -e "${GREEN}✓${NC}"
    CONTAINER_RUNNING=true
else
    echo -e "${YELLOW}⚠ Container não está rodando${NC}"
    CONTAINER_RUNNING=false
fi

# 7. Se container está rodando, verificar volumes
if [ "$CONTAINER_RUNNING" = true ]; then
    echo ""
    echo -e "${BLUE}=== VERIFICAÇÃO DENTRO DO CONTAINER ===${NC}"
    
    echo -n "12. Volume ProjetosVS montado... "
    if docker exec airflow3-standalone test -d /opt/airflow/ProjetosVS 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ Não montado${NC}"
        ((ISSUES++))
    fi
    
    echo -n "13. Diretório Melnick-Code... "
    if docker exec airflow3-standalone test -d /opt/airflow/ProjetosVS/Melnick-Code 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ Não encontrado${NC}"
    fi
    
    echo -n "14. Arquivo AutoBackoffice.py... "
    if docker exec airflow3-standalone test -f /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ Não encontrado${NC}"
    fi
    
    echo -n "15. Webserver acessível... "
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ Não acessível (pode estar iniciando)${NC}"
    fi
fi

# Resumo
echo ""
echo "===== RESUMO ====="
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✓ Tudo OK! Nenhum problema encontrado.${NC}"
    echo ""
    echo "Próximos passos:"
    echo "1. Acesse: http://localhost:8081"
    echo "2. Login: admin / admin"
    echo "3. Execute a DAG 'test_volumes' para diagnóstico"
else
    echo -e "${RED}✗ $ISSUES problema(s) encontrado(s)${NC}"
    echo ""
    echo "Execute './setup.sh' para configurar o ambiente automaticamente"
fi

# Informações adicionais se container está rodando
if [ "$CONTAINER_RUNNING" = true ]; then
    echo ""
    echo "===== INFORMAÇÕES DO CONTAINER ====="
    echo "Status:"
    docker-compose ps 2>/dev/null || docker ps | grep airflow3-standalone
    echo ""
    echo "Para ver logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "Para entrar no container:"
    echo "  docker exec -it airflow3-standalone bash"
fi

echo ""
