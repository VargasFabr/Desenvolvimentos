# Cliente para leitura de e-mails no Outlook Web via Selenium
# %%
from __future__ import annotations

import logging
import os
import pickle
import re
import time
from datetime import datetime, timezone

import dotenv

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
dotenv.load_dotenv(env_path)

logger = logging.getLogger("Cliente Outlook")

DOCUSIGN_CODE_PATTERNS = (
    r"(?:security code|código de segurança|verification code|código de verificação)[:\s]*(\d{6})",
    r"(\d{6})\s*(?:is your|é o seu|é seu)",
    r"\b(\d{6})\b",
)

DOCUSIGN_SENDER_HINTS = ("docusign", "account-d", "noreply@docusign")
DOCUSIGN_SUBJECT_HINTS = ("security code", "código de segurança", "verification", "verificação", "docusign")


class ClienteOutlook:
    _LINUX_CHROME_PATHS = (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/google-chrome",
    )

    OUTLOOK_MAIL_URL = os.getenv("OUTLOOK_MAIL_URL", "https://outlook.office.com/mail/")

    def __init__(self, user: str, password: str, data_file_path: str) -> None:
        self.user = user
        self.password = password
        self.data_file_path = data_file_path
        self.driver = None
        os.makedirs(self.data_file_path, exist_ok=True)

    def _resolve_chrome_bin(self) -> str | None:
        import platform
        import shutil
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
                    ["where", "chrome"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.stdout:
                    return result.stdout.strip().split("\n")[0]
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

    def setup_driver(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        import shutil

        if self.driver is not None:
            return

        chrome_bin = self._resolve_chrome_bin()
        if not chrome_bin:
            raise RuntimeError(
                "Chrome/Chromium não encontrado para o Cliente Outlook. "
                "Instale o Google Chrome ou defina GOOGLE_CHROME_BIN/CHROME_BIN."
            )

        options = webdriver.ChromeOptions()
        headless = os.getenv("OUTLOOK_HEADLESS", "true").lower() in ("1", "true", "yes")
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.binary_location = chrome_bin

        chromedriver_bin = (
            os.getenv("CHROMEDRIVER_PATH")
            or shutil.which("chromedriver")
            or shutil.which("chromium-driver")
        )

        if chromedriver_bin:
            service = Service(chromedriver_bin)
        else:
            try:
                service = Service(ChromeDriverManager().install())
            except Exception as exc:
                logger.warning("Erro ao baixar ChromeDriver: %s. Tentando versão padrão...", exc)
                service = Service()

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(5)
        logger.info("Driver Selenium do Outlook configurado com sucesso.")

    def quit(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def cookies_manager(self, operation: str) -> None:
        if operation not in ("save", "load"):
            raise ValueError("Operação inválida. Use 'save' ou 'load'.")

        if self.driver is None:
            raise ValueError("Driver não está configurado.")

        cookies_dir = os.path.join(self.data_file_path, "Cookies")
        os.makedirs(cookies_dir, exist_ok=True)
        cookies_file = os.path.join(cookies_dir, "outlook.pkl")

        if operation == "save":
            with open(cookies_file, "wb") as handle:
                pickle.dump(self.driver.get_cookies(), handle)
            return

        if not os.path.exists(cookies_file):
            return

        self.driver.get(self.OUTLOOK_MAIL_URL)
        time.sleep(2)
        with open(cookies_file, "rb") as handle:
            cookies = pickle.load(handle)
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                continue

    def _is_logged_in(self) -> bool:
        current_url = self.driver.current_url.lower()
        return (
            "outlook.office.com/mail" in current_url
            or "outlook.live.com/mail" in current_url
        ) and "login.microsoftonline.com" not in current_url

    def _click_first_available(self, selectors: tuple[str, ...]) -> bool:
        from selenium.webdriver.common.by import By

        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    element.click()
                    return True
        return False

    def _fill_first_available(self, selectors: tuple[str, ...], value: str) -> bool:
        from selenium.webdriver.common.by import By

        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    element.clear()
                    element.send_keys(value)
                    return True
        return False

    def _handle_microsoft_login(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        wait = WebDriverWait(self.driver, 20)

        email_selectors = (
            "input[name='loginfmt']",
            "input[type='email']",
            "#i0116",
        )
        password_selectors = (
            "input[name='passwd']",
            "input[type='password']",
            "#i0118",
        )
        submit_selectors = (
            "input[type='submit']",
            "button[type='submit']",
            "#idSIButton9",
        )

        if self._fill_first_available(email_selectors, self.user):
            logger.info("E-mail do Outlook preenchido.")
            self._click_first_available(submit_selectors)
            time.sleep(2)

        if self._fill_first_available(password_selectors, self.password):
            logger.info("Senha do Outlook preenchida.")
            self._click_first_available(submit_selectors)
            time.sleep(3)

        for _ in range(3):
            if self._is_logged_in():
                break

            stay_signed_in = self.driver.find_elements(
                By.CSS_SELECTOR,
                "#idSIButton9, input[value='Yes'], button[data-testid='primaryButton']",
            )
            for button in stay_signed_in:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    time.sleep(2)
                    break

            try:
                wait.until(lambda driver: self._is_logged_in())
                break
            except Exception:
                time.sleep(2)

        if not self._is_logged_in():
            raise RuntimeError(
                "Não foi possível concluir o login no Outlook Web. "
                "Verifique DOCU_USER/EMAIL_PASSWORD ou faça login manualmente uma vez "
                "para salvar cookies."
            )

    def login(self) -> None:
        self.setup_driver()
        self.driver.get(self.OUTLOOK_MAIL_URL)
        time.sleep(3)

        try:
            self.cookies_manager("load")
            self.driver.get(self.OUTLOOK_MAIL_URL)
            time.sleep(4)
        except Exception as exc:
            logger.debug("Cookies do Outlook não carregados: %s", exc)

        if self._is_logged_in():
            logger.info("Sessão do Outlook reutilizada via cookies.")
            return

        logger.info("Realizando login no Outlook Web...")
        self._handle_microsoft_login()
        self.cookies_manager("save")
        logger.info("Login no Outlook concluído.")

    @staticmethod
    def _extract_code_from_text(text: str) -> str | None:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        if not normalized:
            return None

        for pattern in DOCUSIGN_CODE_PATTERNS:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _open_search_results(self, query: str) -> None:
        search_url = f"{self.OUTLOOK_MAIL_URL.rstrip('/')}/search/q/{query.replace(' ', '%20')}"
        self.driver.get(search_url)
        time.sleep(4)

    def _read_visible_messages_text(self) -> list[str]:
        from selenium.webdriver.common.by import By

        texts: list[str] = []

        list_items = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[role='listbox'] [role='option'], div[aria-label*='message'], div[data-convid]",
        )
        for item in list_items[:8]:
            label = (item.text or item.get_attribute("aria-label") or "").strip()
            if not label:
                continue
            if not any(hint in label.lower() for hint in DOCUSIGN_SUBJECT_HINTS + DOCUSIGN_SENDER_HINTS):
                continue

            try:
                item.click()
                time.sleep(2)
            except Exception:
                continue

            body_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='document'], .ReadingPaneContents, #UniqueMessageBody, div[aria-label='Message body']",
            )
            for body in body_elements:
                body_text = body.text.strip()
                if body_text:
                    texts.append(f"{label}\n{body_text}")

            if len(texts) >= 3:
                break

        if not texts:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            if page_text:
                texts.append(page_text)

        return texts

    def get_verification_code(
        self,
        *,
        sender_hints: tuple[str, ...] = DOCUSIGN_SENDER_HINTS,
        subject_hints: tuple[str, ...] = DOCUSIGN_SUBJECT_HINTS,
        max_wait_seconds: int = 90,
        poll_interval_seconds: int = 5,
        requested_after: datetime | None = None,
    ) -> str | None:
        self.login()

        deadline = time.time() + max_wait_seconds
        search_queries = (
            "from:docusign security code",
            "from:docusign código",
            "docusign verification",
        )

        while time.time() < deadline:
            for query in search_queries:
                self._open_search_results(query)
                messages_text = self._read_visible_messages_text()

                for message_text in messages_text:
                    lowered = message_text.lower()
                    if sender_hints and not any(hint in lowered for hint in sender_hints):
                        if not any(hint in lowered for hint in subject_hints):
                            continue

                    code = self._extract_code_from_text(message_text)
                    if code:
                        logger.info("Código de verificação encontrado no Outlook.")
                        return code

            logger.debug(
                "Código ainda não encontrado no Outlook. Aguardando %ss...",
                poll_interval_seconds,
            )
            time.sleep(poll_interval_seconds)

        if requested_after is not None:
            logger.warning(
                "Nenhum código encontrado após %s no Outlook.",
                requested_after.isoformat(),
            )
        else:
            logger.warning("Nenhum código de verificação encontrado no Outlook.")

        return None

    def get_docusign_mfa_code(self, requested_after: datetime | None = None) -> str:
        code = self.get_verification_code(requested_after=requested_after)
        if not code:
            raise RuntimeError(
                "Não foi possível obter o código MFA do DocuSign no Outlook. "
                "Confirme se DOCU_USER/EMAIL_PASSWORD estão corretos e se o e-mail chegou."
            )
        return code


def build_outlook_client_from_env(data_file_path: str, fallback_user: str | None = None) -> ClienteOutlook:
    user = os.getenv("DOCU_USER") or fallback_user
    password = os.getenv("EMAIL_PASSWORD")

    if not user:
        raise ValueError(
            "DOCU_USER não configurado no .env."
        )
    if not password:
        raise ValueError(
            "EMAIL_PASSWORD não configurado no .env."
        )

    return ClienteOutlook(user=user, password=password, data_file_path=data_file_path)


def main() -> None:
    data_path = os.getenv("OUTLOOK_DATA_PATH", os.path.join(os.path.dirname(__file__), "Dados", "Outlook"))
    client = build_outlook_client_from_env(data_path)
    code = client.get_docusign_mfa_code()
    print(f"Código DocuSign encontrado: {code}")
    client.quit()


if __name__ == "__main__":
    main()
