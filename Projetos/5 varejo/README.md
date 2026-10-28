# Demanda sazonal e insights de estoque com DW + LLM

Materializar vendas, estoque e forecast em Postgres e gerar recomendações em linguagem natural para categorias sazonais — do dado operacional ao texto acionável para o time de planejamento.

## Problema de negócio

Varejo sazonal (eletrônicos, roupas) vive o trade-off ruptura × excesso. Forecast e reposição já existem como tabelas; o gargalo costuma ser **traduzir joins complexos em decisão legível** para quem não lê SQL o dia inteiro. Este case automatiza a ponte: warehouse local + LLM que comenta cada produto filtrado.

## Pergunta que o projeto responde

Para cada produto nas categorias Eletrônicos e Roupas, o pipeline consegue gerar um insight em português a partir de vendas, estoque, sazonalidade, forecast e reabastecimento?

## Abordagem (do dado à decisão)

1. Subir Postgres 16 via Docker (porta **5551**, database `dsadb`).
2. Criar schema/tabelas (`Projeto7-01` / `Projeto7-02`).
3. Carregar CSVs `dsa_*.csv` (`Projeto7-03`).
4. Consultar o DW e pedir insights ao Llama 3 via Ollama + LangChain (`Projeto7-04`).
5. Orquestrar ponta a ponta com `Projeto7-05-Run-Pipeline.py` → `projeto7-analise.csv`.

## Decisões de desenho

- **Forecast e reposição vêm dos CSVs** — o código não treina modelo de demanda; foca integração e narrativa.
- **Filtro fixo de categorias** para manter o lote de insights revisável.
- **LLM local (Ollama)** — dados de varejo não precisam sair da máquina em um demo de portfólio.

## Entrega e resultado

| Artefato | Uso |
|----------|-----|
| Banco `dsadb` / schema `projeto7` | Fonte única para consultas |
| `projeto7-analise.csv` | Insights gerados (ex.: 10 linhas na execução de referência) |

Não há métrica quantitativa de “acerto” do texto no repositório: a entrega é o **artefato de análise** para revisão humana do planner.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `Projeto7-05-Run-Pipeline.py` | Orquestração |
| `Projeto7-01-Tabelas.sql` … `Projeto7-04-LLM.py` | Etapas do pipeline |
| `dsa_*.csv` | Dados de entrada |
| `projeto7-analise.csv` | Saída de insights |
| `requirements.txt`, `LEIAME.txt` | Ambiente e Docker |

Referência interna DSA: Projeto 7.

## Como executar

1. Subir o container Postgres conforme `LEIAME.txt` (usuário/senha e porta 5551).
2. Criar o conda env indicado e `pip install -r requirements.txt`.
3. Ter **Ollama** com o modelo **`llama3`** disponível.
4. `python Projeto7-05-Run-Pipeline.py`.

Armadilhas: reexecutar carga em modo append pode duplicar linhas; credenciais estão no código (ok para demo local — não reutilize em produção).

## Limitações e próximos passos

- Insights são **não determinísticos** e sem avaliação automática de qualidade.
- Amostra CSV pequena — demonstra o fluxo, não um calendário comercial real.
- Próximo passo: versionar prompts, avaliar insights com rubric de negócio e retirar segredos para variáveis de ambiente.
