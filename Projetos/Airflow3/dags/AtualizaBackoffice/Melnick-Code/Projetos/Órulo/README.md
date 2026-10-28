# Atualização Órulo → Supabase

Pipeline de atualização de empreendimentos/tipologias/unidades da Órulo com persistência no Supabase.

## Estrutura

- `atualizacao_orulo.py`: orquestrador principal (entrada da execução).
- `orulo_pipeline_utils.py`: utilitários de paginação, merge, índices, deduplicação e limpeza.
- `orulo_region_files.py`: gravação de arquivos por região (`Última Atualização.txt` e `Empreendimentos com Erro.txt`).
- `orulo_backup.py`: backup em parquet.
- `orulo_diagnostic.py`: rotina opcional de diagnóstico de unidades.

## Fluxo de execução

1. Carrega variáveis de ambiente (`.env` do projeto e opcional externo).
2. Busca lista de empreendimentos por região na Órulo.
3. Busca dados relacionados no Supabase (buildings, typologies, units, units_updates).
4. Faz merge respeitando `lock_edit` e regras de priorização.
5. Deduplica, limpa payload e executa upserts em lote.
6. Atualiza arquivos de status por região.
7. Opcionalmente executa backup e diagnóstico.

## Variáveis de ambiente

### Obrigatórias

- `NEXT_PUBLIC_SUPABASE_URL` **ou** `SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` **ou** `SUPABASE_KEY` **ou** `SUPABASE_ANON_KEY`
- Credenciais da região ativa (ex.: `POA_RM_CLIENT_ID`, `POA_RM_CLIENT_SECRET`)

### Opcionais (execução)

- `ORULO_SUPABASE_ENV_PATH`: caminho para um `.env` externo.
- `ORULO_RUN_BACKUP` (`1`/`0`): habilita/desabilita backup.
- `ORULO_RUN_DIAGNOSTIC` (`1`/`0`): habilita/desabilita diagnóstico.
- `ORULO_BUILDING_REQUEST_DELAY` (float): delay entre requisições por empreendimento.
- `ORULO_TYPOLOGY_REQUEST_DELAY` (float): delay entre requisições por tipologia.
- `ORULO_TEST_BUILDING_ID` e `ORULO_TEST_TYPOLOGY_ID`: parâmetros do diagnóstico.

## Execução

Exemplo PowerShell:

```powershell
$env:ORULO_RUN_BACKUP='0'
$env:ORULO_RUN_DIAGNOSTIC='0'
$env:ORULO_BUILDING_REQUEST_DELAY='0.25'
$env:ORULO_TYPOLOGY_REQUEST_DELAY='0.1'
& C:/Users/pedroruppenthal/AppData/Local/anaconda3/envs/AutoBackoffice/python.exe "c:/Users/pedroruppenthal/Documents/Melnick Code/Melnick Code/Projetos/Órulo/atualizacao_orulo.py"
```

## Checklist pré-execução

- Confirmar que o ambiente Python correto está ativo (`AutoBackoffice`).
- Confirmar credenciais Supabase e Órulo no `.env` (ou `ORULO_SUPABASE_ENV_PATH`).
- Confirmar região(s) ativa(s) em `create_regions()`.
- Definir flags da execução (`ORULO_RUN_BACKUP`, `ORULO_RUN_DIAGNOSTIC`).
- Ajustar throttling para o cenário do dia (`ORULO_BUILDING_REQUEST_DELAY`, `ORULO_TYPOLOGY_REQUEST_DELAY`).
- Garantir acesso de escrita às pastas `Logs`, `Regiões` e `Arquivos/backup` (se backup habilitado).

## Checklist pós-execução

- Verificar `Exit Code` da execução (esperado: `0`).
- Conferir logs para erros de API/rate-limit e retries.
- Validar atualização de `Regiões/<REGIAO>/Última Atualização.txt`.
- Validar conteúdo de `Regiões/<REGIAO>/Empreendimentos com Erro.txt`.
- Confirmar volume de upserts no log (buildings, typologies, units, units_updates).
- Se backup habilitado, confirmar geração de arquivos em `Arquivos/backup/<YYYY_MM>/`.
- Se diagnóstico habilitado, confirmar saída sem erros para `ORULO_TEST_BUILDING_ID`/`ORULO_TEST_TYPOLOGY_ID`.

## Operação e troubleshooting

### Rate-limit da Órulo (Cloudflare 1015)

- Sintoma: erros 429/1015 durante `get_building`/`get_units`.
- Mitigação: aumentar `ORULO_BUILDING_REQUEST_DELAY` e `ORULO_TYPOLOGY_REQUEST_DELAY`.
  - Sugestão inicial: `0.3` a `0.6` (building), `0.1` a `0.2` (typology).

### Upsert com payload vazio

- O pipeline já possui guarda para não executar upsert com listas vazias.

### Falhas pontuais de API

- O processamento é protegido por `try/except` por empreendimento e por tipologia.
- Erros pontuais entram em log e não interrompem toda a execução.

## Saídas

- Logs: pasta `Logs` do projeto Órulo.
- Status por região:
  - `Regiões/<REGIAO>/Última Atualização.txt`
  - `Regiões/<REGIAO>/Empreendimentos com Erro.txt`
- Backups (se habilitado): `Arquivos/backup/<YYYY_MM>/*.parquet`
