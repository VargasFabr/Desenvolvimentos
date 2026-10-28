# Sentimento em resenhas de filme (bag-of-words + Naive Bayes)

Classificar resenhas em positive/negative com pipeline clássico de NLP — baseline forte, interpretável e barato de servir.

## Problema de negócio

Resenhas e comentários chegam em volume que ninguém lê um a um. O time de produto/conteúdo precisa saber, em escala, se o tom é **positivo ou negativo** — para dashboard de satisfação, alerta de crise e priorização de resposta. Errar a classe puxa o indicador para o lado errado; por isso o case compara opções simples e baratas de classificar texto **antes** de gastar com soluções mais caras (LLM, etc.).

## Pergunta que o projeto responde

Dada uma resenha de filme em inglês, o sistema consegue dizer se o sentimento é positivo ou negativo com boa taxa de acerto — e qual das três variantes testadas vale colocar em uso?

## Abordagem (do dado à decisão)

1. Carregar `dataset.csv` (50.000 resenhas balanceadas).
2. Limpar HTML/símbolos; stemmer Snowball (EN) + stopwords NLTK.
3. Split 80/20; `CountVectorizer(max_features=1000)`.
4. Treinar três Naive Bayes; selecionar por **AUC de teste**.
5. Persistir `modelo_sentimento.pkl` e validar com texto exemplo.

## Decisões de desenho

- **BoW top-1000** — baseline linear em memória e tempo; suficiente para polaridade grosseira.
- **Seleção por AUC**, não por preferência de algoritmo.
- Stemmer Snowball (revisado) pode deslocar métricas vs. tokenização do notebook original — o revisado é a fonte de verdade deste repo.

## Entrega e resultado

A entrega é um **filtro automático de polaridade** pronto para inferência:

| O que sai | Para que serve |
|-----------|----------------|
| `modelo_sentimento.pkl` | Arquivo único: recebe texto limpo e devolve positivo/negativo |
| Comparativo das 3 opções no teste | Escolher a melhor antes de “congelar” o modelo |
| `modelo_v3.pkl` | Legado — ignore; não é o canônico |

No notebook revisado (50 mil resenhas; 20% guardadas para teste):

| Opção | Acerto no teste | Qualidade do ranking (AUC) |
|-------|-----------------|----------------------------|
| Variante 1 | 79,0% | 0,862 |
| Variante 2 | 82,6% | 0,899 |
| **Variante escolhida (Bernoulli)** | **83,2%** | **0,908** |

**Decisão:** colocar em uso o modelo Bernoulli (`modelo_sentimento.pkl`) como primeiro filtro — cerca de **8 em cada 10** resenhas classificadas corretamente neste teste, com custo baixo. Para ironia, tom misto ou português, não espere o mesmo desempenho sem retreino.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `sentimento_filmes.ipynb` | Fluxo canônico |
| `Projeto2.ipynb` | Versão original |
| `dataset.csv` | Dados (~66 MB) |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 2.

## Como executar

1. Ambiente em `LEIAME.txt` + `pip install -r requirements.txt` (inclui NLTK).
2. Executar `sentimento_filmes.ipynb`. Na primeira vez o NLTK baixa `stopwords`.

## Limitações e próximos passos

- Só unigramas e vocabulário truncado — ironia e negação longa escapam.
- Corpus em inglês; não transferir para PT sem retreino.
- Próximo passo: tf-idf + calibração, ou empilhar com embedding/LLM só nos casos de baixa confiança.
