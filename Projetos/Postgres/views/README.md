# Views — cadastro Melnick

Views de consulta sobre o schema `cad`. Aplicar após o seed:

```powershell
python scripts/apply_views.py
```

## Onde ver no pgAdmin

**Opção 1 (recomendada):** `melnick` → Schemas → **`cad`** → Views

**Opção 2 (atalho):** `melnick` → Schemas → **`public`** → Views  
(cópias `v_*` apontam para `cad`)

## Views

| View | Descrição |
|------|-----------|
| `cad.v_torres_completas` | Torre + empreendimento + fase + incorporadora + cidade (grain canônico) |
| `cad.v_empreendimentos_resumo` | Empreendimento com totais de torres/fases e torre principal |
| `cad.v_torres_principais` | Uma linha por SPE: torre com `principal = true` |
| `cad.v_torre_identificadores` | Torre com IDs externos (gc, orulo, otto…) em colunas |
| `cad.v_empreendimento_identificadores` | Empreendimento com IDs externos (gc, otto, sap…) |
| `cad.v_torre_aliases` | Torre com lista de aliases (nomes legados) |
| `cad.v_busca_cadastro` | Lookup: alias ou nome → `codigo_interno` |
| `cad.v_empreendimentos_listagem` | Resumo + endereço (UI empreendimentos) |
| `cad.v_unidades_completas` | Unidade + torre + empreendimento + `codigo_unidade` |

Equivalentes em `public`: `v_torres_completas`, `v_empreendimentos_resumo`, `v_unidades_completas`, etc.

Arquivos: um por view (`v_*.sql`); unidades ainda em `02_views_unidades.sql`.
