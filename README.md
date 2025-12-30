# Airflow 3 - Projeto Melnick

Sistema de automação com Apache Airflow 3 para execução de tarefas agendadas.

## 🔴 Problema Resolvido

**Erro original:** Volume não montado - caminhos Windows (`E:/Projetos/...`) não funcionam em Linux.

**Solução:** Usar caminhos Linux relativos ou absolutos.

## 🚀 Início Rápido

### Opção 1: Configuração Automática (Recomendado)

```bash
# Executar script de configuração
./setup.sh
```

O script irá:
1. Criar estrutura de diretórios
2. Buscar automaticamente seus projetos
3. Configurar links simbólicos ou copiar arquivos
4. Iniciar o Airflow
5. Exibir instruções de acesso

### Opção 2: Configuração Manual

```bash
# 1. Criar diretórios
mkdir -p ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
mkdir -p dags logs plugins

# 2. Copiar seus projetos
cp -r /caminho/para/Melnick-Code/* ./ProjetosVS/Melnick-Code/

# 3. Iniciar Airflow
docker-compose up -d

# 4. Ver logs
docker-compose logs -f
```

## 📁 Estrutura do Projeto

```
/workspace/
├── docker-compose.yml       # Configuração Docker (CORRIGIDA)
├── setup.sh                 # Script de configuração automática
├── SOLUCAO.md              # Documentação detalhada da solução
├── requirements.txt        # Dependências Python
├── dags/
│   ├── AtualizaBackOffice.py   # DAG principal
│   └── test_volumes.py         # DAG de diagnóstico
├── logs/                   # Logs do Airflow
├── plugins/                # Plugins personalizados
└── ProjetosVS/            # Seus projetos (volume montado)
    └── Melnick-Code/
        └── Projetos/
            └── AutoBackoffice/
                └── AutoBackoffice.py
```

## 🔧 Configuração

### docker-compose.yml

Volume corrigido para Linux:

```yaml
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS  # ✓ Caminho relativo (funciona)
```

❌ **Não use caminhos Windows:**
```yaml
volumes:
  - E:/Projetos/VS_Code:/opt/airflow/ProjetosVS  # ✗ Não funciona em Linux
```

## 🧪 Testes

### 1. Testar Volumes

```bash
# Executar DAG de diagnóstico
# Acesse http://localhost:8081 e execute: test_volumes
```

### 2. Verificar Manualmente

```bash
# Entrar no container
docker exec -it airflow3-standalone bash

# Verificar volumes
ls -la /opt/airflow/ProjetosVS/
ls -la /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/

# Sair do container
exit
```

## 📊 DAGs Disponíveis

### 1. Atualiza_BackOffice
- **Descrição:** Executa script de atualização do BackOffice
- **Agendamento:** 5 minutos após cada hora, das 8h às 18h, de segunda a sábado
- **Cron:** `5 8-18 * * 1-6`

### 2. test_volumes (Diagnóstico)
- **Descrição:** Verifica se todos os volumes estão montados corretamente
- **Agendamento:** Manual
- **Uso:** Execute esta DAG primeiro para diagnosticar problemas

## 🌐 Acesso

- **URL:** http://localhost:8081
- **Usuário:** admin
- **Senha:** admin

## 📝 Logs

```bash
# Ver logs em tempo real
docker-compose logs -f

# Ver logs de container específico
docker-compose logs -f airflow-standalone

# Ver logs de uma DAG específica
# Acesse via interface web: Airflow UI > DAGs > Logs
```

## 🐛 Troubleshooting

### Problema: Volume não montado

**Sintoma:**
```
ERRO: Diretório não encontrado
Volume ProjetosVS não montado
```

**Solução:**
```bash
# 1. Verificar se diretório existe
ls -la ./ProjetosVS/Melnick-Code/

# 2. Se não existir, criar
mkdir -p ProjetosVS/Melnick-Code/Projetos/AutoBackoffice

# 3. Copiar arquivos
cp -r /seu/caminho/* ./ProjetosVS/Melnick-Code/

# 4. Reiniciar container
docker-compose restart
```

### Problema: Permissão negada

```bash
# Ajustar permissões
chmod -R 755 ./ProjetosVS
chown -R $USER:$USER ./ProjetosVS ./dags ./logs ./plugins
```

### Problema: Container não inicia

```bash
# Ver logs detalhados
docker-compose logs airflow-standalone

# Reiniciar do zero
docker-compose down -v
docker-compose up -d
```

### Problema: Arquivo Python não encontrado

```bash
# Verificar dentro do container
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/

# Buscar arquivo
docker exec airflow3-standalone find /opt/airflow -name "AutoBackoffice.py"
```

## 📚 Documentação Adicional

- [SOLUCAO.md](./SOLUCAO.md) - Documentação detalhada da solução
- [Airflow 3 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/)
- [Docker Compose](https://docs.docker.com/compose/)

## 🔄 Comandos Úteis

```bash
# Iniciar
docker-compose up -d

# Parar
docker-compose down

# Reiniciar
docker-compose restart

# Ver status
docker-compose ps

# Ver logs
docker-compose logs -f

# Entrar no container
docker exec -it airflow3-standalone bash

# Limpar tudo (CUIDADO: remove volumes)
docker-compose down -v
```

## ⚠️ Notas Importantes

1. **Sistema Operacional:** Este projeto está configurado para **Linux**
2. **Caminhos:** Use sempre caminhos Linux (não use `E:/` ou `C:/`)
3. **Volumes:** Prefira caminhos relativos (`./`) para portabilidade
4. **Permissões:** Garanta que o usuário tenha permissão de leitura nos diretórios montados
5. **WSL:** Se estiver usando WSL, use `/mnt/e/` em vez de `E:/`

## 🤝 Contribuindo

Para adicionar novas DAGs:

1. Criar arquivo Python em `./dags/`
2. Importar as bibliotecas necessárias do Airflow
3. Definir a DAG com parâmetros adequados
4. Testar com a interface web

## 📄 Licença

Projeto interno Melnick.
