"""
Script para analisar a estrutura da página de empreendimentos da Melnick
Identifica: seletores CSS, comportamento do botão "Ver mais", links e imagens
"""

import requests
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

class MelnickAnalyzer:
    def __init__(self):
        self.base_url = "https://www.melnick.com.br"
        self.empreendimentos_url = f"{self.base_url}/empreendimentos/"
        self.driver = None
        
    def setup_driver(self):
        """Configura o Selenium WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        
    def analyze_page_structure(self):
        """Analisa a estrutura da página de empreendimentos"""
        print("=" * 80)
        print("ANÁLISE DA PÁGINA DE EMPREENDIMENTOS")
        print("=" * 80)
        
        try:
            self.driver.get(self.empreendimentos_url)
            time.sleep(3)
            
            # Captura o HTML
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. IDENTIFICAR SELETORES DOS CARDS
            print("\n1) SELETORES DOS CARDS DE EMPREENDIMENTOS:")
            print("-" * 80)
            
            # Procurar por diferentes estruturas comuns
            possible_selectors = [
                ('div.enterprise-card', 'Classe enterprise-card'),
                ('div.empreendimento-card', 'Classe empreendimento-card'),
                ('div.card-empreendimento', 'Classe card-empreendimento'),
                ('article.enterprise', 'Article enterprise'),
                ('div[data-enterprise]', 'Div com data-enterprise'),
                ('div.property-card', 'Classe property-card'),
                ('div.listing-item', 'Classe listing-item'),
            ]
            
            cards_found = []
            for selector, description in possible_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"✓ Encontrado: {description}")
                    print(f"  Seletor CSS: {selector}")
                    print(f"  Quantidade: {len(elements)}")
                    cards_found.append((selector, elements))
                    
                    # Mostrar estrutura do primeiro card
                    if len(elements) > 0:
                        first_card = elements[0]
                        print(f"  Classes do card: {first_card.get('class', [])}")
                        print(f"  Atributos: {first_card.attrs}")
                        print(f"  Estrutura interna:")
                        for child in first_card.find_all(recursive=False):
                            print(f"    - {child.name}: {child.get('class', [])}")
                    print()
            
            # Se não encontrou, mostrar estrutura geral
            if not cards_found:
                print("⚠ Seletores padrão não encontrados. Analisando estrutura geral...")
                main_content = soup.find('main') or soup.find('div', class_=lambda x: x and 'content' in x.lower())
                if main_content:
                    print("Estrutura do conteúdo principal:")
                    for element in main_content.find_all(['div', 'article', 'section'], limit=20):
                        classes = element.get('class', [])
                        if classes:
                            print(f"  - {element.name}.{'.'.join(classes[:3])}")
            
            # 2. ANALISAR BOTÃO "VER MAIS"
            print("\n2) ANÁLISE DO BOTÃO 'VER MAIS':")
            print("-" * 80)
            
            # Procurar botão "Ver mais"
            ver_mais_selectors = [
                'button:contains("Ver mais")',
                'a:contains("Ver mais")',
                'button.load-more',
                'button.ver-mais',
                'a.load-more',
                '.pagination button',
            ]
            
            # Usar Selenium para encontrar o botão
            ver_mais_found = False
            try:
                ver_mais_button = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Ver mais') or contains(text(), 'Carregar mais') or contains(text(), 'Load more')]")
                print(f"✓ Botão encontrado!")
                print(f"  Tag: {ver_mais_button.tag_name}")
                print(f"  Classes: {ver_mais_button.get_attribute('class')}")
                print(f"  ID: {ver_mais_button.get_attribute('id')}")
                print(f"  Atributos data-*: ", end="")
                
                attrs = self.driver.execute_script(
                    "var items = {}; for (var i = 0; i < arguments[0].attributes.length; i++) { "
                    "var attr = arguments[0].attributes[i]; "
                    "if (attr.name.startsWith('data-')) items[attr.name] = attr.value; } "
                    "return items;", ver_mais_button
                )
                print(json.dumps(attrs, indent=4))
                
                # Interceptar requests de rede
                print("\n  Testando comportamento do botão...")
                
                # Contar elementos antes
                cards_before = len(self.driver.find_elements(By.CSS_SELECTOR, "div[class*='card'], article[class*='enterprise']"))
                print(f"  Cards visíveis antes: {cards_before}")
                
                # Clicar no botão
                self.driver.execute_script("arguments[0].scrollIntoView(true);", ver_mais_button)
                time.sleep(1)
                ver_mais_button.click()
                time.sleep(3)
                
                # Contar elementos depois
                cards_after = len(self.driver.find_elements(By.CSS_SELECTOR, "div[class*='card'], article[class*='enterprise']"))
                print(f"  Cards visíveis depois: {cards_after}")
                
                if cards_after > cards_before:
                    print(f"  ✓ Novos cards carregados: {cards_after - cards_before}")
                    print("  Comportamento: Provavelmente carrega via AJAX/XHR")
                else:
                    print("  Comportamento: Provavelmente revela elementos do DOM")
                
                ver_mais_found = True
                
            except Exception as e:
                print(f"⚠ Botão 'Ver mais' não encontrado ou erro: {e}")
            
            # Verificar chamadas de rede (performance logs)
            print("\n  Verificando chamadas de rede...")
            try:
                logs = self.driver.get_log('performance')
                api_calls = []
                for log in logs:
                    message = json.loads(log['message'])
                    if message['message']['method'] == 'Network.requestWillBeSent':
                        url = message['message']['params']['request']['url']
                        if 'api' in url.lower() or 'ajax' in url.lower() or 'empreendimento' in url.lower():
                            api_calls.append(url)
                
                if api_calls:
                    print("  APIs/Endpoints encontrados:")
                    for api in set(api_calls):
                        print(f"    - {api}")
                else:
                    print("  Nenhuma chamada de API específica detectada")
            except:
                print("  (Logs de performance não disponíveis)")
            
            # 3. LINKS DOS EMPREENDIMENTOS
            print("\n3) LINKS DOS EMPREENDIMENTOS:")
            print("-" * 80)
            
            # Procurar links nos cards
            links = []
            
            # Método 1: Links diretos nos cards
            card_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='enterprise'], a[href*='empreendimento']")
            if card_links:
                print(f"✓ Encontrados {len(card_links)} links de empreendimentos")
                for i, link in enumerate(card_links[:5]):
                    href = link.get_attribute('href')
                    text = link.text.strip()
                    classes = link.get_attribute('class')
                    print(f"  Link {i+1}:")
                    print(f"    URL: {href}")
                    print(f"    Texto: {text}")
                    print(f"    Classes: {classes}")
                    links.append(href)
            
            # Método 2: Botões "Conheça" no mapa
            conheca_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Conheça') or contains(text(), 'Saiba mais')]")
            if conheca_buttons:
                print(f"\n✓ Encontrados {len(conheca_buttons)} botões 'Conheça/Saiba mais'")
                for i, btn in enumerate(conheca_buttons[:3]):
                    print(f"  Botão {i+1}:")
                    print(f"    Tag: {btn.tag_name}")
                    print(f"    Classes: {btn.get_attribute('class')}")
                    if btn.tag_name == 'a':
                        print(f"    Href: {btn.get_attribute('href')}")
            
            # Pegar o primeiro link válido para análise
            if links:
                first_link = links[0]
                print(f"\n  Padrão de URL: {first_link}")
                print(f"  Seletor recomendado: a[href*='/enterprise/'], a[href*='/empreendimento/']")
                
                return first_link
            
        except Exception as e:
            print(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
            
        return None
    
    def analyze_enterprise_page(self, enterprise_url):
        """Analisa a página de um empreendimento específico"""
        print("\n" + "=" * 80)
        print("ANÁLISE DA PÁGINA DO EMPREENDIMENTO")
        print("=" * 80)
        
        try:
            self.driver.get(enterprise_url)
            time.sleep(3)
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            print(f"\nURL: {enterprise_url}")
            
            # 4. IMAGENS DA GALERIA
            print("\n4) URLS DAS IMAGENS:")
            print("-" * 80)
            
            # Galeria principal
            print("\nA) GALERIA PRINCIPAL:")
            gallery_selectors = [
                'img[src*="gallery"]',
                'img[src*="galeria"]',
                '.gallery img',
                '.galeria img',
                '[class*="slider"] img',
                '[class*="carousel"] img',
                '.swiper-slide img',
            ]
            
            gallery_images = []
            for selector in gallery_selectors:
                images = soup.select(selector)
                if images:
                    print(f"  Seletor: {selector} ({len(images)} imagens)")
                    for i, img in enumerate(images[:3]):
                        src = img.get('src', '') or img.get('data-src', '')
                        print(f"    {i+1}. {src}")
                        gallery_images.append(src)
            
            # Plantas
            print("\nB) PLANTAS:")
            planta_selectors = [
                'img[src*="planta"]',
                'img[alt*="planta"]',
                '.plantas img',
                '[class*="floor-plan"] img',
            ]
            
            for selector in planta_selectors:
                images = soup.select(selector)
                if images:
                    print(f"  Seletor: {selector} ({len(images)} imagens)")
                    for i, img in enumerate(images[:3]):
                        src = img.get('src', '') or img.get('data-src', '')
                        print(f"    {i+1}. {src}")
            
            # Características/Diferenciais
            print("\nC) CARACTERÍSTICAS/DIFERENCIAIS:")
            feature_selectors = [
                'img[src*="caracteristica"]',
                'img[src*="diferencial"]',
                '.features img',
                '.caracteristicas img',
                '.diferenciais img',
            ]
            
            for selector in feature_selectors:
                images = soup.select(selector)
                if images:
                    print(f"  Seletor: {selector} ({len(images)} imagens)")
                    for i, img in enumerate(images[:3]):
                        src = img.get('src', '') or img.get('data-src', '')
                        print(f"    {i+1}. {src}")
            
            # Todas as imagens da página
            print("\nD) RESUMO DE TODAS AS IMAGENS:")
            all_images = soup.find_all('img')
            print(f"  Total de imagens na página: {len(all_images)}")
            
            # Agrupar por padrão de URL
            image_patterns = {}
            for img in all_images:
                src = img.get('src', '') or img.get('data-src', '')
                if src:
                    # Extrair padrão (domínio + primeiro path)
                    if 'http' in src:
                        parts = src.split('/')
                        if len(parts) >= 4:
                            pattern = '/'.join(parts[:4])
                            image_patterns[pattern] = image_patterns.get(pattern, 0) + 1
            
            print("\n  Padrões de URL encontrados:")
            for pattern, count in sorted(image_patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"    {pattern}/... ({count} imagens)")
            
            # Verificar se há lazy loading
            lazy_images = soup.find_all(['img', 'div'], attrs={'data-src': True})
            if lazy_images:
                print(f"\n  ⚠ Lazy loading detectado: {len(lazy_images)} elementos com data-src")
                print("    Use 'data-src' além de 'src' para capturar todas as imagens")
            
        except Exception as e:
            print(f"Erro na análise da página do empreendimento: {e}")
            import traceback
            traceback.print_exc()
    
    def run_full_analysis(self):
        """Executa análise completa"""
        try:
            print("Iniciando análise do site Melnick...")
            print("Configurando navegador...\n")
            
            self.setup_driver()
            
            # Analisar página principal
            enterprise_url = self.analyze_page_structure()
            
            # Analisar página de empreendimento
            if enterprise_url:
                self.analyze_enterprise_page(enterprise_url)
            else:
                print("\n⚠ Não foi possível encontrar URL de empreendimento para análise detalhada")
            
            print("\n" + "=" * 80)
            print("ANÁLISE CONCLUÍDA")
            print("=" * 80)
            
        except Exception as e:
            print(f"Erro geral: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    analyzer = MelnickAnalyzer()
    analyzer.run_full_analysis()
