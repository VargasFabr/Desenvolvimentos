# Analytics geoespacial de edificações em escala

Consultar dezenas de milhões de pegadas de edifícios no S3, agregar por grade e recortar uma área de interesse — sem baixar o bucket inteiro — e entregar camadas prontas para GIS.

## Problema de negócio

Planejamento urbano, seguro e logística precisam saber **o que existe no chão** em escala de país. Baixar GeoParquet global ou abrir tudo em GIS desktop não escala. A decisão aqui é operacional: uma única sessão analítica (DuckDB) que varre partições remotas, compara fontes (Google vs Microsoft / Open Buildings) e materializa só o recorte útil.

## Pergunta que o projeto responde

Dentro da área de interesse (`limites.geojson`, no Lesoto), o inventário que junta Google + Microsoft traz quantos edifícios a mais do que o Open Buildings só do Google — ou seja, o que o mesclado cobre e a fonte Google sozinha não vê?

## Abordagem (do dado à decisão)

1. Conectar DuckDB com extensões `httpfs` e `spatial`; usar todos os núcleos da máquina.
2. Escanear GeoParquet particionado no S3 (ex.: Brasil) e contar por fonte.
3. Agregar Austrália por célula S2 (densidade sem materializar cada polígono).
4. Carregar Lesoto (mesclado + Google original), definir AOI via `limites.geojson`, intersectar e isolar o que só aparece no mesclado.
5. Exportar FlatGeobuf e visualizar a AOI em mapa (Folium → HTML local).

## Decisões de desenho

- **Uma conexão DuckDB** com muitos threads em vez de conexões isoladas que não compartilham tabelas.
- **Scan remoto por `country_iso` / S2** em vez de download total do bucket.
- **Spatial na CPU** — o ganho vem de I/O e paralelismo, não de GPU.
- **AOI pequena** para comparar fontes com custo controlado; export do país inteiro fica em arquivo separado e pesado.

## Entrega e resultado

| Artefato | Uso |
|----------|-----|
| `dataset1.fgb` | Edificações do recorte (mesclado ∩ AOI) |
| `dataset2.fgb` | Lesoto completo (atributos + geometria; arquivo grande) |
| `mapa_limites.html` | AOI no mapa para validação visual |
| `limites.geojson` | Definição da área de interesse |

Contagens observadas no notebook revisado: Brasil google **136.237.330** / microsoft **4.807.793**; na AOI, mesclado **13.561**, só Google **13.213**, cobertura extra do mesclado **348**.

Leitura de negócio: esses **348** são o ganho prático de usar o inventário mesclado naquela área — input direto para escolher a fonte.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `edificacoes_geo.ipynb` | Fluxo canônico |
| `Projeto4.ipynb` | Versão original |
| `limites.geojson` | AOI (retângulo fechado em Lesoto) |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 4.

## Como executar

1. Ambiente conforme `LEIAME.txt` + `pip install -r requirements.txt`.
2. Rede estável para S3 (Source Cooperative). A célula do Brasil é a mais lenta.
3. Executar `edificacoes_geo.ipynb`. Para o mapa: a célula sobe HTTP em `127.0.0.1` (evita 403 de tiles em `file://`). Instale `folium` se ainda não estiver no ambiente — pode não constar no `requirements.txt`.

## Limitações e próximos passos

- Dependência de dataset público remoto (disponibilidade e latência fora do seu controle).
- Tiles de mapa de terceiros podem bloquear ou exigir chave de API.
- Próximo passo: parametrizar AOI, versionar exports e comparar cobertura com métricas de área (não só contagem de features).
