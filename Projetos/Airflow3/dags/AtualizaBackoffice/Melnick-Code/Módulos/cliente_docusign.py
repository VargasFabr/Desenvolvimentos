# Cliente para interação com o Docusign e sua API

# Não usa o acesso oficial a API, mas simula os requests
# HTTP feitos pelo front-end web

#--------------------------------
# PONTOS IMPORTANTES
#--------------------------------
"""
- O nome do contrato no Docu segue a nomeclatura padrão do GC para os empreendimentos,
que deve ser a mesma usada no Monday.com e no Otto, que ligam no GC

- O nome do cliente já não é padronizado e deve ter uma maneira diferente de lidar a procura

- Procurar matches de contratos no Docu somente para negócios em emissão.
Negócios com IDs de contrato só podem receber outro contrato se estiverem cancelados/negados.
Fazer o fuzzy match e dar o contrato para o negócio com maior score mas com um score mínimo aceitável.
Fazer uma label com o status do contrato em geral (ex: "Enviado", "Assinado", "Cancelado") e outra
com o status de assinaturas.
"""
# %%
from typing import Literal
import os
import sys
import requests
import json
import time
import tempfile
import shutil
from datetime import datetime, timezone, timedelta

_repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repository_root not in sys.path:
    sys.path.insert(0, _repository_root)

# Monta o caminho esperado para o arquivo .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Carrega as variáveis de ambiente do arquivo .env
import dotenv
dotenv.load_dotenv(env_path)

#--------------------------------
# LOGGER
import logging

# # Verifica se o logger root já tem handlers configurados
# root_logger = logging.getLogger()

# if not root_logger.handlers: # Se não houver handlers
#     # Configura um básico para console
#     logging.basicConfig(
#         level=logging.DEBUG,
#         format='%(name)s - %(levelname)s - %(message)s',
#         handlers=[logging.StreamHandler()]
#     )

logger = logging.getLogger("Cliente DocuSign")
# logger.setLevel(logging.INFO)

#--------------------------------

class DocuClient:
    _LINUX_CHROME_PATHS = (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/google-chrome",
    )
    _WRITABLE_DATA_FALLBACKS = (
        "/opt/airflow/data/docusign",
    )

    def __init__(self, user: str, password: str, account_id: str, data_file_path: str) -> None:
        self.user = user
        self.password = password
        self.account_id = account_id
        self.data_file_path = data_file_path
        self.storage_path = self._resolve_storage_path(data_file_path)
        self._seed_storage_from_preferred_path()
        self._browser_renewal_unavailable_reason: str | None = None
        self._outlook_client = None
        self._mfa_requested_at: datetime | None = None
        self._last_security_code: str | None = None
        os.makedirs(self.storage_path, exist_ok=True)

        # Tenta carregar o token existente no .env
        self.token = self.token_manager('load')

        logger.debug(f"Token carregado: {self.token}")

        # Tenta carregar os dados locais
        self.data_manager('load')

    @staticmethod
    def _is_writable_dir(path: str) -> bool:
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(test_file)
            return True
        except OSError:
            return False

    def _resolve_storage_path(self, preferred_path: str) -> str:
        candidates: list[str] = []
        env_override = os.getenv("DOCUSIGN_DATA_PATH")
        if env_override:
            candidates.append(env_override)
        candidates.append(preferred_path)
        candidates.extend(self._WRITABLE_DATA_FALLBACKS)
        candidates.append(os.path.join(tempfile.gettempdir(), "melnick_docusign"))

        for path in candidates:
            if self._is_writable_dir(path):
                if path != preferred_path:
                    logger.info("Usando diretório gravável para dados DocuSign: %s", path)
                return path

        logger.warning(
            "Nenhum diretório gravável encontrado. Mantendo caminho original: %s",
            preferred_path,
        )
        return preferred_path

    def _seed_storage_from_preferred_path(self) -> None:
        if self.storage_path == self.data_file_path:
            return

        source_files = ("dados_cliente_docusign.json",)
        for filename in source_files:
            source = os.path.join(self.data_file_path, filename)
            target = os.path.join(self.storage_path, filename)
            if os.path.exists(source) and not os.path.exists(target):
                try:
                    shutil.copy2(source, target)
                except OSError as exc:
                    logger.debug("Não foi possível copiar %s: %s", filename, exc)

        source_cookies = os.path.join(self.data_file_path, "Cookies")
        target_cookies = os.path.join(self.storage_path, "Cookies")
        if os.path.isdir(source_cookies) and not os.path.isdir(target_cookies):
            try:
                shutil.copytree(source_cookies, target_cookies)
            except OSError as exc:
                logger.debug("Não foi possível copiar cookies salvos: %s", exc)

    def _resolve_chrome_bin(self) -> str | None:
        """Localiza o executável do Chrome/Chromium no sistema atual."""
        import shutil
        import platform
        import subprocess

        chrome_bin = os.getenv("GOOGLE_CHROME_BIN") or os.getenv("CHROME_BIN")
        if chrome_bin and os.path.exists(chrome_bin):
            return chrome_bin

        if platform.system() == "Windows":
            windows_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Chromium\Application\chrome.exe",
            ]
            for path in windows_paths:
                if os.path.exists(path):
                    return path

            try:
                result = subprocess.run(
                    ['where', 'chrome'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.stdout:
                    return result.stdout.strip().split('\n')[0]
            except Exception:
                pass
            return None

        for binary_name in (
            "google-chrome-stable",
            "google-chrome",
            "chromium",
            "chromium-browser",
        ):
            found = shutil.which(binary_name)
            if found:
                return found

        for path in self._LINUX_CHROME_PATHS:
            if os.path.exists(path):
                return path

        return None

    def _browser_renewal_error_message(self) -> str:
        import platform

        return (
            "Chrome/Chromium não encontrado. "
            "Instale o Google Chrome/Chromium no worker do Airflow ou defina "
            "GOOGLE_CHROME_BIN/CHROME_BIN nas variáveis de ambiente. "
            "Alternativamente, renove DOCUSIGN_TOKEN manualmente em uma máquina "
            "com Chrome e atualize o .env/variáveis do Airflow. "
            f"Sistema operacional detectado: {platform.system()}"
        )

    def _can_renew_token_via_browser(self) -> bool:
        """Indica se a renovação automática via Selenium pode ser tentada."""
        if os.getenv("DOCUSIGN_DISABLE_BROWSER_RENEWAL", "").lower() in ("1", "true", "yes"):
            self._browser_renewal_unavailable_reason = (
                "Renovação via navegador desabilitada por DOCUSIGN_DISABLE_BROWSER_RENEWAL."
            )
            return False

        if self._browser_renewal_unavailable_reason:
            return False

        chrome_bin = self._resolve_chrome_bin()
        if chrome_bin:
            return True

        self._browser_renewal_unavailable_reason = self._browser_renewal_error_message()
        return False

    def setup_driver(self) -> None:
        """
        Configura o driver do Selenium para automação web.
        Funciona em Windows, Linux e Docker.
        """
        # Importa o Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager       
        import shutil

        # Configura as opções do Chrome
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')  # Executa em modo headless (sem interface gráfica)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        chrome_bin = self._resolve_chrome_bin()
        if not chrome_bin:
            error_message = self._browser_renewal_error_message()
            self._browser_renewal_unavailable_reason = error_message
            raise RuntimeError(error_message)
        
        options.binary_location = chrome_bin
        logger.info(f"Usando Chrome: {chrome_bin}")

        # Procura pelo ChromeDriver
        chromedriver_bin = (
            os.getenv("CHROMEDRIVER_PATH")
            or shutil.which("chromedriver")
            or shutil.which("chromium-driver")
        )
        
        if chromedriver_bin:
            logger.info(f"Usando chromedriver local: {chromedriver_bin}")
            service = Service(chromedriver_bin)
        else:
            logger.info("Chromedriver local não encontrado. Baixando via webdriver_manager...")
            try:
                service = Service(ChromeDriverManager().install())
            except Exception as e:
                logger.warning(f"Erro ao baixar ChromeDriver: {e}. Tentando usar versão padrão...")
                service = Service()
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)  # Espera implícita de 10 segundos
        logger.info("Driver Selenium configurado com sucesso")

        return None
    
    def _get_outlook_client(self):
        if self._outlook_client is None:
            try:
                from Módulos.cliente_outlook import build_outlook_client_from_env
            except ModuleNotFoundError:
                from cliente_outlook import build_outlook_client_from_env

            outlook_data_path = os.path.join(self.storage_path, "Outlook")
            self._outlook_client = build_outlook_client_from_env(
                data_file_path=outlook_data_path,
                fallback_user=self.user,
            )
        return self._outlook_client

    def _get_security_code(self) -> str:
        logger.info("Buscando código MFA do DocuSign no Outlook...")
        outlook_client = self._get_outlook_client()
        return outlook_client.get_docusign_mfa_code(requested_after=self._mfa_requested_at)

    def fill_input_field(self) -> str:
        from selenium.webdriver.common.by import By
        action = "none"
        input_field = self.driver.find_elements(By.TAG_NAME, "input")
        # Encontra o nome do campo encontrado
        for field in input_field:
            field_name = field.get_attribute("name")
            is_hidden = field.get_attribute("aria-hidden") == "true"
            print(f"Campo encontrado: {field_name}")
            # Se for email, preenche com o usuário
            if field_name == "email" and not is_hidden:
                print("Preenchendo usuário...")
                field.send_keys(self.user)
                action = "email"
                break  # Sai do loop após preencher o email
            elif field_name == "password" and not is_hidden:
                print("Preenchendo senha...")
                field.send_keys(self.password)
                self._mfa_requested_at = datetime.now(timezone.utc) - timedelta(seconds=5)
                action = "password"
                break  # Sai do loop após preencher a senha
            elif field_name == "security_code" and not is_hidden:
                logger.warning("Código de segurança requerido.")
                print("Código do email necessário...")

                security_code = self._get_security_code()
                if self._last_security_code == security_code:
                    raise RuntimeError(
                        "O código MFA obtido é igual ao da tentativa anterior. "
                        "Aguarde um novo e-mail do DocuSign."
                    )

                logger.info("Código de segurança obtido com sucesso.")
                print(f"Código de segurança obtido: {security_code}")
                field.clear()
                field.send_keys(security_code)
                self._last_security_code = security_code
                action = "security_code"
                break  # Sai do loop após preencher o código de segurança
        
        time.sleep(5)  # Espera antes de submeter

        submit_buttons = self.driver.find_elements(By.TAG_NAME, "button")
        for button in submit_buttons:
            #print(button)
            button_type = button.get_attribute("type")
            print(f"Botão encontrado: {button_type}")
            if button_type == "submit":
                print("Clicando no botão de submit...")
                button.click()
                break

        return action
    
    def _is_on_mfa_page(self) -> bool:
        from selenium.webdriver.common.by import By

        for field in self.driver.find_elements(By.TAG_NAME, "input"):
            if field.get_attribute("name") == "security_code":
                if field.get_attribute("aria-hidden") != "true":
                    return True
        return False

    def login(self):
        """
        Realiza o login no DocuSign usando o Selenium.
        """
        # Garante que o driver está configurado
        if not hasattr(self, 'driver'):
            self.setup_driver()

        # Carrega os cookies salvos
        self.cookies_manager('load')

        # Acessa a página de login
        self.driver.get("https://account.docusign.com/oauth/auth?ui_locales=pt-BR")
        
        logged_in = False
        retries = 0
        max_retries = 10
        mfa_attempts = 0
        max_mfa_attempts = 3

        while not logged_in and retries < max_retries:

            time.sleep(5)  # Espera a página carregar
            
            # Confirma se a URL atual é a página já logada
            current_url = self.driver.current_url
            if "apps.docusign.com/send/home" in current_url:
                logger.debug("Login bem-sucedido no DocuSign.")
                print("Login bem-sucedido no DocuSign.")
                logged_in = True
                break
            
            # Se não for, seguimos com as tentativas de login
            try:
                action = self.fill_input_field()
            except RuntimeError as exc:
                logger.error("Falha ao obter/preencher código MFA: %s", exc)
                mfa_attempts += 1
                retries += 1
                if mfa_attempts >= max_mfa_attempts:
                    raise
                continue

            if action == "none":
                logger.error("Nenhum campo de login preenchido. Verifique as credenciais.")
                retries += 1
                continue
            elif action == "email":
                retries += 1
            elif action == "password":
                retries += 1
            elif action == "security_code":
                mfa_attempts += 1
                time.sleep(5)
                if mfa_attempts >= max_mfa_attempts and self._is_on_mfa_page():
                    raise RuntimeError(
                        "Código MFA rejeitado pelo DocuSign após múltiplas tentativas."
                    )
            else:
                logger.error("Ação desconhecida durante o login.")
                retries += 1
                continue

        if not logged_in:
            raise RuntimeError("Não foi possível concluir o login no DocuSign.")

        self.cookies_manager('save')  # Salva os cookies após o login bem-sucedido

    def cookies_manager(self, operation: str):
        """Gerencia os cookies da sessão atual, salvando em arquivos e os carregando"""

        import pickle
        if operation not in ['save', 'load']:
            raise ValueError("Operação inválida. Use 'save' ou 'load'.")
        
        if not hasattr(self, 'driver') or self.driver is None:
            raise ValueError("Driver não está configurado.")
        
        # Garante que a pasta de cookies existe
        cookies_file_path = os.path.join(self.storage_path, "Cookies")
        os.makedirs(cookies_file_path, exist_ok=True)
        
        urls = {
            #"apps": "https://apps.docusign.com",
            "account": "https://account.docusign.com"
            #"home": "https://apps.docusign.com/send/home",
            #"reports": "https://apps.docusign.com/send/reports/6/S6",
            #"oauth": "https://account.docusign.com/oauth/auth?ui_locales=pt-BR"
        }

        for nome, url in urls.items():
            print(f"Acessando: {url}\nNome: {nome}")
            self.driver.get(url)
            time.sleep(2)  # Aguarda o carregamento da página
            cookie_file = os.path.join(cookies_file_path, f"{nome}.pkl")
            if operation == 'save':
                try:
                    with open(cookie_file, "wb") as handle:
                        pickle.dump(self.driver.get_cookies(), handle)
                except OSError as exc:
                    logger.warning("Não foi possível salvar cookies em %s: %s", cookie_file, exc)
            elif operation == 'load':
                try:
                    with open(cookie_file, "rb") as handle:
                        cookies = pickle.load(handle)
                except FileNotFoundError:
                    print(f"Arquivo de cookies para {nome} não encontrado.")
                    continue
                except OSError as exc:
                    logger.warning("Não foi possível carregar cookies de %s: %s", cookie_file, exc)
                    continue
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception:
                        continue
    
    def get_new_token(self):
        """Captura o token de autorização das requisições de rede após clicar no botão"""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        if not self._can_renew_token_via_browser():
            reason = self._browser_renewal_unavailable_reason or self._browser_renewal_error_message()
            raise RuntimeError(reason)

        if not hasattr(self, 'driver'): # Garante que o driver está configurado
            self.setup_driver()
            self.login()

        try:
            # Primeiro, aguarda o botão aparecer e clica nele
            wait = WebDriverWait(self.driver, 10)

            self.driver.get("https://apps.docusign.com/send/reports/6/S6")
            
            # Aguarda e encontra o botão "Executar relatório"
            run_report_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-qa="run-report"]'))
            )
            print("Botão 'Executar relatório' encontrado.")
            
            # Limpa os logs existentes antes de clicar no botão
            self.driver.get_log('performance')
            
            # Clica no botão
            run_report_button.click()
            print("Botão 'Executar relatório' clicado.")
            
            # Aguarda um tempo para que a requisição seja feita
            time.sleep(5)
            
            # Obtém os logs de performance do navegador
            logs = self.driver.get_log('performance')
            
            for log in logs:
                message = json.loads(log['message'])
                
                # Procura por requisições HTTP
                if message['message']['method'] == 'Network.requestWillBeSent':
                    request = message['message']['params']['request']
                    url = request.get('url', '')
                    
                    # Verifica se a URL contém 'report_results'
                    if 'report_results' in url:
                        headers = request.get('headers', {})
                        
                        # Verifica se há um header Authorization
                        if 'authorization' in headers or 'Authorization' in headers:
                            auth_header = headers.get('authorization') or headers.get('Authorization')
                            if auth_header and auth_header.startswith('Bearer '):
                                print(f"Token encontrado na requisição report_results: {auth_header[7:]}")
                                self.token = auth_header.replace('Bearer ', '')
                                
                                # Tenta salvar o token, mas não falha se não conseguir
                                try:
                                    self.token_manager('save')
                                    logger.info("Token salvo com sucesso.")
                                except Exception as save_error:
                                    logger.warning(f"Falha ao salvar token no .env: {save_error}. Token está carregado em memória.")
                                
                                # Tenta fechar o driver, mas não falha se não conseguir
                                try:
                                    self.driver.quit()
                                    logger.info("Driver fechado com sucesso.")
                                except Exception as quit_error:
                                    logger.warning(f"Falha ao fechar driver: {quit_error}. Continuando...")
                                
                                return self.token
        
            print("Token de autorização não encontrado na requisição report_results")
            logger.warning("Token não foi encontrado nos logs de performance.")
            return None
        
        except Exception as e:
            logger.error(f"Erro detalhado ao capturar token: {type(e).__name__}: {str(e)}")
            logger.exception("Stack trace completo:")
            # Limpar o driver se houver erro
            if hasattr(self, 'driver') and self.driver:
                try:
                    logger.debug("Tentando fechar driver após erro...")
                    self.driver.quit()
                except Exception as quit_error:
                    logger.debug(f"Erro ao fechar driver: {quit_error}")
            return None

    def data_manager(self, operation: Literal['load', 'save']) -> None:
        """
        Gerencia o carregamento e salvamento de dados locais relacionados ao cliente DocuSign.
        Args:
            operation Literal['load', 'save']: A operação a ser realizada: 'load' ou 'save'.
        """
        data_file = os.path.join(self.storage_path, "dados_cliente_docusign.json")
        if operation == 'load':
            load_candidates = [data_file]
            fallback_file = os.path.join(self.data_file_path, "dados_cliente_docusign.json")
            if fallback_file not in load_candidates:
                load_candidates.append(fallback_file)

            for candidate in load_candidates:
                try:
                    with open(candidate, 'r', encoding='utf-8') as f:
                        data = f.read()
                        logger.debug("Dados carregados com sucesso de %s.", candidate)
                        self.groups = json.loads(data)
                        return None
                except FileNotFoundError:
                    continue

            logger.error("Arquivo de dados não encontrado: %s", data_file)
            self.groups = {}
            return None

        elif operation == 'save':

            if not hasattr(self, 'groups') or not self.groups:
                logger.error("Nenhum dado de grupo disponível para salvar.")
                return
            try:
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.groups, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"Erro ao salvar dados: {e}")

        else: # Se a operação for inválida
            raise ValueError("Operação inválida para data_manager")

    def token_manager(self, operation: Literal['save', 'load']) -> str | None:
        """
        Gerencia o token de autenticação para a API do Docusign.
        Lida com a obtenção, salvamento e carregamento do token conforme necessário.
        Carrega e cria o token no cliente como self.token e salva no arquivo .env.
        Args:
            operation Literal['save', 'load']: A operação a ser realizada:  'save', ou 'load'.
        Returns:
            str: O token de autenticação, se aplicável. Operações 'save' retornam None.
        Raises:
            ValueError: Se a operação for inválida ou se tentar salvar sem um token válido.
        """        
        if operation == 'save':
            # Confirma que há um token válido para salvar
            if not self.token or self.token.strip() == "":
                logger.debug("Nenhum token disponível para salvar.")
                return None
            
            # Adiciona o token ao ambiente atual carregado
            os.environ["DOCUSIGN_TOKEN"] = self.token
            try:
                dotenv.set_key(env_path, "DOCUSIGN_TOKEN", self.token)
                logger.debug("Token salvo no .env.")
            except OSError as exc:
                logger.warning(
                    "Token mantido apenas em memória; não foi possível gravar no .env (%s): %s",
                    env_path,
                    exc,
                )
            return None
        
        elif operation == 'load':
            # Carrega o token do .env            
            token = os.getenv("DOCUSIGN_TOKEN")

            # Se o token não existir ou for vazio, retorna None
            if not token or token.strip() == "":
                logger.debug("Nenhum token encontrado no .env.")
                return None
            
            # Se não for vazio, salva e retorna o token
            logger.debug("Token carregado do .env.")
            self.token = token
            return token
        
        else: # Se a operação for inválida
            raise ValueError("Operação inválida para token_manager")

    def validate_token(self) -> bool:
        """Verifica se o token atual é aceito pela API do DocuSign."""
        if not self.token or not self.token.strip():
            return False

        url = (
            f"https://apps.docusign.com/api/esign/na2/restapi/v2.1/accounts/"
            f"{self.account_id}/groups"
        )
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.error("Erro ao validar token do DocuSign: %s", exc)
            return False

        return response.status_code == 200

    def ensure_authenticated(self) -> None:
        """
        Garante um token válido antes de consultas à API.
        Renova via Selenium quando necessário e falha com erro claro se não for possível.
        """
        if self.validate_token():
            logger.info("Token do DocuSign válido.")
            return

        logger.warning("Token do DocuSign inválido ou expirado. Tentando renovar...")

        if not self._can_renew_token_via_browser():
            reason = self._browser_renewal_unavailable_reason or self._browser_renewal_error_message()
            raise RuntimeError(
                "Não foi possível autenticar no DocuSign. "
                f"{reason}"
            )

        self.get_new_token()
        self.token_manager("save")

        if not self.validate_token():
            raise RuntimeError(
                "Renovação do token DocuSign concluída, mas a API ainda retorna não autorizado."
            )

        logger.info("Token do DocuSign renovado com sucesso.")
        
    def run_query(self, url_end: str) -> dict:
        """
        Executa uma consulta na API do Docusign. Lida com retries em caso de falhas temporárias.
        Args:
            url_end (str): A URL da consulta a ser executada.
        """
        url = f"https://apps.docusign.com/api/esign/na2/restapi/v2.1/accounts/{self.account_id}/{url_end}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        max_retries = 3
        retries = 0

        while retries < max_retries:

            if retries > 0: # Loga apneas se for uma tentativa de retry
                logger.debug(f"Tentativa {retries + 1} de {max_retries}...")

            try:
                request = requests.get(url, headers=headers) # Realiza a requisição GET
            except requests.RequestException as e: # Captura erros de requisição
                logger.error(f"Erro na requisição: {e}")
                retries += 1
                continue

            if request.status_code == 401: # Unauthorized
                if retries == 0:
                    logger.error("Token inválido ou expirado.")
                # Busca um novo token e tenta novamente
                if not self._can_renew_token_via_browser():
                    if retries == 0:
                        logger.error(
                            "Não foi possível renovar o token automaticamente: %s",
                            self._browser_renewal_unavailable_reason,
                        )
                    return {}
                try:
                    self.get_new_token()
                except Exception as e:
                    self._browser_renewal_unavailable_reason = str(e)
                    if retries == 0:
                        logger.error(f"Falha ao renovar token: {e}")
                    return {}
                if not self.token or self.token.strip() == "":
                    if retries == 0:
                        logger.error("Token não renovado. Abortando consulta.")
                    return {}
                headers["Authorization"] = f"Bearer {self.token}"
                retries += 1
                continue

            elif request.status_code == 404: # Not Found
                logger.error(f"Recurso não encontrado: {url}")
                return {} # Retorna vazio para recursos não encontrados, sem tentar novamente

            elif request.status_code >= 500: # Erro do servidor
                retries += 1
                logger.warning(f"Erro do servidor (status {request.status_code})")
                continue

            elif request.status_code != 200: # Outros erros
                try:
                    error_data = request.json()
                    logger.error(f"Erro na API. Código status: {request.status_code}. Mensagem: {error_data['message']}. Erro completo: {error_data}")
                except (ValueError, KeyError):
                    logger.error(f"Erro inesperado (status {request.status_code}. Mensagem: {request.text})")
                    retries = max_retries # Não tenta mais
                    continue

                # Trata os erros específicos
                error_code = error_data.get('errorCode', '')

                if error_code == 'INVALID_REQUEST_PARAMETER':
                    logger.error(f"Parâmetro de requisição inválido. {error_data['message']}")    
                    retries = max_retries  # Não tenta mais
                elif error_code == 'USER_NOT_FOUND':
                    logger.error(f"Usuário não encontrado. {error_data['message']}")
                    retries = max_retries  # Não tenta mais
                elif error_code == 'USER_LACKS_PERMISSIONS':
                    logger.error(f"Usuário sem permissões. {error_data['message']}")
                    return {"erro": "sem_permissao"}
                else:
                    retries += 1  # Tenta novamente para outros erros
                    continue

            elif request.status_code == 200: # Sucesso
                try:
                    data = request.json()
                    logger.debug("Consulta bem-sucedida.")
                    return data
                except ValueError:
                    logger.error("Erro ao decodificar a resposta JSON.")
                    retries += 1
                    continue

        logger.error("Consulta falhou.")
        return {}
    
    def get_groups(self) -> dict:
        """
        Obtém a lista de grupos da conta DocuSign.
        Returns:
            dict: Dados dos grupos retornados pela API.
        """
        # Faz a requisição para obter os grupos
        groups_data = self.run_query("groups")
        # Recupera a lsita de grupos
        groups = groups_data.get("groups", [])
        logger.debug(f"Número de grupos obtidos: {len(groups)}")

        # Retorna dicionário de grupos com o ID como chave
        groups_dict = {}

        for group in groups:

            group_id = group.get("groupId")
            group_name = group.get("groupName")

            if group_name.lower() == "everyone":
                # Esse grupo não pode ser usado como filtro, então não é preciso salvar
                logger.debug("Grupo 'Everyone' encontrado e será ignorado.")
                continue

            groups_dict[group_id] = {
                "nome_grupo": group_name,
            }

        self.groups = groups_dict
        return groups_dict
    
    def get_users(self) -> dict:
        """
        Obtém a lista de usuários em um grupo específico.
        Args:
            group_id (str): O ID do grupo.
        Returns:
            dict: Dados dos usuários no grupo retornados pela API.
        """
        # Busca os grupos salvos no cliente
        groups = self.groups.copy()

        # Se não tiver ou for vazio
        if not groups or len(groups) == 0:
            # Busca os grupos primeiro
            logger.debug("Nenhum grupo salvo no cliente, obtendo grupos primeiro.")
            self.get_groups()
            groups = self.groups.copy()
        # Confirma se ainda está vazio 
        if not groups or len(groups) == 0:
            logger.error("Não foi possível obter grupos para buscar usuários.")
            return {} # Se vazio retorna vazio
            
        # Itera pelos grupos salvos e busca os usuários
        for group_id, group_data in groups.copy().items():
            logger.debug(f"Buscando usuários do grupo ID: {group_id}, Nome: {group_data['nome_grupo']}")
            group_users_data = self.run_query(f"users?group_id={group_id}")
            group_users = group_users_data.get("users", [])
            total_users = len(group_users)
            logger.debug(f"Número de usuários obtidos no grupo {group_id}: {total_users}")

            if total_users == 0:
                logger.debug(f"Nenhum usuário encontrado no grupo {group_id}.")
                groups.pop(group_id)  # Remove o grupo vazio
                self.groups.pop(group_id, None)  # Remove do cliente também
                continue

            # Itera pelos usuários e os adiciona ao dicionário de usuários do grupo
            for user in group_users:
                user_id = user.get("userId")
                user_name = user.get("userName")
                user_email = user.get("email")

                groups[group_id].setdefault("usuarios", {})[user_id] = {
                    "nome_usuario": user_name,
                }

        # Atualiza os grupos salvos no cliente
        self.groups.update(groups)
        self.data_manager('save') # Salva os dados atuais após buscar usuários
        return groups
    
    def get_envelopes_with_updates(self, updated_after: str) -> dict:
        """
        Obtém os envelopes que foram atualizados após uma data específica.
        Args:
            updated_after (str): A data no formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ).
        Returns:
            dict: Dados dos envelopes atualizados retornados pela API.
        """
        # Busca os grupos salvos no cliente
        if not hasattr(self, 'groups') or not self.groups or len(self.groups) == 0:
            logger.debug("Nenhum grupo salvo no cliente, obtendo grupos primeiro.")
            self.get_groups()
            self.get_users()  # Também busca os usuários
        groups = getattr(self, 'groups', {})
        if not groups or len(groups) == 0:
            logger.error("Não foi possível obter grupos para buscar usuários.")
            return {} # Se vazio retorna vazio
        
        self.data_manager('save') # Salva os dados atuais antes de buscar envelopes
        
        # Faz as requisições para obter os envelopes atualizados para cada usuário
        envelopes_dict = {}

        for group_id, group_data in groups.copy().items():
            usuarios = group_data.get("usuarios", {})
            for user_id, user_data in usuarios.copy().items():
                logger.debug(f"Buscando envelopes atualizados para o usuário ID: {user_id}, Nome: {user_data['nome_usuario']}")
                envelopes_data = self.run_query(f"envelopes?from_date={updated_after}&user_id={user_id}")

                if "erro" in envelopes_data:
                    error_type = envelopes_data["erro"]
                    if error_type == "sem_permissao":
                        logger.error(f"Sem permissão para acessar envelopes do usuário {user_id}.")
                        user_popped = groups[group_id]["usuarios"].pop(user_id)  # Remove o usuário sem permissão
                        logger.debug(f"Usuário removido do grupo {group_id}: {user_popped}")
                        continue

                envelopes = envelopes_data.get("envelopes", [])
                total_envelopes = len(envelopes)
                logger.debug(f"Número de envelopes atualizados obtidos para o usuário {user_id}: {total_envelopes}")

                if total_envelopes == 0:
                    logger.debug(f"Nenhum envelope atualizado encontrado para o usuário {user_id}.")
                    continue

                # Adiciona os envelopes ao dicionário geral
                for envelope in envelopes:
                    envelope_id = envelope.get("envelopeId")
                    envelopes_dict[envelope_id] = {
                        "status": envelope.get("status"),
                        "assunto": envelope.get("emailSubject"),
                        "criado_em": envelope.get("createdDateTime"),
                        "enviado_em": envelope.get("sentDateTime"),
                    }

                # Conta o número de usuários restantes com permissão no grupo
            total_users_with_permission = len(groups[group_id].get("usuarios", {}))
            if total_users_with_permission == 0:
                logger.debug(f"Nenhum usuário com permissão restante no grupo {group_id}. Removendo grupo.")
                groups.pop(group_id)  # Remove o grupo vazio
                self.groups.pop(group_id, None)  # Remove do cliente também

        self.groups = groups  # Atualiza os grupos no cliente
        self.data_manager('save') # Salva os dados atuais após buscar envelopes
        return envelopes_dict
    
    def get_recipients_data(self, envelope_ids_list: list) -> dict:
        """
        Obtém os dados dos signatários para uma lista de IDs de envelopes.
        Args:
            envelope_ids_list (list): Lista de IDs de envelopes.
        Returns:
            dict: Dados dos signatários retornados pela API.
        """
        envelopes_data = {}

        for envelope_id in envelope_ids_list:
            # Busca os dados dos destinatários
            envelopes_data[envelope_id] = {"destinatarios": []}
            recipients_data = self.run_query(f"envelopes/{envelope_id}/recipients")

            total_clients = 0
            clients_signed = 0
            total_real_estate = 0
            real_estates_signed = 0

            # Itera pelos itens do dicionário retornado e adiciona ao dicionário geral
            for key, value in recipients_data.items():

                # Acessa apenas os signatários e cópias carbono (se existirem)
                if key == "signers" and isinstance(value, list):

                    # Itera pelos destinatários na lista
                    for recipient in value:
                        role = recipient.get("roleName", "desconhecido")
                        status = recipient.get("status", "desconhecido")
                        # Conta o número de clientes e imobiliárias e se já assinaram
                        if role in ["CLIENTE", "CLIENTE 1", "CLIENTE 2", "CLIENTE 3", "CLIENTE 4", "CLIENTE 5", "CLIENTE 6"]:
                            total_clients += 1
                            if status == "completed":
                                clients_signed += 1
                        elif role in ["IMOBILIÁRIA", "IMOBILIÁRIA 1", "IMOBILIÁRIA 2", "IMOBILIÁRIA 3", "IMOBILIARIA", "IMOBILIÁRIA 5", "IMOBILIÁRIA 6"]:
                            total_real_estate += 1
                            if status == "completed":
                                real_estates_signed += 1

                        recipient_info = {
                            "tipo_de_destinatario": key,
                            "papel": role,
                            "status": status,
                            "nome": recipient.get("name"),
                            "email": recipient.get("email"),
                            "entregue_em": recipient.get("deliveredDateTime"),
                            "full_data": recipient
                        }
                        envelopes_data[envelope_id]["destinatarios"].append(recipient_info)

            if total_clients == 0: client_signature_status = "nenhum_cliente"
            elif clients_signed == 0: client_signature_status = "nenhum_assinou"
            elif clients_signed < total_clients: client_signature_status = "parcialmente_assinado"
            else: client_signature_status = "completo"
            envelopes_data[envelope_id]["status_assinatura_cliente"] = client_signature_status

            if total_real_estate == 0: real_estate_signature_status = "nenhuma_imobiliaria"
            elif real_estates_signed == 0: real_estate_signature_status = "nenhuma_assinou"
            elif real_estates_signed < total_real_estate: real_estate_signature_status = "parcialmente_assinado"
            else: real_estate_signature_status = "completo"
            envelopes_data[envelope_id]["status_assinatura_imobiliaria"] = real_estate_signature_status

        return envelopes_data


def main():
    """Carrega credenciais do .env central (DOCUSIGN_* / DOCU_*)."""
    from pathlib import Path

    try:
        from dotenv import load_dotenv
        here = Path(__file__).resolve()
        for p in [here.parents[i] / ".env" for i in range(1, 8)]:
            if p.is_file():
                load_dotenv(p)
                break
    except ImportError:
        pass

    user = os.getenv("DOCU_USER", "")
    password = os.getenv("DOCU_PASSWORD", "")
    account_id = os.getenv("DOCUSIGN_ACCOUNT_ID", "")
    data_path = os.getenv("DOCUSIGN_DATA_PATH", "/opt/airflow/data/docusign")
    if not account_id:
        raise RuntimeError("Defina DOCUSIGN_ACCOUNT_ID no .env da raiz")
    client = DocuClient(
        user=user, password=password, account_id=account_id, data_file_path=data_path
    )
    token = os.getenv("DOCUSIGN_TOKEN", "")
    if token:
        client.token = token
    return client


if __name__ == "__main__":
    client = main()
    # Status dos envelopes são: 
    """
        completed: todas as assinaturas e passos completos
        created: criado, mas não enviado
        declined: algun signatário recusou
        deleted: deletado
        delivered: entregue
        processing: ??? não sei o que é
        sent: enviado, aguardando ações
        signed: ??? assinado mas não completo?
        template: ????
        voided: cancelado
    """

    # # Cria a lista de ids a serem consultados
    # envelope_ids_list = []
    # # Itera pelos envelopes e filtra os que não estão completos ou cancelados
    # for envelope_id, envelope_data in envelopes.items():
    #     envelope_status = envelope_data.get("status", "desconhecido")
    #     # Se o status for completo ou cancelado, não adiciona à lista
    #     if envelope_status.lower() in ["completed", "created", "deleted", "voided"]:
    #         pass
    #     else:
    #         envelope_ids_list.append(envelope_id)

    # Finalmente busca os dados dos signatários para os envelopes filtrados
    envelopes_with_recipients = {}

    test_envelope_id = "4a2bb12a-49d2-4de5-a319-d2dd0d8f698c"

    print(f"Buscando dados dos destinatários para o envelope ID: {test_envelope_id}")
    recipients = client.get_recipients_data([test_envelope_id])

    print(f"Dados dos destinatários para o envelope ID {test_envelope_id}:")
    envelopes_data = client.run_query(f"envelopes/{test_envelope_id}")

    #test_envelope_id = "f73a4acd-4529-4320-8c5a-6e76bc5aaa87"

    #recipients_data = client.run_query(f"envelopes/{test_envelope_id}/recipients")

    #/restapi/v2.1/accounts/{accountId}/envelopes/{envelopeId}/attachments

    #attachments = client.run_query(f"envelopes/{test_envelope_id}/documents")
    #print(attachments)











