# Previsão do índice de rotatividade de estoque (LSTM)

Projetar a rotatividade anual de estoque para apoiar planejamento de demanda e capacidade — série temporal curta, split cronológico, horizonte de dois anos.

## Problema de negócio

Logística e supply planejam compra, armazenagem e nível de serviço com base em **rotatividade**. Erro sistemático no índice distorce reposição e capital empatado. O case trata a série histórica anual (1970–2024) e entrega projeção para 2025–2026, com erro medido em holdout temporal.

## Pergunta que o projeto responde

Olhando a rotatividade de estoque de 1970 a 2024, o que o time de planejamento pode esperar para **2025 e 2026** — e o quão errado esse número tende a ficar quando testamos o modelo em anos que ele ainda não tinha visto?

## Abordagem (do dado à decisão)

1. Carregar `dataset.csv` (55 anos). O modelo usa `indice_rotatividade_estoque` (outras colunas no CSV não entram neste desenho).
2. Split temporal 80/20 — sem embaralhar o tempo.
3. `MinMaxScaler` ajustado só no treino; janelas com look-back = 1.
4. LSTM (50 unidades) + Dense; treino com early volume de épocas definido no notebook.
5. RMSE em treino/teste na escala original; forecast recursivo de dois passos.

## Decisões de desenho

- **Split cronológico** — métrica de teste reflete o futuro, não um shuffle irrealista.
- **Univariado e look-back = 1** — baseline enxuto na série curta; covariates (`otif`, `lead_time`, etc.) ficam para evolução.
- Batch size adaptativo (`min(32, n)`) para estabilidade com poucas janelas.

## Entrega e resultado

A entrega é um **parecer numérico para planejamento**: a projeção da rotatividade nos dois próximos anos, mais uma medida de erro para saber se dá para confiar nela.

| O que sai | Para que serve |
|-----------|----------------|
| Projeção **2025** e **2026** | Input para compra, capacidade e nível de estoque |
| Erro no “teste” (anos finais da série, RMSE) | Gate: se o erro for alto demais para o negócio, não use a projeção como se fosse certeza |
| Gráfico histórico × previsto | Validação visual com o time |

Os valores exatos de 2025/2026 e do RMSE saem ao rodar `rotatividade_estoque.ipynb` (podem variar um pouco a cada treino). O notebook não deixa esses números fixos no arquivo — a decisão é materializar a execução e comparar o erro de teste com a tolerância do seu processo.

**Decisão:** use as projeções só se o erro de teste for aceitável para o negócio; lembre que prever dois anos à frente acumula incerteza (o segundo ano usa a previsão do primeiro como entrada).

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `rotatividade_estoque.ipynb` | Fluxo canônico |
| `Projeto10.ipynb` | Versão original |
| `dataset.csv` | Série |
| `requirements.txt`, `LEIAME.txt` | Ambiente (TensorFlow) |

Referência interna DSA: Projeto 10.

## Como executar

1. Ambiente em `LEIAME.txt` (Python 3.12 no guia) + `pip install -r requirements.txt`.
2. Executar `rotatividade_estoque.ipynb`. GPU é opcional (o código detecta dispositivo).

## Limitações e próximos passos

- Série curta (55 pontos) e look-back = 1 limitam memória temporal do modelo.
- Forecast recursivo de 2 passos propaga erro.
- Próximo passo: incluir covariates, validação rolling e intervalos de previsão.
