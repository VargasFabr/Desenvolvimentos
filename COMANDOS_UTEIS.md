# 📝 Comandos Úteis - Airflow 3

## 🚀 Início Rápido

```bash
# Configuração automática (primeira vez)
./setup.sh

# Verificar ambiente
./verify.sh

# Migrar de Windows para Linux
./migrate.sh
```

## 🐳 Docker Compose

### Gerenciamento Básico

```bash
# Iniciar Airflow
docker-compose up -d

# Parar Airflow
docker-compose down

# Reiniciar Airflow
docker-compose restart

# Ver status dos containers
docker-compose ps

# Ver logs em tempo real
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f airflow-standalone

# Parar e remover tudo (inclusive volumes)
docker-compose down -v
```

### Build e Atualização

```bash
# Rebuild do container (após mudar docker-compose.yml)
docker-compose up -d --build

# Forçar recriação do container
docker-compose up -d --force-recreate

# Puxar imagem mais recente
docker-compose pull
docker-compose up -d
```

## 🔍 Diagnóstico

### Verificar Volumes

```bash
# No host (seu computador)
ls -la ./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/

# Dentro do container
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/

# Buscar arquivo específico
docker exec airflow3-standalone find /opt/airflow -name "AutoBackoffice.py"

# Ver estrutura completa
docker exec airflow3-standalone tree /opt/airflow/ProjetosVS/
```

### Verificar Configuração

```bash
# Ver configuração do Airflow
docker exec airflow3-standalone airflow config list

# Ver variáveis de ambiente
docker exec airflow3-standalone env | grep AIRFLOW

# Ver versão do Airflow
docker exec airflow3-standalone airflow version
```

### Ver Processos

```bash
# Processos dentro do container
docker exec airflow3-standalone ps aux

# Ver uso de recursos
docker stats airflow3-standalone

# Inspecionar container
docker inspect airflow3-standalone
```

## 🐛 Debug

### Entrar no Container

```bash
# Bash interativo
docker exec -it airflow3-standalone bash

# Executar comando único
docker exec airflow3-standalone ls -la /opt/airflow/

# Como root (se precisar de permissões elevadas)
docker exec -it -u root airflow3-standalone bash
```

### Dentro do Container

```bash
# Ver logs do Airflow
cd /opt/airflow/logs
tail -f scheduler/latest/*.log

# Testar Python
python -c "import sys; print(sys.path)"

# Verificar DAGs
airflow dags list

# Ver detalhes de uma DAG
airflow dags show Atualiza_BackOffice

# Testar DAG
airflow dags test Atualiza_BackOffice 2025-12-30

# Ver tasks de uma DAG
airflow tasks list Atualiza_BackOffice

# Executar task manualmente
airflow tasks test Atualiza_BackOffice Atualiza_BackOffice 2025-12-30
```

## 📊 DAGs

### Gerenciar DAGs

```bash
# Listar DAGs
docker exec airflow3-standalone airflow dags list

# Pausar DAG
docker exec airflow3-standalone airflow dags pause Atualiza_BackOffice

# Retomar DAG
docker exec airflow3-standalone airflow dags unpause Atualiza_BackOffice

# Executar DAG manualmente
docker exec airflow3-standalone airflow dags trigger Atualiza_BackOffice

# Ver próximas execuções
docker exec airflow3-standalone airflow dags next-execution Atualiza_BackOffice
```

### Ver Execuções

```bash
# Listar execuções de uma DAG
docker exec airflow3-standalone airflow dags list-runs -d Atualiza_BackOffice

# Ver estado de uma execução
docker exec airflow3-standalone airflow dags state Atualiza_BackOffice run_id estado
```

## 👤 Usuários

### Gerenciar Usuários

```bash
# Listar usuários
docker exec airflow3-standalone airflow users list

# Criar novo usuário
docker exec airflow3-standalone airflow users create \
    --username novousuario \
    --firstname Nome \
    --lastname Sobrenome \
    --role Admin \
    --email email@exemplo.com

# Alterar senha
docker exec airflow3-standalone airflow users reset-password \
    --username admin

# Deletar usuário
docker exec airflow3-standalone airflow users delete --username usuario
```

## 📦 Dependências Python

### Instalar Pacotes

```bash
# Método 1: Adicionar ao requirements.txt e rebuild
echo "pandas==2.1.4" >> requirements.txt
docker-compose restart

# Método 2: Instalar temporariamente (perdido ao reiniciar)
docker exec airflow3-standalone pip install pandas

# Método 3: Instalar dentro do container permanentemente
docker exec -it airflow3-standalone bash
pip install pandas
exit
# Depois adicione ao requirements.txt para manter
```

### Ver Pacotes Instalados

```bash
# Listar todos os pacotes
docker exec airflow3-standalone pip list

# Ver versão de um pacote específico
docker exec airflow3-standalone pip show airflow

# Verificar dependências
docker exec airflow3-standalone pip check
```

## 🔐 Permissões

### Ajustar Permissões (Host)

```bash
# Dar permissão de leitura/escrita
chmod -R 755 ./ProjetosVS ./dags ./logs ./plugins

# Mudar proprietário
chown -R $USER:$USER ./ProjetosVS ./dags ./logs ./plugins

# Verificar permissões
ls -la ./ProjetosVS/
```

### Ajustar Permissões (Container)

```bash
# Como root
docker exec -it -u root airflow3-standalone bash

# Dentro do container
chown -R airflow:root /opt/airflow/ProjetosVS
chmod -R 755 /opt/airflow/ProjetosVS
exit
```

## 🌐 Rede

### Verificar Conectividade

```bash
# Testar se Airflow está respondendo
curl http://localhost:8081/health

# Ver porta mapeada
docker port airflow3-standalone

# Testar conexão de dentro do container
docker exec airflow3-standalone curl http://localhost:8080/health
```

### Problemas de Porta

```bash
# Ver o que está usando a porta 8081
sudo lsof -i :8081

# Ou com netstat
netstat -tulpn | grep 8081

# Matar processo usando a porta
sudo kill -9 $(lsof -t -i:8081)
```

## 🗄️ Banco de Dados

### SQLite (padrão)

```bash
# Acessar banco de dados
docker exec -it airflow3-standalone sqlite3 /opt/airflow/airflow.db

# Dentro do sqlite3
.tables              # Listar tabelas
.schema dag         # Ver schema de uma tabela
SELECT * FROM dag;  # Query
.quit               # Sair
```

### Backup do Banco

```bash
# Fazer backup
docker cp airflow3-standalone:/opt/airflow/airflow.db ./backup_airflow.db

# Restaurar backup
docker cp ./backup_airflow.db airflow3-standalone:/opt/airflow/airflow.db
docker-compose restart
```

## 🧹 Limpeza

### Limpar Logs Antigos

```bash
# Limpar logs do host
find ./logs -type f -name "*.log" -mtime +30 -delete

# Limpar logs do container
docker exec airflow3-standalone find /opt/airflow/logs -type f -name "*.log" -mtime +30 -delete
```

### Limpar Docker

```bash
# Remover containers parados
docker container prune

# Remover imagens não utilizadas
docker image prune

# Remover volumes não utilizados
docker volume prune

# Limpar tudo (CUIDADO!)
docker system prune -a --volumes
```

## 📈 Monitoramento

### Recursos do Container

```bash
# Ver uso de CPU/memória em tempo real
docker stats airflow3-standalone

# Ver uso de disco
docker exec airflow3-standalone df -h

# Ver uso de inodes
docker exec airflow3-standalone df -i
```

### Logs de Sistema

```bash
# Journalctl (systemd)
sudo journalctl -u docker -f

# Ver logs do Docker daemon
sudo tail -f /var/log/docker.log
```

## 🔄 Backup e Restore

### Backup Completo

```bash
# Criar backup de tudo
tar -czf airflow-backup-$(date +%Y%m%d).tar.gz \
    dags/ \
    logs/ \
    plugins/ \
    ProjetosVS/ \
    docker-compose.yml \
    requirements.txt

# Backup do banco de dados
docker cp airflow3-standalone:/opt/airflow/airflow.db ./airflow.db.backup
```

### Restore

```bash
# Extrair backup
tar -xzf airflow-backup-20251230.tar.gz

# Restaurar banco
docker cp ./airflow.db.backup airflow3-standalone:/opt/airflow/airflow.db

# Reiniciar
docker-compose restart
```

## 🆘 Troubleshooting Rápido

```bash
# Container não inicia
docker-compose logs airflow-standalone
docker-compose down -v && docker-compose up -d

# DAG não aparece
docker exec airflow3-standalone airflow dags list
docker-compose restart

# Erro de permissão
chmod -R 755 ./dags ./logs ./plugins
docker-compose restart

# Volume não montado
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/
./verify.sh

# Porta em uso
sudo lsof -i :8081
docker-compose down && docker-compose up -d

# Problema de memória
docker stats
# Aumentar memória do Docker Desktop (Settings > Resources)

# Reset completo
docker-compose down -v
rm -rf logs/*
docker-compose up -d
```

## 📚 Referências Rápidas

```bash
# Ver todos os comandos Airflow
docker exec airflow3-standalone airflow --help

# Ver comandos de DAG
docker exec airflow3-standalone airflow dags --help

# Ver comandos de tasks
docker exec airflow3-standalone airflow tasks --help

# Ver comandos de usuários
docker exec airflow3-standalone airflow users --help

# Documentação oficial
# https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-variables-ref.html
```

## 💡 Dicas

1. Use `./verify.sh` regularmente para verificar o ambiente
2. Sempre veja os logs com `-f` (follow) para debug em tempo real
3. Use `docker exec -it` para entrar interativamente no container
4. Faça backup antes de mudanças grandes
5. Use `docker-compose down -v` apenas se quiser apagar TUDO
6. Adicione pacotes Python ao `requirements.txt` para persistir
7. Use caminhos relativos (`.`) no docker-compose.yml para portabilidade

## ⚡ Atalhos Úteis

```bash
# Alias úteis (adicione ao ~/.bashrc)
alias aup='docker-compose up -d'
alias adown='docker-compose down'
alias arestart='docker-compose restart'
alias alogs='docker-compose logs -f'
alias ashell='docker exec -it airflow3-standalone bash'
alias averify='./verify.sh'
```

Depois de adicionar, recarregue o bash:
```bash
source ~/.bashrc
```
