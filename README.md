# Desenvolvimentos
Destinado a projetos

## Gerador de Nuvem de Palavras

Script Python para gerar nuvem de palavras a partir de um arquivo Excel.

### Requisitos

- Python 3.8 ou superior
- Interface gráfica disponível (para seleção de arquivo e exibição do gráfico)

### Instalação

```bash
pip install -r requirements.txt
```

### Como usar

1. Execute o script:
```bash
python word_cloud_generator.py
```

2. Uma janela de seleção de arquivo será aberta - escolha seu arquivo Excel (.xlsx ou .xls)

3. O arquivo Excel deve ter:
   - Apenas uma coluna com dados
   - Um cabeçalho na primeira linha

4. A nuvem de palavras será gerada e exibida automaticamente

### Exemplo de formato do Excel

| Palavras |
|----------|
| Python   |
| Dados    |
| Análise  |
| Excel    |
| Nuvem    |
