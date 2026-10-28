# Histórico de debug: Previsao_Propostas (Prophet + pandas 3.x)

## Problema original

- **Erro:** `ValueError: cannot reindex on an axis with duplicate labels`
- **Contexto:** DAG `Previsao_Propostas` no Airflow; task `executar_previsao_propostas` falha em `model.fit(treino_fit)`.
- **Ambiente:** Airflow 3.1.3, Python 3.12, **pandas 3.0.1**, **Prophet 1.2.1** (no worker).
- **Referência:** `Previsao_Propostas_standalone.py` roda **sem erro** fora do Airflow (mesma lógica; ambiente local provavelmente com pandas 2.x).

## Cadeia do erro (traceback típico)

```
model.fit(treino_fit)
  → prophet/forecaster.py fit → preprocess → make_all_seasonality_features
  → regressor_column_matrix → pd.crosstab
  → pandas pivot.py crosstab → DataFrame(...) → dict_to_mgr → arrays_to_mgr
  → _homogenize → Series.reindex → Index.reindex
  → ValueError: cannot reindex on an axis with duplicate labels
```

O problema vem **de dentro do Prophet** (crosstab para sazonalidade), não dos dados de entrada. O DataFrame `treino_fit` já estava limpo (sem `ds` duplicados, índice único, sem colunas duplicadas — confirmado por logs).

---

## Modificações já tentadas (não repetir)

### 1. Limpeza do DataFrame de treino

- **O que foi feito:** `drop_duplicates(subset=['ds'])`, `sort_values('ds')`, `reset_index(drop=True)`, `RangeIndex`, construção via `pd.DataFrame({'ds': ds_arr, 'y': y_arr})`.
- **Resultado:** Dados já estavam limpos; erro persiste (é interno ao Prophet/pandas).

### 2. Ajustes no Prophet

- **O que foi feito:** Desligar yearly/weekly, usar `add_seasonality` manual, `growth='flat'` sem sazonalidade.
- **Resultado:** Erro continua (caminho interno do Prophet ainda usa crosstab/reindex).

### 3. Monkey-patch em `pd.crosstab`

- **O que foi feito:** Envolver `pd.crosstab` e passar `index`/`columns` únicos ao pandas.
- **Resultado:** Sumiu “duplicate labels” mas surgiu **`ValueError: All arrays must be of the same length`** (reduzir a índices únicos alterou tamanho dos arrays). **Patch revertido.**

### 4. Monkey-patch em `pandas.core.indexes.base.Index.reindex`

- **O que foi feito:** Em `try/except` ao capturar `ValueError` com "duplicate labels", chamar o `reindex` original com `self.unique()` e `target.unique()` (ou variantes).
- **Resultado:**  
  - Retornar indexer como posições em `self` (`indexer_u[inverse]`) → depois **`IndexError: indices are out-of-bounds`** (groupby usa o indexer em `.take()`; tamanho do array não batia).  
  - Retornar indexer como posições em `target_u` (`inverse`) → mesmo **out-of-bounds**.  
  - Retornar **indexer = np.arange(len(target))** (ordem identidade) → ainda **out-of-bounds** em outro ponto (groupby `_sorted_data` → `take(self._sort_idx)`).  
- **Conclusão (variantes com `target.unique()` + expansão de indexer):** alteravam semântica e quebravam `take()` no groupby. **Exceção:** em reavaliação posterior foi tentada **outra** variante em `Index.reindex` usando só `get_loc` por label em `target` (ver seção "Reavaliação do projeto") — distinta das tentativas acima.

### 5. Checagem de ambiente + mensagem clara

- **O que foi feito:** Se `pd.__version__.startswith('3.')`, levantar `RuntimeError` com mensagem indicando: (1) usar pandas>=2.0,<3 no ambiente, ou (2) atualizar Prophet para 1.3.0+.
- **Resultado:** Mensagem clara, mas task continua falhando até o ambiente ser corrigido.

### 6. Atualizar Prophet para 1.3.0+

- **O que foi feito:** Em `requirements.txt`, trocar `prophet==1.1.5` por `prophet>=1.3.0`; remover o `RuntimeError` por pandas 3.x.
- **Resultado:** Se o **ambiente ainda estiver com Prophet 1.2.x** (ou 1.1.5), o erro **"cannot reindex on an axis with duplicate labels"** volta, pois a causa é Prophet antigo + pandas 3.x. Ou seja: a solução correta é **garantir Prophet 1.3.0+ instalado no worker**; só mudar o `requirements.txt` não altera o container já em execução.

---

## Etapa: Rebuild da imagem Docker (2026-03-05)

### O que foi feito

- **Comando:** `docker build -t airflow-com-requirements E:\Airflow3`
- **Dockerfile:** Base `apache/airflow:3.1.3`; `COPY requirements.txt`; `RUN pip install --no-cache-dir -r /tmp/requirements.txt`
- **requirements.txt no build:** `prophet>=1.3.0`, `pandas>=2.0.0,<3.0.0`
- **Resultado do build:** Concluído com sucesso (135.4s).

### Resultado após subir versões do Prophet

- **Erro continua:** `ValueError: cannot reindex on an axis with duplicate labels` no mesmo ponto (`model.fit(treino_fit)` → Prophet `regressor_column_matrix` → `pd.crosstab` → pandas `reindex`).
- **Conclusão:** Na imagem ou no container em execução ainda está em uso **pandas 3.x** e/ou **Prophet < 1.3.0**. O `pip install -r requirements.txt` pode não ter feito downgrade do pandas se a **imagem base** `apache/airflow:3.1.3` ou o pacote `apache-airflow` exigir pandas 3.x (o pip não desce de 3 para 2.x nesse caso).

---

## Próxima etapa recomendada

1. **Confirmar qual imagem o container usa**  
   Garantir que o serviço (docker-compose ou comando `docker run`) está usando a imagem **`airflow-com-requirements`** (ou o nome correto da imagem que você deu no build). Se estiver usando `apache/airflow:3.1.3` sem o build customizado, as alterações do requirements não entram em efeito.

2. **Conferir versões dentro do container**  
   No container que executa as tasks (worker/scheduler), rodar:
   ```bash
   pip show pandas prophet
   ```
   Anotar as versões. Se aparecer `pandas 3.x` ou `Prophet 1.2.x` (ou menor), o ambiente ainda não está com as versões desejadas.

3. **Forçar pandas &lt; 3 no Dockerfile**  
   Se a base Airflow 3.1.3 puxar pandas 3 como dependência, adicionar no Dockerfile um passo que force a instalação de pandas 2.x **depois** do `pip install -r requirements.txt`, por exemplo:
   ```dockerfile
   RUN pip install --no-cache-dir -r /tmp/requirements.txt \
       && pip install --no-cache-dir "pandas>=2.0.0,<3.0.0"
   ```
   **Nota:** Esse passo já foi adicionado ao `Dockerfile` do projeto. Rebuild da imagem e uso da nova imagem no compose/run é a próxima etapa.

4. **Alternativa: subprocess com ambiente controlado**  
   Se não for possível manter pandas 2.x na imagem (por conflito com Airflow 3), considerar executar apenas o treino Prophet em um **subprocess** com um venv/ambiente que tenha apenas pandas 2.x e Prophet (ex.: script auxiliar chamado pela DAG). Documentado aqui apenas como opção; implementação seria mais trabalhosa.

---

## Etapa: Dockerfile com forçar pandas&lt;3 + novo rebuild (2026-03-05)

### O que foi feito

- **Dockerfile:** Adicionada linha para forçar pandas 2.x **depois** do requirements: `RUN pip install -r /tmp/requirements.txt && pip install "pandas>=2.0.0,<3.0.0"`.
- **Rebuild:** Imagem `airflow-com-requirements` reconstruída; containers recriados com essa imagem.
- **Resultado:** Erro **persiste** — `ValueError: cannot reindex on an axis with duplicate labels` no mesmo traceback.

### Conclusão

O passo extra no Dockerfile não fez o worker usar pandas 2.x (imagem base ou Airflow podem fixar pandas 3; ou o container ainda usa imagem antiga). **Próximo passo:** workaround no código — patch em `Series.reindex` deduplicando o Series antes de reindexar (sem alterar semântica do indexer).

---

## Próximos passos (após esta etapa)

1. **Verificar versões no container em execução**  
   `docker exec <container_worker> pip show pandas prophet` — confirmar se pandas 3.x segue instalado mesmo após o rebuild.
2. **Se quiser insistir no ambiente:** no Dockerfile, instalar pandas 2.x **antes** do requirements: `RUN pip install "pandas>=2.0,<3" && pip install -r /tmp/requirements.txt`.
3. **Workaround no código (este passo):** Patch em `Series.reindex`: se o Series tiver índice com duplicatas, deduplicar (keep='first') antes de chamar o reindex original; assim o pandas não levanta e não alteramos a semântica do indexer retornado. *(Se o erro continuar, a duplicata pode estar no índice **alvo** do reindex; aí seria necessário outro contorno.)*

---

## Estado atual

- **Código da DAG:** Mesma lógica de dados que o standalone; **única diferença intencional:** patch temporário em `Index.reindex` só durante `model.fit` (workaround pandas 3.x no Airflow).
- **requirements.txt:** `prophet>=1.3.0` e `pandas>=2.0.0,<3.0.0`.
- **Erro em produção:** Continua `ValueError: cannot reindex on an axis with duplicate labels` enquanto o **worker** estiver com **pandas 3.x** e **Prophet < 1.3.0**.
- **Imagem:** Rebuild feito com `docker build -t airflow-com-requirements E:\Airflow3`; Dockerfile com `pip install "pandas>=2.0,<3"` após requirements; erro persiste. Ver "Etapa: Dockerfile com forçar pandas<3 + novo rebuild".
- **Código (workaround atual):** Patch em `Index.reindex` com indexer montado por `get_loc` por label (substituiu o patch em `Series.reindex` — ver seção "Reavaliação do projeto").

---

## Soluções válidas (escolher uma)

1. **Garantir Prophet 1.3.0+ no worker**  
   Rebuild da imagem Docker usando o `requirements.txt` atualizado **ou** instalar no container:  
   `pip install "prophet>=1.3.0"`  
   Assim o Prophet usado no worker é compatível com pandas 3.0.

2. **Garantir pandas < 3 no worker**  
   Se não for possível atualizar o Prophet, fixar no ambiente (Docker/requirements do worker):  
   `pandas>=2.0.0,<3.0.0`  
   e garantir que o worker não puxe pandas 3 (ex.: dependência do Airflow 3).

Patches em `crosstab` e tentativas antigas em `Index.reindex` (com `unique`/`inverse` sem `get_loc`) foram descartadas. **Em uso:** nova variante de `Index.reindex` que, em caso de erro por duplicatas, monta o indexer com `get_loc` por elemento de `target` (ver "Reavaliação do projeto").

---

## Arquivos alterados ao longo do debug

| Arquivo | Alterações (resumo) |
|--------|----------------------|
| `Previsao_Propostas.py` | Limpeza de `treino_fit`; comentário no topo; lógica igual ao standalone; **patch em Index.reindex** (fallback com `get_loc` por label) só durante `model.fit`. |
| `requirements.txt` | `prophet>=1.3.0`; `pandas>=2.0.0,<3.0.0`; comentários. |
| `Dockerfile` | `RUN pip install -r /tmp/requirements.txt && pip install "pandas>=2.0.0,<3.0.0"`. |
| `Previsao_Propostas_DEBUG_HISTORICO.md` | Este documento (histórico + etapa Dockerfile + próximos passos). |

**Última atualização:** 2026-03-05 (Dockerfile com forçar pandas&lt;3 + rebuild; patch Series.reindex aplicado).

---

## Reavaliação do projeto (DAG vs standalone)

### Por que o standalone funciona e o Airflow não?

| Aspecto | Standalone (típico) | Airflow (worker) |
|--------|---------------------|------------------|
| **Código de previsão** | Igual (treino, Prophet, fit) | Igual, exceto conexão DB e patch só na DAG |
| **pandas** | Muitas vezes **2.x** (venv local) | Imagem `apache/airflow:3.1.3` costuma trazer **pandas 3.x** |
| **Prophet** | Compatível com o pandas local | Pode ficar em 1.2.x se o pip não atualizar |

O erro **não** vem de diferença na query ou no `treino_fit` em si: logs anteriores mostraram `treino_fit` sem `ds` duplicados. A falha ocorre **dentro** do Prophet (`regressor_column_matrix` → `crosstab` → `_homogenize` → `reindex`), quando o **pandas 3** recusa reindex com rótulos duplicados no eixo alvo.

### Limite do patch em `Series.reindex` (substituído)

- O patch anterior deduplicava apenas o **índice do Series** (`self.index`).
- No fluxo do crosstab, o `ValueError` costuma vir do **índice alvo** (`target`) com duplicatas, enquanto o Series já pode ter índice único.
- Por isso o patch em `Series.reindex` era **insuficiente** para o caso típico.

### Nova alteração (após reavaliação)

- **Removido:** monkey-patch em `pandas.core.series.Series.reindex`.
- **Adicionado:** monkey-patch em `pandas.core.indexes.base.Index.reindex` (apenas durante `model.fit`):
  - Tenta o `reindex` original.
  - Em `ValueError` com mensagem relacionada a duplicatas, percorre cada label em `target` e usa `self.get_loc(t)` para montar um vetor `indexer` inteiro (`-1` se não existir).
  - Retorna `(target, indexer)` com `len(indexer) == len(target)`, alinhado ao que o código interno do pandas espera para alinhar valores (evita a abordagem anterior que misturava posições em `target_u` e gerava `indices are out-of-bounds`).

**Arquivo:** `Previsao_Propostas.py` (bloco `try/finally` ao redor de `Prophet(...).fit(...)`).

**Risco conhecido:** Se em algum caminho o `take()` esperar outro comprimento ou semântica, pode voltar `IndexError`; nesse caso registrar traceback e considerar subprocess com pandas 2 ou ambiente isolado.

### Checklist para o operador

1. `docker exec <worker> pip show pandas prophet` — confirmar versões reais.
2. Compose/stack usando a imagem custom (`airflow-com-requirements`), não só a base oficial sem rebuild.
3. Após deploy do código novo, rerodar a task e anotar sucesso ou novo traceback.

---

**Última atualização:** 2026-03-05 — Reavaliação DAG vs standalone; substituição do patch `Series.reindex` por `Index.reindex` com indexer via `get_loc`.

---

## Achado novo (2026-03-20): “Sem Status” porque os DAGruns ficam `queued`

### Evidência (Airflow)

- O `dagrun` manual mais recente da DAG `Atualiza_PostgreSQL` aparece como `queued`, com `start_date` vazio:
  - `Atualiza_PostgreSQL | manual__2026-03-20T15:07:46+00:00 | queued`
  - mostrado no output salvo em `agent-tools/d242edd9-d9c0-49dc-9fb3-1e0d8be6b442.txt`.

- Para a DAG `Prev_Propostas_Aprovacao`, os `dagruns` manuais também ficam `queued`:
  - `Prev_Propostas_Aprovacao | manual__2026-03-20T12:53:53.57 | queued` (idem no `agent-tools/aebc4353-1fd1-4c9c-9d7b-a867bb2c85da.txt`).

### Evidência (container / scheduler)

- Antes do restart, o container `airflow3-standalone` estava com `health=unhealthy`.
- Ao rodar `airflow jobs check --job-type SchedulerJob`, retornou:
  - `No alive jobs found.`

Isso explica por que as tasks ficam com “Sem Status” (o scheduler não está agendando os jobs).

### Ação tomada

- Reiniciei o container:
  - `docker restart airflow3-standalone`

### Próximo passo

- Depois do restart estabilizar, disparar novamente manualmente a DAG `Atualiza_PostgreSQL` e confirmar que o `dagrun` sai de `queued` para `running`/`success`.
- Se continuar em `queued`, reiniciar novamente o container e/ou verificar logs do scheduler dentro do container.

---

## Correção adicional (2026-03-20): falhas de inserção não devem virar sucesso

### Sintoma observado

- Você reportou que `prev_propostas` “executou” mas “sumiu da DAG” e não apareciam erros.
- Um caso comum nesse tipo de pipeline é a tarefa terminar como `success` mesmo quando a persistência falha (ex.: conexão retorna `None` e o código apenas ignora).

### Hipótese

- Em `Previsao_Propostas.py` e/ou `prev_propostas_aprov.py`, erros de conexão/inserção eram tratados como “não fez nada” sem lançar exceção.

### Alterações aplicadas agora

1. `Previsao_Propostas.py`
   - Agora lança `RuntimeError` se `connect_to_db_Melnick()` retornar `None` ao salvar métricas em `modelos_lineares`.
   - Agora lança `RuntimeError` se `connect_to_db_Melnick()` retornar `None` ao inserir em `prev_propostas`.

2. `prev_propostas_aprov.py`
   - Agora valida o retorno de `inserir_dados_postgres(df_postgres)` e lança `RuntimeError` quando retornar `False`.

### Próximo passo

- Rodar novamente as DAGs no Airflow e verificar se, em caso de falha de DB, a task aparece como `failed` (em vez de `success` silencioso).

