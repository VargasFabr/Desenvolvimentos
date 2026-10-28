# Melnick Code

Repositório centralizado de módulos reutilizáveis e projetos de automação para operações comerciais e de backoffice da Melnick.

## Visão Geral

Este repositório contém:
- **Módulos compartilhados**: Bibliotecas Python para integração com sistemas externos (Monday.com, Otto, DocuSign, Procempa)
- **Projetos de automação**: Aplicações que utilizam os módulos para automatizar processos de negócio
- **Configuração centralizada**: Sistema de mapeamento de dados e logs padronizados

## Estrutura do Repositório

```
Melnick Code/
├── Módulos/                      # Bibliotecas compartilhadas e clientes de API
│   ├── cliente_monday.py         # Cliente GraphQL para Monday.com
│   ├── cliente_otto.py           # Cliente PostgreSQL para banco Otto (CRM)
│   ├── cliente_docusign.py       # Cliente DocuSign (em desenvolvimento)
│   ├── cliente_procempa.py       # Cliente API Procempa (expedientes)
│   ├── logs_melnick.py           # Sistema de logging padronizado
│   └── mapeamento_dados.py       # Mapeamento de colunas entre sistemas
│
└── Projetos/                     # Aplicações de automação
    ├── AutoBackoffice/           # Sincronização Otto → Monday.com
    │   ├── AutoBackoffice.py     # Script principal
    │   ├── requirements.txt      # Dependências do projeto
    │   └── Dados/
    │       └── ultima_atualizacao.txt
    │
    └── Expediente Único/         # Consulta de expedientes Procempa
        ├── main.py               # Script de exemplo
        └── cliente_procempa.py   # Cliente API (cópia local)
```

### Módulos Disponíveis

- **cliente_monday.py**: Cliente completo para API GraphQL do Monday.com com suporte a queries, criação, atualização de itens, parsing de tipos de coluna, paginação automática e retry logic
- **cliente_otto.py**: Cliente para banco de dados Otto (PostgreSQL) com queries especializadas para processos, propostas, reservas e unidades
- **cliente_docusign.py**: Integração com DocuSign (não implementado)
- **logs_melnick.py**: Configuração padronizada de logging com formatação customizada para console e arquivo
- **mapeamento_dados.py**: Mapeamento centralizado entre IDs de colunas do Monday.com e nomes padronizados

### Projetos Disponíveis

- **AutoBackoffice**: Sincroniza dados do banco Otto (CRM) com quadros do Monday.com para gestão comercial de negócios imobiliários
- **Expediente Único**: Consulta informações de expedientes de construção através da API pública da Procempa

## Adicionando Novos Códigos

### Quando criar um Módulo

Adicione código na pasta **Módulos/** quando:
- O código é uma **biblioteca reutilizável** que pode ser importada em diferentes projetos
- Implementa um **cliente para API externa** ou serviço
- Fornece **funcionalidades genéricas** (logging, mapeamento de dados, utilitários)
- Foi projetado para ser **independente** e não vinculado a um projeto específico

**Exemplos**: Clientes de API (Monday, Otto, DocuSign), sistemas de logging, conversores de dados

### Quando criar um Projeto

Adicione código na pasta **Projetos/** quando:
- É uma **aplicação completa** com objetivo ou funcionalidade específica
- Pode conter **múltiplos arquivos e subpastas** (scripts, dados, configurações)
- **Utiliza os módulos** existentes para resolver um problema de negócio
- **Não é feito para ser reutilizado** em outros projetos (é o produto final)

**Exemplos**: Scripts de automação, sincronizadores de dados, ferramentas de consulta

### Regra Geral

> **Módulos são bibliotecas. Projetos são aplicações.**
> 
> Se você está criando algo para ser importado e reutilizado → **Módulo**  
> Se você está criando algo para ser executado e resolver um problema → **Projeto**

## Instalação

### Pré-requisitos

- Python 3.8 ou superior
- Git

### Passos de Instalação

1. **Clone o repositório**:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd "Melnick Code"
   ```

2. **Crie um ambiente virtual** (recomendado):
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Instale as dependências do projeto desejado**:
   
   Para o **AutoBackoffice**:
   ```bash
   pip install -r "Projetos/AutoBackoffice/requirements.txt"
   ```
   
   Para o **Expediente Único** (sem dependências externas além do `requests`):
   ```bash
   pip install requests
   ```

## Configuração

### Arquivo .env

O arquivo `.env` deve ser criado **na pasta pai** do diretório `Melnick Code` (ou seja, um nível acima do repositório clonado).

**Localização esperada**:
```
📁 Sua Pasta/
├── 📁 Melnick Code/          ← Repositório clonado
│   ├── Módulos/
│   └── Projetos/
└── 📄 .env                    ← Arquivo de configuração aqui
```

### Variáveis de Ambiente Necessárias

As variáveis necessárias dependem de quais módulos e projetos você irá utilizar:

#### Para `cliente_monday.py` e `cliente_otto.py`:
```
MONDAY_API_KEY=<seu_token_monday>
OTTO_DB_USER=<usuario_banco_otto>
OTTO_DB_PASSWORD=<senha_banco_otto>
```

#### Para o projeto `AutoBackoffice.py`:
```
MONDAY_API_KEY=<seu_token_monday>
OTTO_DB_USER=<usuario_banco_otto>
OTTO_DB_PASSWORD=<senha_banco_otto>
AUTOBACKOFFICE_LOGS_PATH=<caminho_para_salvar_logs>
AUTOBACKOFFICE_ENVIRONMENT=<dev|prod>
```

**Nota sobre `AUTOBACKOFFICE_ENVIRONMENT`**:
- `dev`: Utiliza quadros de desenvolvimento no Monday.com
- `prod`: Utiliza quadros de produção no Monday.com
- Valor padrão: `dev` (se não especificado)

#### Para o projeto `Expediente Único`:
Nenhuma variável de ambiente necessária (utiliza API pública da Procempa).

## Execução

### AutoBackoffice

Execute a sincronização entre Otto e Monday.com:

```bash
cd "Melnick Code"
python Projetos/AutoBackoffice/AutoBackoffice.py
```

O script irá:
1. Buscar atualizações no banco Otto desde a última execução
2. Sincronizar com o Monday.com (criar/atualizar negócios)
3. Salvar timestamp da última atualização
4. Gerar logs detalhados no caminho especificado em `AUTOBACKOFFICE_LOGS_PATH`

### Expediente Único

Execute consultas de expedientes da Procempa:

```bash
cd "Melnick Code"
python "Projetos/Expediente Único/main.py"
```

Este é um script de exemplo que demonstra como buscar expedientes por endereço.

## Documentação Adicional

Cada módulo e projeto possui documentação detalhada em arquivos separados:

- Documentação completa de cada módulo: Ver pasta `Código/Módulos/`
- Documentação de projetos específicos: Ver pasta `Código/Projetos/`
- Melhores práticas de desenvolvimento: Ver `Código/Melhores Práticas.md`

## Logs e Dados

- **Logs do AutoBackoffice**: Salvos no caminho definido em `AUTOBACKOFFICE_LOGS_PATH` com timestamp
- **Dados de controle**: `Projetos/AutoBackoffice/Dados/ultima_atualizacao.txt` armazena o horário da última sincronização bem-sucedida

## Suporte

Para questões sobre configuração ou uso dos módulos e projetos, consulte a documentação detalhada na pasta `Código/` ou entre em contato com a equipe de Controladoria Comercial.
