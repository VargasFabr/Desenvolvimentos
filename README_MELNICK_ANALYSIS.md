# Análise do Site Melnick - Scripts de Scraping

## Objetivo

Analisar a estrutura da página de empreendimentos da Melnick (https://www.melnick.com.br/empreendimentos/) para identificar:

1. **Seletores CSS** dos cards de empreendimentos
2. **Comportamento do botão "Ver mais"** (AJAX/XHR ou revelação de DOM)
3. **Links para páginas de empreendimentos** (botão "Conheça" ou link direto)
4. **URLs das imagens** (galeria, plantas, características)

## Scripts Disponíveis

### 1. `melnick_simple_analysis.py` ⭐ RECOMENDADO PARA COMEÇAR

**Análise estática usando apenas requests + BeautifulSoup**

- ✅ Mais simples de executar
- ✅ Não requer ChromeDriver
- ✅ Salva HTML para inspeção manual
- ⚠️ Não detecta conteúdo carregado dinamicamente via JavaScript

**Como executar:**

```bash
# Instalar dependências
pip install -r requirements_melnick_analysis.txt

# Executar análise
python melnick_simple_analysis.py
```

**Saída:**
- Console com análise detalhada
- `melnick_page.html` - HTML da página principal
- `[nome-empreendimento].html` - HTML de um empreendimento específico

### 2. `melnick_scraper_analysis.py`

**Análise dinâmica usando Selenium**

- ✅ Detecta conteúdo carregado via JavaScript
- ✅ Testa cliques no botão "Ver mais"
- ✅ Intercepta chamadas de rede (APIs)
- ⚠️ Requer ChromeDriver instalado

**Como executar:**

```bash
# Instalar dependências
pip install -r requirements_melnick_analysis.txt

# Instalar ChromeDriver (escolha uma opção):
# Opção 1: Usando webdriver-manager
pip install webdriver-manager

# Opção 2: Download manual
# Baixe de: https://chromedriver.chromium.org/
# Coloque no PATH do sistema

# Executar análise
python melnick_scraper_analysis.py
```

## O Que os Scripts Retornam

### 1. Seletores dos Cards

```
✓ Seletor CSS: div.enterprise-card
  Quantidade: 12
  Classes: ['enterprise-card', 'card-item']
  Estrutura interna:
    - div: ['card-image']
    - div: ['card-content']
    - a: ['card-link']
```

### 2. Comportamento do Botão "Ver Mais"

```
✓ Botão encontrado!
  Tag: button
  Classes: load-more btn-primary
  Atributos data-*: {"data-action": "load-more", "data-page": "1"}
  
  Cards visíveis antes: 12
  Cards visíveis depois: 24
  ✓ Novos cards carregados: 12
  Comportamento: Provavelmente carrega via AJAX/XHR
  
  APIs/Endpoints encontrados:
    - https://www.melnick.com.br/wp-json/melnick/v1/enterprises
```

### 3. Links dos Empreendimentos

```
✓ Encontrados 12 links de empreendimentos
  Link 1:
    URL: https://www.melnick.com.br/enterprise/hom-lindoia/
    Texto: Hom Lindóia
    Classes: enterprise-link
    
  Padrão de URL: https://www.melnick.com.br/enterprise/[slug]/
  Seletor recomendado: a[href*='/enterprise/']
```

### 4. URLs das Imagens

```
A) GALERIA PRINCIPAL:
  Seletor: .gallery img (15 imagens)
    1. https://cdn.melnick.com.br/uploads/2024/01/gallery-01.jpg
    2. https://cdn.melnick.com.br/uploads/2024/01/gallery-02.jpg

B) PLANTAS:
  Seletor: .plantas img (5 imagens)
    1. https://cdn.melnick.com.br/uploads/2024/01/planta-tipo-1.jpg

C) CARACTERÍSTICAS:
  Seletor: .features img (8 imagens)
    1. https://cdn.melnick.com.br/uploads/2024/01/feature-piscina.jpg

D) PADRÕES DE URL:
  https://cdn.melnick.com.br/... (28 imagens)
  
⚠ Lazy loading detectado: 15 elementos com data-src
  Use 'data-src' além de 'src' para capturar todas as imagens
```

## Próximos Passos

Após executar os scripts, você terá:

1. **Seletores CSS confiáveis** para extrair dados
2. **Endpoints de API** (se houver)
3. **Estrutura HTML** salva para análise manual
4. **Padrões de URL** para imagens

Com essas informações, você pode:

- Criar um scraper completo
- Automatizar extração de dados
- Monitorar novos empreendimentos
- Baixar imagens em massa

## Troubleshooting

### Erro: "ChromeDriver not found"
```bash
pip install webdriver-manager
```

Ou use o script simples: `melnick_simple_analysis.py`

### Erro: "Connection timeout"
- Verifique sua conexão com internet
- O site pode estar bloqueando bots (use User-Agent)
- Tente aumentar o timeout no código

### Página HTML vazia ou incompleta
- O conteúdo pode ser carregado via JavaScript
- Use o script com Selenium: `melnick_scraper_analysis.py`

## Observações Importantes

⚠️ **Respeite os Termos de Uso do site**
⚠️ **Não faça requisições excessivas** (use delays entre requests)
⚠️ **Verifique o robots.txt**: https://www.melnick.com.br/robots.txt

## Contato

Para dúvidas ou melhorias, consulte a documentação dos scripts.
