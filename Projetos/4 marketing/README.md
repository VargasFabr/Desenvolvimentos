# Teste A/B de campanha de marketing

Decidir, com rigor estatístico, se a variante B melhora a conversão em relação à A — antes de escalar orçamento.

## Problema de negócio

Marketing gasta em criativo, canal e audiência. Sem teste controlado, “B parece melhor” vira viés de amostra. O decisor precisa de uma resposta binária sob α definido: **há evidência de diferença de conversão?** Coordenadas no dataset contextualizam o público; não substituem o teste.

## Pergunta que o projeto responde

A versão B da campanha converte de verdade mais do que a A, ou a diferença que aparece nos números ainda pode ser só acaso — e, neste teste, vale a pena trocar o orçamento para B?

## Abordagem (do dado à decisão)

1. Carregar `dataset.csv` (1.000 observações).
2. Calcular taxa média de conversão por grupo e tamanhos amostrais.
3. Testar normalidade (Shapiro) e homogeneidade de variâncias (Levene).
4. Rodar t-test e Mann-Whitney; **a decisão operacional segue o Mann-Whitney** quando a normalidade cai.
5. Plot exploratório lat/lon — sem entrar na hipótese principal.

## Decisões de desenho

- Conversão é **binária** → Shapiro rejeita normalidade → teste não paramétrico decide.
- t-test fica como contraste didático/operacional, não como veredito.
- Mapa é contexto; não modela geografia na decisão A/B.

## Entrega e resultado

A entrega é um **parecer para o time de marketing** (não um modelo salvo): seguir com A, migrar para B, ou refazer o teste.

No experimento (1.000 pessoas: 490 em A, 510 em B):

| Grupo | Conversão observada |
|-------|---------------------|
| A | **30,0%** |
| B | **31,6%** |

B parece um pouco melhor (~1,6 ponto percentual), mas o teste estatístico (Mann-Whitney, e o t-test no mesmo sentido) indica que essa diferença **não é confiável**: com a amostra deste teste, ainda pode ser variação aleatória (p ≈ 0,59; usamos o limiar usual de 5% de risco de erro).

**Decisão:** neste experimento, **não há evidência suficiente para migrar o orçamento para B**. Ou mantém A, ou desenha um novo teste maior / mais longo se a meta for detectar um ganho pequeno como esse.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `teste_ab.ipynb` | Análise canônica |
| `Projeto6.ipynb` | Versão original |
| `dataset.csv` | Resultados do experimento |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 6.

## Como executar

1. Ambiente em `LEIAME.txt` + `pip install -r requirements.txt` (pandas, scipy, matplotlib).
2. Executar `teste_ab.ipynb` de cima a baixo.

## Limitações e próximos passos

- n = 1.000 e efeito absoluto pequeno (~1,6 p.p.) — power limitado para diferenças sutis.
- Sem análise formal de poder amostral a priori.
- Próximo passo: definir MDE (minimum detectable effect), duração e métricas secundárias (receita, retenção) antes do próximo experimento.
