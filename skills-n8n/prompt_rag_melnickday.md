# Prompt de consulta pgvector — Melnick Day 2026 (identificação de intenção)

Este é o **texto de query** que deve ser embedado e enviado ao pgvector. O objetivo é recuperar chunks que permitam à IA identificar:

1. **Pergunta sobre o evento** — data do Melnick Day, regras, prazos, simuladores VPL, lista de empreendimentos represados/não represados, contato.
2. **Problema com reserva ou proposta em empreendimento represado** — regra de que reserva/proposta em represado é somente no dia do evento (21/03), lista de represados para conferir o empreendimento.

---

## Query única (recomendado)

Use a mensagem do usuário **expandida** com termos que existem na base, para o embedding puxar tanto trechos de “evento” quanto de “represado”:

```
Melnick Day 2026 evento data 21/03 regras campanha limpeza de espelho prazos reservas propostas contratos. Simuladores VPL empreendimentos represados. Lista empreendimentos represados e não represados. Reserva e proposta em empreendimento represado somente no dia do evento 21/03. Backoffice Comercial WhatsApp. {MENSAGEM_DO_USUARIO}
```

**Como usar:** substitua `{MENSAGEM_DO_USUARIO}` pela frase que o usuário digitou. Esse texto completo é o que você envia para o modelo de embedding e, em seguida, para a busca no pgvector (ex.: `ORDER BY embedding <=> query_embedding LIMIT k`).

---

## Query em duas partes (evento + represado)

Se preferir duas buscas e depois juntar os resultados (ou dar peso maior a um dos lados):

**Query 1 — evento:**  
`Melnick Day 2026 data do evento 21/03 regras campanha limpeza espelho prazos reservas propostas contratos simuladores VPL lista empreendimentos contato Backoffice`

**Query 2 — represado:**  
`Empreendimento represado reserva proposta somente dia do evento 21/03 lista represados não represados Botanique Gama Go Cidade Baixa Go Moinhos Family Grand Park Lindoia High Garden Jazz Nilo Square Seen Square Garden Supreme Yofi`

**Uso:**  
- Gerar embedding de `Query1 + " " + Query2 + " " + mensagem_do_usuario` e fazer uma única busca; ou  
- Fazer duas buscas (embed(Query1 + msg) e embed(Query2 + msg)), juntar os chunks, remover duplicatas por `id`, e passar o conjunto para a IA.

---

## Parâmetros sugeridos na busca pgvector

| Parâmetro   | Valor sugerido | Motivo |
|------------|----------------|--------|
| `LIMIT k`  | 10 a 20 (ou mais) | Com limit maior você traz mais chunks e cobre melhor o documento (regras, listas represados e não represados, resumo). Ajuste no node "Limit" do n8n. |
| Distância  | `<=>` (cosine) ou `<->` (L2) | Conforme o que foi usado ao gerar os embeddings. |

---

## O que a IA deve conseguir identificar com os chunks

Com os chunks retornados, a IA deve conseguir:

- **Evento:** responder data (21/03), prazos, regras e contato; saber se é “pergunta sobre o evento”.
- **Represado:** saber se o empreendimento citado está na lista de represados; aplicar a regra “reserva/proposta somente no dia 21/03”; saber se é “problema em reserva/proposta represado”.

O **prompt da IA** (system/user) fica em outro lugar; aqui está apenas o **prompt de consulta ao pgvector** para recuperar o contexto que permite essa identificação.
