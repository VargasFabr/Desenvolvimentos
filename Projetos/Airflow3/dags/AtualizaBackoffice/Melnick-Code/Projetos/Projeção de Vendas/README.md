## Projecao de Vendas (Streamlit)

App simples para cadastrar estoque, vendas e distratos por empreendimento e ano.
Permite abrir o ano em meses para maior granularidade e valida estoque nao negativo.

### Funcionalidades
- Cadastro de empreendimentos e anos.
- Estoque inicial por ano.
- Vendas e distratos anuais ou mensais (quando abrir meses).
- Validacao de estoque final nao negativo.
- Alerta de estoque negativo em qualquer mes (quando mensal).
- Graficos simples de estoque e movimentos.

### Como rodar
1. Crie o ambiente e instale dependencias:
	- `pip install -r requirements.txt`
2. Execute o app:
	- `streamlit run app.py`

### Dados
Os dados ficam em tres arquivos dentro de `data/`:
- `empreendimentos.json`
- `projecoes.json`
- `projecoes_series.json`

Esses arquivos sao criados automaticamente ao salvar.

### Dados de exemplo
Use o script abaixo para criar arquivos de exemplo:
- `python scripts/seed_sample_data.py`

Para sobrescrever dados existentes:
- `python scripts/seed_sample_data.py --force`
