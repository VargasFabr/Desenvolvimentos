# Desenvolvimentos

Portfólio de **ciência de dados** e plataforma de **dados + automação em produção** para Controladoria Comercial (imobiliário): do case analítico à orquestração que alimenta BI, Monday e atendimento.

## Dois trilhos

| Trilho | Onde | O que é |
|--------|------|---------|
| **Cases analíticos (1–9)** | [`Projetos/1…9`](Projetos/) | Projetos de ciência de dados (portfólio) que respondem uma pergunta de negócio ponta a ponta |
| **Plataforma em produção** | [`Airflow3`](Projetos/Airflow3), [`n8n`](Projetos/n8n), [`Postgres`](Projetos/Postgres) | Stack operacional da Controladoria: espelhos, sync, cadastro canônico, atendimento |

Cada pasta tem o próprio README com problema → abordagem → entrega. Este arquivo é o mapa.

---

## Plataforma em produção

O problema de fundo: reservas, propostas, contratos e concorrência vivem em sistemas diferentes (Otto, Monday, DocuSign, SharePoint, Órulo, Excel). Sem um lugar único e atualizado, o time perde tempo conferindo na mão e o relatório comercial atrasa. A entrega é um banco central (Postgres) alimentado no horário certo pelo Airflow, com atendimento WhatsApp e automações pontuais no n8n/Chatwoot.

| Pasta | Problema de negócio | Entrega |
|-------|---------------------|---------|
| [`Projetos/Postgres`](Projetos/Postgres) | Empreendimentos eram “achados” por nome em planilha; cada sistema chamava a torre de um jeito | Cadastro único (torre como referência), telas para cadastrar/editar e consultas prontas para o time |
| [`Projetos/Airflow3`](Projetos/Airflow3) | CRM e contratos mudam o tempo todo; o time não tinha cópia local confiável nem Monday atualizado sozinho | Agenda e roda as atualizações da Controladoria (Otto → banco/Monday, DocuSign, Órulo, dações…) |
| [`Projetos/n8n`](Projetos/n8n) | Atendimento e tarefas do dia a dia (WhatsApp, imagem, reset de senha no Otto) não cabem no lote agendado | Inbox WhatsApp (Chatwoot) + fluxos n8n + serviço auxiliar de imagem/senha |

Detalhe operacional e decisões: README e `ARCHITECTURE.md` de cada pasta. Segredos: [`.env.example`](.env.example) na raiz (nunca committe `.env`).

### Catálogo Airflow — o que cada fluxo resolve

Cada item é uma rotina que o Airflow dispara no horário combinado (horários e pastas técnicas em [`Airflow3/README.md`](Projetos/Airflow3/README.md)). O código de negócio fica em [`Melnick-Code`](Projetos/Airflow3/dags/AtualizaBackoffice/Melnick-Code).

**`Atualiza_PostgreSQL`**

- **Problema:** dados de reservas e propostas ficam só no Otto na nuvem; painéis e análises locais não enxergam o CRM atualizado.
- **Entrega:** cópia local do Otto no banco `otto`, atualizada ao longo do expediente, para BI e outros fluxos consultarem sem depender da nuvem a cada clique.

**`Atualiza_BackOffice` (AutoBackoffice)**

- **Problema:** o quadro de Relatório Comercial no Monday atrasa — corretor, imobiliária e status do negócio mudam no Otto e ninguém atualiza o board.
- **Entrega:** a cada ~20 min no horário comercial, reservas e propostas novas/alteradas sobem no Monday (contas + negócios).

**`Atualiza_Docu` / `ContratosDocusign`**

- **Problema:** o cliente assina no DocuSign, mas o Monday não mostra se o contrato andou.
- **Entrega:** status e envelopes de assinatura voltam para o board — o comercial vê o contrato sem abrir o DocuSign.

**`Atualiza_Orulo` (legado) / `Atualiza_Orulo_2_0`**

- **Problema:** concorrência e lançamentos nacionais somem do radar se alguém não entrar no Órulo na mão.
- **Entrega:** capta lançamentos pela API do Órulo; o 2.0 grava no banco da empresa (`melnick.orulo`); o legado ainda alimenta o Supabase.

**`Atualiza_Dacoes` + Avaliação de Dações**

- **Problema:** planilha de dações no SharePoint — difícil consultar, cruzar e alimentar o agente Hermes; risco de perder histórico.
- **Entrega:** lê o SharePoint, grava no banco `dacoes` (backup consultável) e deixa os dados prontos para o Hermes avaliar.

**`Atualiza_Hermes_Deps`**

- **Problema:** o agente Hermes pode quebrar ou ficar vulnerável se uma dependência tiver falha de segurança.
- **Entrega:** todo dia checa CVEs/dependências e gera relatório — a TI é avisada antes de virar incidente.

**`Previsao_Propostas` / `Prev_Propostas_Aprovacao`**

- **Problema:** estimar volume de propostas ou chance de aprovação sem planilha improvisada.
- **Entrega:** modelos de previsão sobre o espelho Otto — **hoje sob demanda** (não entram no horário automático).

**`Previsao_Distratos`** ([`projetoDistratos.ipynb`](Projetos/Airflow3/dags/projetoDistratos.ipynb))

- **Problema:** o time precisa antecipar quais contratos têm maior risco de desfazer a venda (distrato), sem revisar contrato a contrato na mão.
- **Entrega:** pipeline que lê os contratos no SQL Server, monta features (pagamento, ato, empreendimento, perfil etc.) e treina um XGBoost otimizado para pontuar risco de distrato e exportar as previsões — **notebook sob demanda** (ainda não é rotina automática do Airflow).

**`Sync_Media_Otto_Imagens`**

- **Problema:** fotos/mídias dos empreendimentos ficam só no Otto; quem precisa do arquivo local não tem.
- **Entrega:** baixa as imagens para disco e registra o que já foi sincronizado — **também manual**.


---

## Cases de ciência de dados (1–9)

Cases de aula, escritos como entrega de negócio. Métricas e “como rodar” ficam no README de cada pasta.

| # | Pasta | Pergunta de negócio | Entrega |
|---|-------|---------------------|---------|
| 1 | [`descomplicando algoritimos e modelos`](Projetos/1%20descomplicando%20algoritimos%20e%20modelos) | Quando intervir na máquina a partir de sensores, sem excesso de ordem de serviço? | Classificador de manutenção preditiva (melhor modelo por AUC) |
| 2 | [`dados em larga escala`](Projetos/2%20dados%20em%20larga%20escala) | Na AOI, o inventário mesclado (Google+Microsoft) cobre quantos edifícios a mais que só o Google? | Camadas GIS + contagem de cobertura extra |
| 3 | [`sentimento texto`](Projetos/3%20sentimento%20texto) | A resenha é positiva ou negativa — e qual baseline barato vale usar? | Modelo NB + artefato de inferência |
| 4 | [`marketing`](Projetos/4%20marketing) | A variante B converte de verdade mais que A, ou ainda pode ser acaso? | Parecer A/B (neste case: **não migrar** orçamento) |
| 5 | [`varejo`](Projetos/5%20varejo) | Dado vendas/estoque/forecast no DW, qual insight em português para o planner? | Pipeline Postgres + LLM → CSV de recomendações |
| 6 | [`cliente`](Projetos/6%20cliente) | O atendente responde ancorado no FAQ oficial, sem inventar política? | Chatbot RAG (Streamlit) |
| 7 | [`logistica`](Projetos/7%20logistica) | Qual rotatividade esperar em 2025–2026, e com que erro de holdout? | Projeção LSTM + RMSE |
| 8 | [`finanças e credito`](Projetos/8%20finanças%20e%20credito) | Qual o tom (neg/neutro/pos) de um texto sobre cripto em PT? | BERT fine-tuned + app Streamlit — **nota:** o nome da pasta é do trilho do curso; o case é sentimento em cripto, não score de crédito |
| 9 | [`agronegocio`](Projetos/9%20agronegocio) | A foto da planta indica ferrugem (folha/tronco) ou saudável? | CNN (InceptionV3) para triagem visual |

---

## Como navegar

1. **Produção** → README (+ `ARCHITECTURE.md`) de Postgres, Airflow3 ou n8n.
2. **Case 1–9** → README da pasta (problema, decisão, limitações, como executar).
3. **Segredos / env** → copie [`.env.example`](.env.example) para `.env` na raiz; composes apontam para esse arquivo.

## Stack (visão rápida)

Python · PostgreSQL 17 · Apache Airflow 3 · n8n · Chatwoot · Docker · Streamlit / Vite (UI de cadastro e demos) · DuckDB / scikit-learn / XGBoost / TensorFlow / Transformers nos cases.
