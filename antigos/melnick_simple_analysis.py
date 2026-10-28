"""
Versão simplificada - Análise básica sem Selenium
Usa apenas requests + BeautifulSoup para análise estática
"""

import requests
from bs4 import BeautifulSoup
import json
import re

class MelnickSimpleAnalyzer:
    def __init__(self):
        self.base_url = "https://www.melnick.com.br"
        self.empreendimentos_url = f"{self.base_url}/empreendimentos/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def analyze_page(self):
        """Analisa a estrutura da página"""
        print("=" * 80)
        print("ANÁLISE SIMPLIFICADA - PÁGINA DE EMPREENDIMENTOS")
        print("=" * 80)
        
        try:
            print(f"\nBuscando: {self.empreendimentos_url}")
            response = self.session.get(self.empreendimentos_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Salvar HTML para inspeção manual
            with open('melnick_page.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("✓ HTML salvo em: melnick_page.html")
            
            # 1. ESTRUTURA GERAL
            print("\n1) ESTRUTURA GERAL DA PÁGINA:")
            print("-" * 80)
            
            # Procurar por scripts com dados JSON
            scripts = soup.find_all('script', type='application/ld+json')
            if scripts:
                print(f"✓ Encontrados {len(scripts)} scripts JSON-LD")
                for i, script in enumerate(scripts):
                    try:
                        data = json.loads(script.string)
                        print(f"\nScript {i+1}:")
                        print(json.dumps(data, indent=2)[:500])
                    except:
                        pass
            
            # Procurar por variáveis JavaScript com dados
            all_scripts = soup.find_all('script')
            for script in all_scripts:
                if script.string:
                    # Procurar por padrões de dados
                    if 'enterprise' in script.string.lower() or 'empreendimento' in script.string.lower():
                        # Tentar extrair objetos JSON
                        json_matches = re.findall(r'({[^{}]*(?:{[^{}]*}[^{}]*)*})', script.string)
                        if json_matches:
                            print("\n✓ Dados JavaScript encontrados:")
                            for match in json_matches[:2]:
                                if len(match) > 50:
                                    print(match[:200] + "...")
            
            # 2. CARDS DE EMPREENDIMENTOS
            print("\n2) PROCURANDO CARDS DE EMPREENDIMENTOS:")
            print("-" * 80)
            
            # Lista de seletores para testar
            selectors_to_test = [
                'div.enterprise-card',
                'div.empreendimento-card', 
                'article.enterprise',
                'div[class*="enterprise"]',
                'div[class*="empreendimento"]',
                'div[class*="card"]',
                'article[class*="card"]',
                'div[data-enterprise-id]',
                'div[data-id]',
            ]
            
            found_cards = []
            for selector in selectors_to_test:
                elements = soup.select(selector)
                if elements and len(elements) > 2:
                    print(f"\n✓ Seletor: {selector}")
                    print(f"  Quantidade: {len(elements)}")
                    
                    # Analisar primeiro elemento
                    first = elements[0]
                    print(f"  Classes: {first.get('class', [])}")
                    print(f"  Atributos: {list(first.attrs.keys())}")
                    
                    # Procurar links dentro
                    links = first.find_all('a', href=True)
                    if links:
                        print(f"  Links encontrados: {len(links)}")
                        for link in links[:2]:
                            print(f"    - {link.get('href')}")
                    
                    found_cards.append((selector, elements))
            
            if not found_cards:
                print("\n⚠ Seletores padrão não encontrados")
                print("Mostrando todas as divs com classe 'card' ou similar:")
                all_divs = soup.find_all('div', class_=re.compile(r'card|item|box', re.I))
                print(f"Total encontrado: {len(all_divs)}")
                for div in all_divs[:5]:
                    print(f"  - Classes: {div.get('class', [])}")
            
            # 3. BOTÃO VER MAIS
            print("\n3) BOTÃO 'VER MAIS':")
            print("-" * 80)
            
            ver_mais = soup.find(['button', 'a'], string=re.compile(r'ver\s+mais|carregar\s+mais|load\s+more', re.I))
            if ver_mais:
                print("✓ Botão encontrado!")
                print(f"  Tag: {ver_mais.name}")
                print(f"  Classes: {ver_mais.get('class', [])}")
                print(f"  ID: {ver_mais.get('id', 'N/A')}")
                print(f"  Atributos data-*:")
                for attr, value in ver_mais.attrs.items():
                    if attr.startswith('data-'):
                        print(f"    {attr}: {value}")
                
                # Se for botão, provavelmente usa AJAX
                if ver_mais.name == 'button':
                    print("\n  Análise: Botão <button> geralmente indica carregamento AJAX/XHR")
                elif ver_mais.get('href', '#') == '#':
                    print("\n  Análise: Link com href='#' geralmente indica JavaScript/AJAX")
                else:
                    print("\n  Análise: Link normal, pode ser paginação tradicional")
            else:
                print("⚠ Botão 'Ver mais' não encontrado na versão estática")
                print("  (Pode ser carregado dinamicamente via JavaScript)")
            
            # 4. LINKS DE EMPREENDIMENTOS
            print("\n4) LINKS DOS EMPREENDIMENTOS:")
            print("-" * 80)
            
            enterprise_links = soup.find_all('a', href=re.compile(r'/enterprise/|/empreendimento/', re.I))
            if enterprise_links:
                print(f"✓ Encontrados {len(enterprise_links)} links")
                unique_links = list(set([link.get('href') for link in enterprise_links]))
                print(f"  Links únicos: {len(unique_links)}")
                
                for i, link in enumerate(unique_links[:5]):
                    full_url = link if link.startswith('http') else self.base_url + link
                    print(f"  {i+1}. {full_url}")
                
                # Analisar primeiro empreendimento
                if unique_links:
                    first_url = unique_links[0]
                    if not first_url.startswith('http'):
                        first_url = self.base_url + first_url
                    
                    print(f"\n  Analisando primeiro empreendimento...")
                    self.analyze_enterprise_page(first_url)
            else:
                print("⚠ Nenhum link de empreendimento encontrado")
            
            # 5. POSSÍVEIS ENDPOINTS DE API
            print("\n5) POSSÍVEIS ENDPOINTS DE API:")
            print("-" * 80)
            
            # Procurar por URLs de API no HTML/JavaScript
            api_patterns = [
                r'https?://[^"\s]+/api/[^"\s]+',
                r'https?://[^"\s]+/wp-json/[^"\s]+',
                r'"/api/[^"]+',
                r'"/ajax/[^"]+',
            ]
            
            api_urls = set()
            for pattern in api_patterns:
                matches = re.findall(pattern, response.text)
                api_urls.update(matches)
            
            if api_urls:
                print("✓ Possíveis endpoints encontrados:")
                for url in sorted(api_urls)[:10]:
                    print(f"  - {url}")
            else:
                print("⚠ Nenhum endpoint de API óbvio encontrado no HTML")
            
        except requests.exceptions.RequestException as e:
            print(f"Erro ao acessar a página: {e}")
        except Exception as e:
            print(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_enterprise_page(self, url):
        """Analisa página de um empreendimento específico"""
        print("\n" + "=" * 80)
        print("ANÁLISE DA PÁGINA DO EMPREENDIMENTO")
        print("=" * 80)
        print(f"URL: {url}\n")
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Salvar HTML
            filename = url.split('/')[-2] + '.html'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print(f"✓ HTML salvo em: {filename}")
            
            # IMAGENS
            print("\n4) IMAGENS DO EMPREENDIMENTO:")
            print("-" * 80)
            
            all_images = soup.find_all('img')
            print(f"Total de imagens: {len(all_images)}")
            
            # Categorizar imagens
            galleries = []
            plantas = []
            features = []
            outros = []
            
            for img in all_images:
                src = img.get('src', '') or img.get('data-src', '')
                alt = img.get('alt', '').lower()
                
                if not src:
                    continue
                
                if 'planta' in src.lower() or 'planta' in alt:
                    plantas.append(src)
                elif 'galeria' in src.lower() or 'gallery' in src.lower():
                    galleries.append(src)
                elif 'caracteristica' in src.lower() or 'diferencial' in src.lower() or 'feature' in src.lower():
                    features.append(src)
                else:
                    outros.append(src)
            
            if galleries:
                print(f"\nA) GALERIA ({len(galleries)} imagens):")
                for i, img in enumerate(galleries[:3]):
                    print(f"  {i+1}. {img}")
            
            if plantas:
                print(f"\nB) PLANTAS ({len(plantas)} imagens):")
                for i, img in enumerate(plantas[:3]):
                    print(f"  {i+1}. {img}")
            
            if features:
                print(f"\nC) CARACTERÍSTICAS ({len(features)} imagens):")
                for i, img in enumerate(features[:3]):
                    print(f"  {i+1}. {img}")
            
            # Padrões de URL
            print("\nD) PADRÕES DE URL DAS IMAGENS:")
            url_patterns = {}
            for img in all_images:
                src = img.get('src', '') or img.get('data-src', '')
                if src and 'http' in src:
                    domain = '/'.join(src.split('/')[:3])
                    url_patterns[domain] = url_patterns.get(domain, 0) + 1
            
            for pattern, count in sorted(url_patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"  {pattern} ({count} imagens)")
            
            # Seletores recomendados
            print("\nE) SELETORES CSS RECOMENDADOS:")
            
            # Galeria
            gallery_container = soup.find(['div', 'section'], class_=re.compile(r'galer|gallery|slider|carousel', re.I))
            if gallery_container:
                classes = gallery_container.get('class', [])
                print(f"  Galeria: .{'.'.join(classes)} img")
            
            # Plantas
            plantas_container = soup.find(['div', 'section'], class_=re.compile(r'planta|floor', re.I))
            if plantas_container:
                classes = plantas_container.get('class', [])
                print(f"  Plantas: .{'.'.join(classes)} img")
            
            # Lazy loading
            lazy_imgs = soup.find_all(['img', 'div'], attrs={'data-src': True})
            if lazy_imgs:
                print(f"\n⚠ Lazy loading detectado: {len(lazy_imgs)} elementos")
                print("  Use: img[data-src], div[data-src]")
            
        except Exception as e:
            print(f"Erro ao analisar empreendimento: {e}")

if __name__ == "__main__":
    analyzer = MelnickSimpleAnalyzer()
    analyzer.analyze_page()
    
    print("\n" + "=" * 80)
    print("ANÁLISE CONCLUÍDA")
    print("=" * 80)
    print("\nArquivos HTML salvos para inspeção manual.")
    print("Você pode abri-los no navegador ou editor de texto para ver a estrutura completa.")
