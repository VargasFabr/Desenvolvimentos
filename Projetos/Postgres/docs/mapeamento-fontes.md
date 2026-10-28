# Mapeamento de Fontes → Schema `cad`

## CSV Controladoria (`Empreendimentos.csv`) — Fase 1 (master)

| Coluna CSV | Destino | Notas |
|------------|---------|-------|
| Empreendimento | `empreendimentos.nome_comercial` + alias | |
| SPE | `empreendimentos.cod_spe` + id externo `gc` | Chave empreendimento |
| Torre | `torres.nome_torre` | |
| Cód. Torre | `torres.cod_torre` | Parte da chave torre |
| Fase | `fases.numero_fase` | Parte da chave torre |
| ID Órulo | `torres.id_orulo` + id externo `orulo` | |
| Segmento, Estágio, VGV… | `torres.*` | Atributos na torre |
| Empresa | `torres.tipo_empresa` | INC, URB, PERM… |
| Logradouro…CEP | `empreendimentos.endereco_*` | Por SPE (primeira linha) |

**Grain do CSV:** 1 linha = 1 torre → 818 registros em `cad.torres`

## Otto CRM — Fase 2

| Otto | cad | Join |
|------|-----|------|
| `realty.integration_id` | `empreendimentos.cod_spe` | TEXT = SPE |
| `realty.id` | `identificadores_externos` sistema `otto` | |
| `building.id` | torre via nome/cod | heurística |
| `building.integration_id` | `torres.cod_torre` | sufixo `{cod}{spe}` ex. `0018190` → cod `001`, SPE `8190` |
| `unit.number` | `unidades.nome` | |
| `unit.integration_id` | `unidades.id_gc` | |
| `unit.id` | `identificadores_externos` sistema `otto` | |

Script sync unidades: [`scripts/sync_otto_unidades.py`](../scripts/sync_otto_unidades.py)  
API/UI: `GET /api/unidades/sync/otto/preview`, `POST /api/unidades/sync/otto`

## SAP

| SAP | cad | Join |
|-----|-----|------|
| `stage_bseg.cd_empreendimento` | `empreendimentos.cod_spe` | INTEGER cast TEXT |

## GC / SPE

Código numérico SPE (8190, 8120) = `cod_spe` = identificador `gc`

## Orulo

`ID Órulo` no CSV → `identificadores_externos` sistema `orulo` na torre

## Excel legado — Fase 3

Importar como `aliases` com `fonte = 'excel'`, apontando para torre resolvida manualmente ou via fuzzy match.

## Monday / DocuSign — Fase 3+

Cadastrar em `identificadores_externos` ou `aliases` conforme padrão de cada integração.
