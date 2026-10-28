# Chatbot de suporte com RAG sobre FAQ

Atendente virtual em Streamlit que responde com base nos documentos oficiais de suporte — menos ticket repetitivo, resposta alinhada à política publicada.

## Problema de negócio

Suporte escala mal quando cada analista reinterpreta o FAQ. O risco é inconsistência (frete, fidelidade, retirada) e tempo de primeira resposta. A entrega aqui é um canal conversacional que **ancora a resposta no acervo** (`./suporte`), não um LLM solto inventando política.

## Pergunta que o projeto responde

Dada uma pergunta do cliente, o assistente condensa o histórico da sessão e responde usando os FAQs indexados?

## Abordagem (do dado à decisão)

1. Interface Streamlit com histórico de chat.
2. Embeddings `all-MiniLM-L6-v2` (GPU se disponível).
3. LLM local via Ollama (`llama3.1`).
4. Indexar `./suporte` (docx) com LlamaIndex → índice vetorial em cache.
5. Chat em modo `condense_question` com prompt de atendente em português.

## Decisões de desenho

- **RAG sobre FAQ** em vez de fine-tune: política muda no documento, não no peso do modelo.
- **Ollama local** para o LLM; embeddings HuggingFace na máquina — demo sem API paga de chat.
- Workaround `torch.classes.__path__` para convivência Streamlit + PyTorch.

## Entrega e resultado

| Artefato | Uso |
|----------|-----|
| `chatbot_rag.py` | App Streamlit (versão a rodar) |
| `suporte/FAQ1.docx`, `FAQ2.docx` | Base de conhecimento |
| Índice em memória (cache Streamlit) | Recuperação na sessão |

Não há métrica de qualidade automática no código: a entrega é o **canal operacional** para validação humana com perguntas reais de suporte.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `chatbot_rag.py` | App canônico |
| `projeto9.py` | Versão original |
| `suporte/` | FAQs |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 9. O `LEIAME.txt` pode citar o script antigo — use `chatbot_rag.py`.

## Como executar

1. Ambiente em `LEIAME.txt` + `pip install -r requirements.txt`.
2. Ollama com modelo **`llama3.1`** (diferente do `llama3` do projeto de varejo).
3. `streamlit run chatbot_rag.py`.
4. A primeira indexação baixa o modelo de embedding (rede necessária).

## Limitações e próximos passos

- Base limitada a dois FAQs — cobertura = o que estiver em `suporte/`.
- Sem ground-truth nem avaliação offline de alucinação.
- Próximo passo: citation obrigatória no UI, avaliação com perguntas rotuladas e atualização incremental do índice.
