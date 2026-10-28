# Manutenção preditiva com sensores IoT

Classificar se uma máquina precisa de manutenção a partir de 178 leituras de sensores — para reduzir parada não planejada sem disparar ordem de serviço em excesso.

## Problema de negócio

Em operação industrial, decidir **quando** intervir custa caro nos dois extremos: falha sem aviso derruba produção; manutenção desnecessária consome peça, mão de obra e janela de linha. O time de confiabilidade precisa de um sinal acionável a partir da telemetria, com taxa de erro conhecida no conjunto de teste — não só “um modelo treinado”.

## Pergunta que o projeto responde

Dado o vetor de 178 sensores, qual modelo (regressão logística, Naive Bayes ou XGBoost) maximiza a AUC em validação e, no teste, entrega probabilidade de necessidade de manutenção com limiar 0,5?

## Abordagem (do dado à decisão)

1. Carregar `dataset.csv` (~11,5 mil linhas × 179 colunas, dados fictícios) e validar qualidade básica.
2. Separar treino / validação / teste (70 / 15 / 15), com seed fixa.
3. Equilibrar só o treino com undersampling; manter validação e teste na prevalência real (~20% de positivos).
4. Padronizar features (`StandardScaler` ajustado no treino equilibrado) e persistir scaler + lista de colunas.
5. Treinar candidatos; no XGBoost, grid search com validação cruzada. Escolher pelo **AUC de validação**.
6. Avaliar no teste e aplicar o artefato em `novos_dados.csv`.

## Decisões de desenho

- **Undersampling só no treino:** evita que o otimizador ignore a classe rara, sem distorcer a estimativa de desempenho em validação/teste.
- **Critério de seleção = AUC de validação;** limiar de decisão fixo em 0,5 na operação.
- **Grid concentrado no XGBoost;** regressão logística e Naive Bayes entram como baseline baratos.
- **`n_jobs=1` no XGBoost** quando a GPU local tem VRAM limitada — troca tempo de wall-clock por estabilidade.

## Entrega e resultado

| Artefato | Uso |
|----------|-----|
| `melhor_modelo_dsa.pkl` | Modelo escolhido para inferência |
| `scaler.sav` / `cols_input.sav` | Mesmo pré-processamento em produção |
| `dados_treino*.csv`, `dados_valid.csv`, `dados_teste.csv` | Reproduzibilidade do split |

Métricas observadas no notebook revisado (XGBoost otimizado no teste): AUC **0,993**, acurácia **0,962**, recall **0,964**, precisão **0,846**, especificidade **0,962**. Em validação, o XGBoost ficou à frente da regressão logística (AUC ~0,52) e do Naive Bayes (~0,99).

Leitura de negócio: alto recall reduz risco de deixar máquina crítica passar; precisão ~0,85 implica ainda filtrar falsos positivos operacionaismente.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `manutencao_preditiva.ipynb` | Fluxo canônico (use este) |
| `Projeto3.ipynb` | Versão original / referência |
| `dataset.csv`, `novos_dados.csv` | Dados de treino e inferência |
| `requirements.txt`, `LEIAME.txt` | Dependências e setup de ambiente |

Referência interna DSA: Projeto 3.

## Como executar

1. Criar ambiente (ver `LEIAME.txt`) e `pip install -r requirements.txt`.
2. Abrir e executar `manutencao_preditiva.ipynb` na ordem das células.
3. Se não houver GPU CUDA, ajuste a configuração do XGBoost (`device`) — o revisado assume CUDA quando disponível.

## Limitações e próximos passos

- Dados **sintéticos**: serve para demonstrar o fluxo de decisão, não para calibrar limiar em planta real.
- AUC de treino saturada em alguns runs — monitorar overfitting antes de promover o modelo.
- Próximo passo natural: calibrar probabilidade, custo de FP/FN explícito e monitoramento de drift nos sensores.
