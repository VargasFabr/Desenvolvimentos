# Cadastro Manual — visualizacao



App interno para CRUD da hierarquia `cad` (empreendimentos → fases → torres → unidades) e importação/exportação Excel.



## Pré-requisitos



- Postgres `melnick` com schema `cad` aplicado (`scripts/apply_cad.py`)

- Views em `public` (`python scripts/apply_views.py` — inclui unidades)

- Docker Desktop (opcional) ou Python 3.11+ e Node 20+



## Subir com Docker



```powershell

cd PROJETOS/dados/visualizacao

copy .env.example .env

docker compose up -d --build

```



- UI: http://localhost:5173

- API: http://localhost:8090/docs



## Funcionalidades



| Tela | Descrição |

|------|-----------|

| Dashboard | Totais + busca em `v_busca_cadastro` |

| Empreendimentos | Filtros (cidade, UF, incorporadora, qtd torres), **todas as colunas** (seletor), edição |

| Torres | Filtros (SPE, segmento, estágio, principal, permutante, cidade, fase), colunas completas, edição, link p/ unidades |

| Unidades | CRUD manual + **sync Otto** (preview → import) + filtros |

| Importar Excel | Abas **Torres** e **Unidades** — template → preview → confirm |



## API principal



### Empreendimentos / Torres



- `GET /api/empreendimentos` — `v_empreendimentos_listagem` + filtros (`q`, `cidade`, `uf`, `incorporadora`, `min_torres`, `max_torres`)

- `PUT /api/empreendimentos/{id}` — edição

- `GET /api/torres` — `v_torres_completas` completa + filtros (`spe`, `segmento`, `estagio`, `principal`, `permutante`, `cidade`, `uf`, `fase`, `q`)

- `GET /api/torres/filtros/opcoes` — valores distintos para selects

- `PUT /api/torres/{id}` — edição



### Unidades



- `GET /api/unidades` — `v_unidades_completas` + filtros

- `POST /api/unidades` — cria (por `codigo_interno` ou `id_torre`)

- `POST /api/unidades/sync/otto` — importa unidades do Otto (query `?spe=8190` opcional)
- `GET /api/unidades/sync/otto/preview` — preview antes de importar

- `GET /api/import/unidades/template.xlsx`

- `POST /api/import/unidades/preview` / `confirm`



### Import torres (existente)



- `GET /api/import/template.xlsx`, `POST /api/import/preview`, `POST /api/import/confirm`

- `GET /api/export/torres.xlsx`



Libs compartilhadas: `dados/lib/cad_parsers.py`, `cad_service.py`, `unidade_parsers.py`, `unidade_service.py`.



## Segurança (v1)



Sem autenticação — uso em localhost/rede interna.

