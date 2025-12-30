# Solução para Problema de Volume Não Montado no Airflow 3

## Problema Identificado

Você está executando **Linux** mas tentando montar volumes com caminhos do **Windows** (`E:/Projetos/...`). Isso não funciona!

### Erro Original
```
ERRO: Diretório não encontrado: /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
Volume ProjetosVS não montado
```

### Causa
No `docker-compose.yml` original:
```yaml
volumes:
  - E:/Projetos/VS_Code:/opt/airflow/ProjetosVS  # ❌ Caminho Windows em sistema Linux
```

## Solução Implementada

### 1. Criar Estrutura de Diretórios

Primeiro, crie a estrutura necessária no seu workspace:

```bash
# No diretório onde está o docker-compose.yml
mkdir -p ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
mkdir -p dags logs plugins
```

### 2. Copiar Seus Arquivos

Copie seus projetos para o diretório local:

```bash
# Opção A: Se os arquivos estão em outra partição/disco
cp -r /caminho/para/seus/projetos/Melnick-Code/* ./ProjetosVS/Melnick-Code/

# Opção B: Criar link simbólico (se os arquivos estão acessíveis)
ln -s /caminho/real/para/Melnick-Code ./ProjetosVS/Melnick-Code
```

### 3. Ajustar docker-compose.yml

O arquivo `docker-compose.yml` foi corrigido para usar caminhos relativos (Linux):

```yaml
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS  # ✓ Caminho relativo funciona em Linux
```

**Alternativa**: Se você quer usar caminhos absolutos Linux:

```yaml
volumes:
  - /home/seu-usuario/Projetos/VS_Code:/opt/airflow/ProjetosVS
```

### 4. Estrutura Esperada

Seu workspace deve ficar assim:

```
/workspace/
├── docker-compose.yml
├── dags/
│   ├── AtualizaBackOffice.py
│   └── test_volumes.py
├── logs/
├── plugins/
├── requirements.txt
└── ProjetosVS/
    └── Melnick-Code/
        └── Projetos/
            └── AutoBackoffice/
                └── AutoBackoffice.py
```

## Passos para Resolver

### 1. Parar o Container Atual
```bash
docker-compose down
```

### 2. Criar Diretórios
```bash
mkdir -p ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
mkdir -p dags logs plugins
```

### 3. Copiar Seus Arquivos
```bash
# Ajuste o caminho de origem conforme necessário
cp -r /seu/caminho/Melnick-Code/* ./ProjetosVS/Melnick-Code/
```

### 4. Iniciar o Container
```bash
docker-compose up -d
```

### 5. Verificar os Logs
```bash
docker-compose logs -f
```

### 6. Testar com DAG de Diagnóstico

1. Acesse o Airflow em `http://localhost:8081`
2. Login: `admin` / `admin`
3. Execute a DAG `test_volumes` (manual)
4. Verifique os logs para confirmar que os volumes estão montados

### 7. Executar Sua DAG

Após confirmar que os volumes estão corretos, execute a DAG `Atualiza_BackOffice`.

## Opções de Montagem de Volume

### Opção 1: Usar Diretório Local (Recomendado)
```yaml
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS
```

**Vantagens:**
- Funciona em qualquer sistema operacional
- Portável
- Fácil de versionar com Git

### Opção 2: Usar Caminho Absoluto Linux
```yaml
volumes:
  - /home/usuario/Projetos:/opt/airflow/ProjetosVS
```

**Vantagens:**
- Acessa arquivos em qualquer lugar do sistema
- Não duplica arquivos

**Desvantagens:**
- Não portável entre máquinas
- Específico do sistema

### Opção 3: Usar Link Simbólico
```bash
ln -s /home/usuario/Projetos/Melnick-Code ./ProjetosVS/Melnick-Code
```

**Vantagens:**
- Mantém arquivo único
- Funciona com volumes relativos

## Problemas Comuns

### 1. "Permission denied"
```bash
# Dar permissões corretas
chmod -R 755 ./ProjetosVS
chown -R $USER:$USER ./ProjetosVS
```

### 2. "Volume not found"
```bash
# Verificar se o diretório existe
ls -la ./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/
```

### 3. Container não inicia
```bash
# Ver logs detalhados
docker-compose logs airflow-standalone
```

### 4. Arquivo não encontrado dentro do container
```bash
# Entrar no container e verificar
docker exec -it airflow3-standalone bash
ls -la /opt/airflow/ProjetosVS/
```

## Verificação Final

Execute estes comandos para verificar se está tudo correto:

```bash
# 1. Verificar estrutura local
tree -L 4 ProjetosVS/

# 2. Verificar dentro do container
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/

# 3. Verificar se o arquivo Python existe
docker exec airflow3-standalone test -f /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/AutoBackoffice.py && echo "Arquivo encontrado!" || echo "Arquivo NÃO encontrado!"
```

## Dicas Adicionais

1. **Sempre use caminhos Linux** quando estiver executando em Linux (mesmo dentro do WSL)
2. **Evite caminhos do Windows** como `E:/`, `C:/` em sistemas Linux
3. **Use caminhos relativos** (`./`) sempre que possível para portabilidade
4. **Teste com a DAG de diagnóstico** antes de executar suas DAGs principais
5. **Verifique permissões** se tiver problemas de acesso

## Referências

- [Docker Compose Volumes](https://docs.docker.com/compose/compose-file/compose-file-v3/#volumes)
- [Airflow 3 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/)
