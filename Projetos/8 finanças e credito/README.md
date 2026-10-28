# Sentimento em textos sobre criptoativos (BERT + app)

Classificar mensagens como negativo, neutro ou positivo e expor a inferência em Streamlit — leitura rápida de tom de mercado a partir de texto.

> Nota de escopo: o nome da pasta vem do trilho do curso; o **case entregue** é NLP de sentimento em cripto/blockchain, não score de crédito.

## Problema de negócio

Desk de pesquisa e comunidades geram volume de texto sobre ativos digitais. Triagem manual não escala; sentimento agregado alimenta monitoramento e priorização de leitura. O risco de errar classe (sobretudo negativo ↔ positivo) é sinal falso para o analista — por isso o fluxo inclui holdout e app para inspeção humana da probabilidade.

## Pergunta que o projeto responde

Dado um texto em português sobre cripto/blockchain, o sistema classifica o tom como **negativo, neutro ou positivo** de forma útil para o analista — e dá para abrir isso numa tela simples, colar a mensagem e ver o resultado na hora?

## Abordagem (do dado à decisão)

1. Partir de `dataset.csv` (ou gerar amostra com `gera_dados.py`).
2. Filtrar idioma PT (`langid`); limpar URL, hashtag, menções e dígitos.
3. Fine-tune `bert-base-uncased` (max length 128, poucas épocas, batch efetivo via accumulation — adequado a GPU de ~6 GB).
4. Persistir em `./dsa_modelo_final`.
5. Servir com `projeto12app.py` (gauge, barras, wordcloud).

## Decisões de desenho

- **BERT inglês uncased em texto PT:** tokenização subótima; fine-tune compensa em parte — trade-off explícito vs. modelo PT maior.
- **Accumulation + fp16 opcional** para caber em VRAM limitada.
- **App separado do treino** — treino é batch; produto é inspeção interativa.

## Entrega e resultado

A entrega é um **classificador de sentimento + app para o desk**:

| O que sai | Para que serve |
|-----------|----------------|
| Modelo treinado em `./dsa_modelo_final` | Motor que lê o texto e devolve a classe |
| App Streamlit (`projeto12app.py`) | Colar mensagem, ver negativo/neutro/positivo, probabilidade e nuvem de palavras |
| Avaliação no treino (acurácia, F1, etc.) | Gate: só promove o modelo para o app se o erro no conjunto de teste for aceitável |

Os percentuais exatos de acerto saem ao rodar o notebook (não ficam fixos neste README). Sem a pasta `./dsa_modelo_final`, o app **não sobe** — o fluxo de negócio é treinar → validar → só então usar a tela.

**Decisão:** use o app para triagem rápida de tom; trate a classe e a probabilidade como apoio à leitura humana, sobretudo com base pequena/sintética como a deste case.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `sentimento_cripto.ipynb` | Treino canônico |
| `Projeto12.ipynb` | Versão original |
| `projeto12app.py` | Deploy local |
| `gera_dados.py` | Dados sintéticos opcionais |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 12.

## Como executar

1. Ambiente em `LEIAME.txt` + `pip install -r requirements.txt` (PyTorch, transformers — pesado).
2. Rodar `sentimento_cripto.ipynb` até gravar `./dsa_modelo_final`.
3. `streamlit run projeto12app.py`.

Sem o diretório do modelo, o app não sobe.

## Limitações e próximos passos

- Dataset pequeno / em parte sintético — bom para demonstrar pipeline, frágil para produção.
- Backbone EN em PT; considerar modelo multilingual ou PT-BR.
- Próximo passo: versionar o modelo no repo (ou registry), métricas no CI e matriz de confusão no README de release.
