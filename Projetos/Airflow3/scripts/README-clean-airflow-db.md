# Limpar `airflow.db` (historico de execucao)

Remove apenas o **historico de runs** (logs, task_instance, dag_run, etc.) para reduzir o tamanho do SQLite.

## O que NAO e apagado

| Item | Onde fica | Seguro? |
|------|-----------|---------|
| Senhas e conexoes (`postgres`, `postgres_otto`) | tabela `connection` no `airflow.db` | Sim — preservada |
| Variaveis do Airflow | tabela `variable` | Sim — preservada |
| Usuarios (admin, etc.) | tabelas `ab_user` / `ab_role` | Sim — preservadas |
| Arquivos das DAGs (`.py`) | `PROJETOS\Airflow3\dags\` (volume Docker) | Sim — nem passam pelo script |

O script verifica a contagem de linhas em `connection`, `variable`, `ab_user`, `dag` e `serialized_dag` **antes e depois**. Se algo mudar, aborta sem devolver o banco ao container.

## Como rodar (recomendado)

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\Airflow3\scripts
.\Run-CleanAirflowDb.ps1
```

O script vai:
1. Pedir confirmacao (`SIM`)
2. Parar o container `airflow3-standalone`
3. Copiar o `airflow.db` para fora
4. Salvar backup em `scripts\backups\airflow_YYYYMMDD_HHMMSS.db`
5. Limpar apenas tabelas de historico
6. Devolver o banco e reiniciar o container

Simular sem alterar nada:

```powershell
.\Run-CleanAirflowDb.ps1 -WhatIf
```

## Reverter (se necessario)

```powershell
docker stop airflow3-standalone
docker cp "e:\Projetos\VS_Code\Melnick\PROJETOS\Airflow3\scripts\backups\airflow_20260613_120000.db" airflow3-standalone:/opt/airflow/airflow.db
docker start airflow3-standalone
docker exec -u root airflow3-standalone chown airflow:root /opt/airflow/airflow.db
docker exec -u root airflow3-standalone chmod 664 /opt/airflow/airflow.db
```

(substitua pelo nome real do backup em `scripts\backups\`)

**Importante:** apos qualquer `docker cp` do `airflow.db`, ajuste o dono para `airflow` — senao a UI retorna **500 Internal Server Error** ao disparar DAGs (`readonly database`).

## Tabelas limpas (nesta ordem)

`log` → `task_fail` → `task_instance` → `dag_run` → `job` → (extras do Airflow 3, se existirem)

Usa `PRAGMA foreign_keys=OFF` durante o DELETE, valida tabelas preservadas e depois `VACUUM`.

## Caminho customizado (manual)

```powershell
python clean_airflow_db.py "D:\backup\airflow.db"
```

Ou no container (com Airflow parado):

```bash
AIRFLOW_DB_PATH=/opt/airflow/airflow.db python3 clean_airflow_db.py
```

## Pre-requisitos

- Docker Desktop rodando
- Container `airflow3-standalone` ja criado (`docker compose up -d` em `PROJETOS\Airflow3`)
- Python 3 no Windows (`python` ou `py -3`)
