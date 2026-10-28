# Governança de Nomes

## Problema

Planilhas legadas usam **nome de empreendimento** como chave. Isso causa:

- Confusão entre empreendimento e torre ("GO Carlos Gomes Torre A")
- Mesmo SPE com grafias diferentes
- Impossibilidade de join confiável entre fontes

## Solução

### Chave canônica = torre

Use sempre `cad.torres.codigo_interno`:

```
8190-001-F1
│    │   └── fase
│    └────── código da torre (CSV: Cód. Torre)
└─────────── SPE / cod_spe (GC/SAP)
```

### Empreendimento vs torre

| Conceito | Exemplo | Onde cadastrar |
|----------|---------|----------------|
| Empreendimento | AG Anita Garibaldi (SPE 8190) | `cad.empreendimentos` |
| Torre | Torre Única (001) | `cad.torres` |
| Vagas do empreendimento | Vagas (002) | `cad.torres` (segmento Vaga) |

**Regra:** se a linha da planilha tem `Cód. Torre`, é uma **torre**.

### Torre principal

Para planilhas que só tinham nome do empreendimento, use a torre com `principal = true` do SPE correspondente.

### Aliases

Ao encontrar string legada:

1. Buscar em `cad.aliases` (fuzzy: `pg_trgm`)
2. Se não existir, cadastrar alias apontando para `torres.id` correto
3. Nunca criar empreendimento duplicado por variação de nome

### Novas planilhas

- Coluna obrigatória: `codigo_interno` (torre) ou `cod_spe` + `cod_torre` + `fase`
- Proibido: usar `nome_empreendimento` como PK ou FK

## Exemplos

| String legada | Resolve para |
|---------------|--------------|
| AG Anita Garibaldi | alias → torre principal `8190-001-F1` |
| Arte Bela Vista Torre A | alias → `8080-00A-F1` |
| GO CARLOS GOMES | alias → empreendimento + torre principal (buscar SPE) |
