"""Cliente SharePoint para extração da lista Daes (site Dacoes)."""
from __future__ import annotations

import json
import logging
import os
import pickle
import re
import shutil
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger("Cliente SharePoint Dações")

DEFAULT_SHAREPOINT_URL = (
    "https://melnickeven.sharepoint.com/sites/Dacoes/Lists/Daes/AllItems.aspx"
    "?sortField=ID&isAscending=false&viewid=4fa43363%2Daf41%2D4d3f%2Daf14%2D86136a147809"
)

_METADATA_KEYS = {
    "id",
    "id@odata.type",
    "contenttypeid",
    "created",
    "modified",
    "authorid",
    "editorid",
    "owshiddenversion",
    "version",
    "path",
    "fileleafref",
    "filedirref",
    "attachments",
    "guid",
    "workflowversion",
    "workflowinstanceid",
    "itemchildcount",
    "folderchildcount",
    "appauthor",
    "appeditor",
    "uiversionstring",
    "edit",
    "linktitle",
    "linktitle2",
    "linktitle3",
    "linktitle4",
    "linktitle5",
    "linktitle6",
    "linktitle7",
    "linktitle8",
    "linktitle9",
    "linktitle10",
    "selecttitle",
    "instanceid",
    "order",
    "parentfolderid",
    "parentversionstring",
    "parentleafname",
    "docicon",
    "serverurl",
    "encodedabsurl",
    "base64encoded",
    "filesize",
    "metainfo",
    "level",
    "scopeid",
    "uniqueid",
    "fsObjType",
    "progid",
    "sortbehavior",
    "permmask",
    "principalcount",
    "isrecordsenabled",
    "accesspolicy",
    "virusstatus",
    "virusvendorid",
    "virusinfo",
    "rld",
    "bnnonindexed",
    "bnindexed",
    "bnindexedvalue",
    "bnkeywords",
    "bnkeywordsvalue",
    "bncategory",
    "bncategoryvalue",
    "bnlanguage",
    "bnlanguagevalue",
    "bnauthor",
    "bnauthorvalue",
    "bneditor",
    "bneditorvalue",
    "bnmodified",
    "bnmodifiedvalue",
    "bncreated",
    "bncreatedvalue",
    "bnfilename",
    "bnfilenamevalue",
    "bntitle",
    "bntitlevalue",
    "bncomments",
    "bncommentsvalue",
    "bnkeywords2",
    "bnkeywords2value",
    "bnkeywords3",
    "bnkeywords3value",
    "bnkeywords4",
    "bnkeywords4value",
    "bnkeywords5",
    "bnkeywords5value",
    "bnkeywords6",
    "bnkeywords6value",
    "bnkeywords7",
    "bnkeywords7value",
    "bnkeywords8",
    "bnkeywords8value",
    "bnkeywords9",
    "bnkeywords9value",
    "bnkeywords10",
    "bnkeywords10value",
}


_SKIP_ITEM_KEYS = {
    "FileSystemObjectType",
    "ServerRedirectedEmbedUri",
    "ServerRedirectedEmbedUrl",
    "ContentTypeId",
    "ComplianceAssetId",
    "OData__ColorTag",
    "OData__UIVersionString",
    "AuthorId",
    "EditorId",
    "GUID",
    "Attachments",
}


class ClienteSharePointDacoes:
    _LINUX_CHROME_PATHS = (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/google-chrome",
    )

    def __init__(
        self,
        user: str,
        password: str,
        data_file_path: str,
        sharepoint_url: str | None = None,
        list_name: str | None = None,
    ) -> None:
        self.user = user
        self.password = password
        self.data_file_path = data_file_path
        self.sharepoint_url = sharepoint_url or os.getenv(
            "DACOES_SHAREPOINT_URL", DEFAULT_SHAREPOINT_URL
        )
        self.list_name = list_name or os.getenv("DACOES_LIST_NAME", "Dações")
        self.list_relative_path = os.getenv(
            "DACOES_LIST_PATH",
            self._extract_list_relative_path(self.sharepoint_url),
        )
        self.site_url = self._extract_site_url(self.sharepoint_url)
        self.driver = None
        self.session = requests.Session()
        self._outlook_client = None
        self._mfa_requested_at: datetime | None = None
        self._last_security_code: str | None = None
        self.field_mapping: dict[str, str] = {}
        self.editable_fields: dict[str, dict[str, Any]] = {}
        self.list_item_entity_type = os.getenv(
            "DACOES_LIST_ITEM_ENTITY_TYPE", "SP.Data.DaesListItem"
        )
        self._digest_value: str | None = None
        self._digest_expires_at: datetime | None = None
        os.makedirs(self.data_file_path, exist_ok=True)

    @staticmethod
    def _extract_site_url(sharepoint_url: str) -> str:
        parsed = urlparse(sharepoint_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if "sites" in path_parts:
            site_index = path_parts.index("sites")
            site_path = "/".join(path_parts[: site_index + 2])
            return f"{parsed.scheme}://{parsed.netloc}/{site_path}"
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _extract_list_relative_path(sharepoint_url: str) -> str:
        parsed = urlparse(sharepoint_url)
        path = parsed.path.split("/AllItems.aspx", 1)[0]
        if "/Lists/" in path:
            return path
        return "/sites/Dacoes/Lists/Daes"

    def _resolve_chrome_bin(self) -> str | None:
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

        if self.driver is not None:
            return

        chrome_bin = self._resolve_chrome_bin()
        if not chrome_bin:
            raise RuntimeError(
                "Chrome/Chromium não encontrado. Instale o Google Chrome ou defina "
                "GOOGLE_CHROME_BIN/CHROME_BIN."
            )

        options = webdriver.ChromeOptions()
        headless = os.getenv("DACOES_HEADLESS", "true").lower() in ("1", "true", "yes")
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
                logger.warning("Erro ao baixar ChromeDriver: %s. Tentando padrão...", exc)
                service = Service()

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(5)
        logger.info("Driver Selenium configurado para SharePoint.")

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
        cookies_file = os.path.join(cookies_dir, "sharepoint.pkl")

        if operation == "save":
            with open(cookies_file, "wb") as handle:
                pickle.dump(self.driver.get_cookies(), handle)
            return

        if not os.path.exists(cookies_file):
            return

        self.driver.get(self.site_url)
        time.sleep(2)
        with open(cookies_file, "rb") as handle:
            cookies = pickle.load(handle)
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                continue

    def _is_logged_in(self) -> bool:
        if self.driver is None:
            return False
        current_url = self.driver.current_url.lower()
        host = urlparse(self.site_url).netloc.lower()
        return host in current_url and "login.microsoftonline.com" not in current_url

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

    def _get_outlook_client(self):
        if self._outlook_client is None:
            from Módulos.cliente_outlook import build_outlook_client_from_env

            outlook_data_path = os.path.join(self.data_file_path, "Outlook")
            self._outlook_client = build_outlook_client_from_env(
                data_file_path=outlook_data_path,
                fallback_user=self.user,
            )
        return self._outlook_client

    def _get_security_code(self) -> str:
        logger.info("Buscando código MFA no Outlook...")
        outlook_client = self._get_outlook_client()
        return outlook_client.get_docusign_mfa_code(requested_after=self._mfa_requested_at)

    def _handle_microsoft_login(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        wait = WebDriverWait(self.driver, 20)
        email_selectors = ("input[name='loginfmt']", "input[type='email']", "#i0116")
        password_selectors = ("input[name='passwd']", "input[type='password']", "#i0118")
        submit_selectors = ("input[type='submit']", "button[type='submit']", "#idSIButton9")
        security_code_selectors = ("input[name='otc']", "input[name='security_code']", "#idTxtBx_SAOTCC_OTC")

        if self._fill_first_available(email_selectors, self.user):
            logger.info("E-mail Microsoft preenchido.")
            self._click_first_available(submit_selectors)
            time.sleep(2)

        if self._fill_first_available(password_selectors, self.password):
            logger.info("Senha Microsoft preenchida.")
            self._mfa_requested_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            self._click_first_available(submit_selectors)
            time.sleep(3)

        for _ in range(5):
            if self._is_logged_in():
                break

            if self._fill_first_available(security_code_selectors, ""):
                try:
                    security_code = self._get_security_code()
                    if self._last_security_code == security_code:
                        raise RuntimeError(
                            "Código MFA repetido. Aguarde um novo e-mail de verificação."
                        )
                    self._fill_first_available(security_code_selectors, security_code)
                    self._last_security_code = security_code
                    self._click_first_available(submit_selectors)
                    time.sleep(3)
                except RuntimeError:
                    logger.warning("MFA não resolvido nesta tentativa.")

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
                "Não foi possível concluir o login no SharePoint. "
                "Verifique DACOES/DACOES_PASS e MFA."
            )

    def login(self) -> None:
        self.setup_driver()
        self.driver.get(self.sharepoint_url)
        time.sleep(3)

        try:
            self.cookies_manager("load")
            self.driver.get(self.sharepoint_url)
            time.sleep(4)
        except Exception as exc:
            logger.debug("Cookies SharePoint não carregados: %s", exc)

        if self._is_logged_in():
            logger.info("Sessão SharePoint reutilizada via cookies.")
            self.cookies_manager("save")
            return

        logger.info("Realizando login no SharePoint...")
        self._handle_microsoft_login()
        self.driver.get(self.sharepoint_url)
        time.sleep(4)
        if not self._is_logged_in():
            raise RuntimeError("Login concluído, mas a lista SharePoint não ficou acessível.")
        self.cookies_manager("save")
        logger.info("Login no SharePoint concluído.")

    def export_session_cookies(self) -> requests.Session:
        if self.driver is None:
            raise RuntimeError("Driver não configurado. Execute login() antes.")

        session = requests.Session()
        for cookie in self.driver.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
        self.session = session
        return session

    def _rest_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json;odata=nometadata",
            "Content-Type": "application/json;odata=verbose;charset=utf-8",
        }

    def _rest_write_headers(self, digest: str) -> dict[str, str]:
        return {
            "Accept": "application/json;odata=nometadata",
            "Content-Type": "application/json;odata=verbose;charset=utf-8",
            "X-RequestDigest": digest,
            "IF-MATCH": "*",
            "X-HTTP-Method": "MERGE",
        }

    def load_session_from_saved_cookies(self) -> bool:
        cookies_file = os.path.join(self.data_file_path, "Cookies", "sharepoint.pkl")
        if not os.path.exists(cookies_file):
            return False
        self.session = requests.Session()
        with open(cookies_file, "rb") as handle:
            cookies = pickle.load(handle)
        for cookie in cookies:
            try:
                self.session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                )
            except Exception:
                continue
        return True

    def ensure_authenticated(self) -> None:
        if self.load_session_from_saved_cookies():
            try:
                self.get_request_digest()
                return
            except Exception as exc:
                logger.info("Sessão salva inválida (%s). Renovando login...", exc)
        self.login()
        self.export_session_cookies()

    def get_request_digest(self) -> str:
        if (
            self._digest_value
            and self._digest_expires_at
            and datetime.now(timezone.utc) < self._digest_expires_at
        ):
            return self._digest_value

        if not self.session.cookies:
            if not self.load_session_from_saved_cookies():
                raise RuntimeError("Sessão SharePoint não autenticada.")

        url = f"{self.site_url}/_api/contextinfo"
        response = self.session.post(
            url,
            headers={
                "Accept": "application/json;odata=nometadata",
                "Content-Type": "application/json;odata=verbose;charset=utf-8",
            },
            timeout=60,
        )
        if response.status_code in (401, 403):
            self.login()
            self.export_session_cookies()
            response = self.session.post(url, headers=self._rest_headers(), timeout=60)
        response.raise_for_status()
        payload = response.json()
        digest_info = payload.get("FormDigestValue")
        timeout_seconds = payload.get("FormDigestTimeoutSeconds", 1800)
        if not digest_info and "d" in payload:
            digest_info = payload["d"].get("GetContextWebInformation", {}).get("FormDigestValue")
            timeout_seconds = payload["d"].get("GetContextWebInformation", {}).get(
                "FormDigestTimeoutSeconds", 1800
            )
        if not digest_info:
            raise RuntimeError("Não foi possível obter FormDigestValue do SharePoint.")
        self._digest_value = digest_info
        self._digest_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(int(timeout_seconds) - 60, 120)
        )
        return digest_info

    def _editable_fields_endpoint(self) -> str:
        list_path = self.list_relative_path.replace("'", "''")
        return (
            f"{self.site_url}/_api/web/GetListUsingPath(DecodedUrl=@a1)/fields"
            f"?@a1='{list_path}'&$filter=Hidden eq false and ReadOnlyField eq false"
            f"&$select=Title,InternalName,StaticName,TypeAsString,Required,ReadOnlyField"
        )

    def _item_endpoint(self, sharepoint_id: int) -> str:
        list_path = self.list_relative_path.replace("'", "''")
        return (
            f"{self.site_url}/_api/web/GetListUsingPath(DecodedUrl=@a1)/items({int(sharepoint_id)})"
            f"?@a1='{list_path}'"
        )

    def _request_write_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        digest = self.get_request_digest()
        response = self.session.post(
            url,
            headers=self._rest_write_headers(digest),
            json=payload,
            timeout=120,
        )
        if response.status_code in (401, 403):
            logger.warning("Sessão REST expirada na escrita (%s). Renovando login...", response.status_code)
            self.login()
            self.export_session_cookies()
            digest = self.get_request_digest()
            response = self.session.post(
                url,
                headers=self._rest_write_headers(digest),
                json=payload,
                timeout=120,
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Falha na escrita SharePoint ({response.status_code}): {response.text[:1000]}"
            )
        if not response.text.strip():
            return {}
        return response.json()

    def fetch_editable_fields(self) -> dict[str, dict[str, Any]]:
        payload = self._request_json(self._editable_fields_endpoint())
        fields = payload.get("value", [])
        editable: dict[str, dict[str, Any]] = {}
        skip_titles = {
            "ID", "Criado", "Modificado", "Criado por", "Modificado por", "Anexos", "Editar",
            "Tipo", "Título", "Contagem de Itens Filhos",
            "Contagem de Elementos Filho da Pasta",
        }

        for field in fields:
            internal_name = (field.get("InternalName") or "").strip()
            title = (field.get("Title") or "").strip()
            if not internal_name or not title:
                continue
            if title in skip_titles or internal_name in _SKIP_ITEM_KEYS:
                continue
            if internal_name.startswith("LinkTitle"):
                continue
            info = {
                "internal_name": internal_name,
                "title": title,
                "normalized_name": self._sanitize_key(title),
                "type": field.get("TypeAsString") or "Text",
                "required": bool(field.get("Required")),
            }
            editable[internal_name] = info

        self.editable_fields = editable
        logger.info("Campos editáveis carregados: %s.", len(editable))
        return editable

    def build_reverse_field_index(self) -> dict[str, str]:
        if not self.field_mapping:
            self.fetch_field_mapping()
        if not self.editable_fields:
            self.fetch_editable_fields()

        reverse: dict[str, str] = {}
        for internal_name, info in self.editable_fields.items():
            reverse[internal_name] = internal_name
            reverse[internal_name.lower()] = internal_name
            title = info.get("title", "")
            normalized = info.get("normalized_name", "")
            if title:
                reverse[title] = internal_name
                reverse[title.lower()] = internal_name
            if normalized:
                reverse[normalized] = internal_name

        for internal_name, title in self.field_mapping.items():
            if internal_name in self.editable_fields:
                reverse[internal_name] = internal_name
                reverse[self._sanitize_key(title)] = internal_name
                reverse[title] = internal_name
                reverse[title.lower()] = internal_name
        return reverse

    def resolve_fields_to_internal(self, fields: dict[str, Any]) -> dict[str, Any]:
        reverse = self.build_reverse_field_index()
        resolved: dict[str, Any] = {}
        unknown: list[str] = []

        for key, value in fields.items():
            internal = reverse.get(key) or reverse.get(str(key).lower())
            if not internal:
                sanitized = self._sanitize_key(str(key))
                internal = reverse.get(sanitized)
            if not internal:
                unknown.append(str(key))
                continue
            if internal not in self.editable_fields:
                raise ValueError(f"Campo não editável: {key}")
            resolved[internal] = self._coerce_sharepoint_value(internal, value)

        if unknown:
            raise ValueError(
                f"Campos desconhecidos: {', '.join(unknown)}. "
                "Use listar_campos_editaveis_dacoes para ver nomes válidos."
            )
        return resolved

    def _coerce_sharepoint_value(self, internal_name: str, value: Any) -> Any:
        if value is None or value == "":
            return None
        field_type = (self.editable_fields.get(internal_name) or {}).get("type", "Text")
        if field_type in {"Number", "Currency"}:
            if isinstance(value, (int, float)):
                return float(value)
            text = str(value).strip().replace(".", "").replace(",", ".")
            return float(text) if text else None
        if field_type == "Boolean":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "sim", "yes"}
        return str(value)

    def get_item_raw(self, sharepoint_id: int) -> dict[str, Any]:
        payload = self._request_json(self._item_endpoint(sharepoint_id))
        if "value" in payload and isinstance(payload["value"], list):
            if not payload["value"]:
                raise ValueError(f"Item SharePoint {sharepoint_id} não encontrado.")
            return payload["value"][0]
        if "d" in payload:
            return payload["d"]
        return payload

    def get_item(self, sharepoint_id: int) -> dict[str, Any]:
        if not self.field_mapping:
            self.fetch_field_mapping()
        raw = self.get_item_raw(sharepoint_id)
        normalized = self.normalize_items([raw], self.field_mapping)
        if not normalized:
            raise ValueError(f"Item SharePoint {sharepoint_id} não encontrado.")
        return normalized[0]

    def update_item(self, sharepoint_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        if not self.editable_fields:
            self.fetch_editable_fields()
        internal_fields = self.resolve_fields_to_internal(fields)
        if not internal_fields:
            raise ValueError("Nenhum campo válido informado para atualização.")

        payload = {
            "__metadata": {"type": self.list_item_entity_type},
            **internal_fields,
        }
        self._request_write_json(self._item_endpoint(sharepoint_id), payload)
        return self.get_item(sharepoint_id)

    def _fields_endpoint(self) -> str:
        list_path = self.list_relative_path.replace("'", "''")
        return (
            f"{self.site_url}/_api/web/GetListUsingPath(DecodedUrl=@a1)/fields"
            f"?@a1='{list_path}'&$filter=Hidden eq false&$select=Title,InternalName,StaticName"
        )

    def _request_json(self, url: str) -> dict[str, Any]:
        if not self.session.cookies:
            self.export_session_cookies()

        response = self.session.get(url, headers=self._rest_headers(), timeout=120)
        if response.status_code in (401, 403):
            logger.warning("Sessão REST expirada (%s). Renovando login...", response.status_code)
            self.login()
            self.export_session_cookies()
            response = self.session.get(url, headers=self._rest_headers(), timeout=120)
        response.raise_for_status()
        return response.json()

    def fetch_field_mapping(self) -> dict[str, str]:
        """Retorna mapeamento internal_name/static_name -> título exibido na lista."""
        payload = self._request_json(self._fields_endpoint())
        fields = payload.get("value", [])
        mapping: dict[str, str] = {}

        for field in fields:
            title = (field.get("Title") or "").strip()
            if not title:
                continue
            internal_name = (field.get("InternalName") or "").strip()
            static_name = (field.get("StaticName") or "").strip()
            if internal_name:
                mapping[internal_name] = title
            if static_name:
                mapping[static_name] = title

        self.field_mapping = mapping
        logger.info("Mapeamento de colunas carregado: %s campos.", len(mapping))
        return mapping

    def save_field_mapping(self, mapping: dict[str, str] | None = None) -> str:
        mapping = mapping or self.field_mapping
        path = os.path.join(self.data_file_path, "dacoes_mapeamento_colunas.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(mapping, handle, ensure_ascii=False, indent=2, sort_keys=True)
        return path

    def _items_endpoint(self) -> str:
        list_path = self.list_relative_path.replace("'", "''")
        return (
            f"{self.site_url}/_api/web/GetListUsingPath(DecodedUrl=@a1)/items"
            f"?@a1='{list_path}'&$top=5000"
        )

    def fetch_list_items(self) -> list[dict[str, Any]]:
        if not self.session.cookies:
            self.export_session_cookies()

        items: list[dict[str, Any]] = []
        next_url = self._items_endpoint()
        page = 0

        while next_url:
            page += 1
            logger.info("Buscando página %s da lista %s...", page, self.list_name)
            response = self.session.get(next_url, headers=self._rest_headers(), timeout=120)

            if response.status_code in (401, 403):
                logger.warning("Sessão REST expirada (%s). Renovando login...", response.status_code)
                self.login()
                self.export_session_cookies()
                response = self.session.get(next_url, headers=self._rest_headers(), timeout=120)

            response.raise_for_status()
            payload = response.json()

            if "value" in payload:
                batch = payload.get("value", [])
                next_url = payload.get("@odata.nextLink")
            elif "d" in payload:
                data = payload["d"]
                batch = data.get("results", data.get("Items", []))
                next_url = data.get("__next")
            else:
                batch = payload if isinstance(payload, list) else []
                next_url = None

            items.extend(batch)
            logger.info("Página %s: %s itens (total acumulado: %s).", page, len(batch), len(items))

        return items

    @staticmethod
    def _sanitize_key(key: str) -> str:
        normalized = unicodedata.normalize("NFKD", key.strip())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^0-9a-zA-Z_]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_").lower()
        return normalized or "campo"

    @classmethod
    def _resolve_column_name(cls, internal_key: str, field_mapping: dict[str, str]) -> str:
        display_name = field_mapping.get(internal_key)
        if not display_name:
            display_name = field_mapping.get(internal_key.lower())
        if not display_name:
            display_name = field_mapping.get(internal_key.upper())
        if display_name:
            return cls._sanitize_key(display_name)
        return cls._sanitize_key(internal_key)

    @classmethod
    def normalize_items(
        cls,
        raw_items: list[dict[str, Any]],
        field_mapping: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        field_mapping = field_mapping or {}
        normalized_items: list[dict[str, Any]] = []

        for raw in raw_items:
            record: dict[str, Any] = {
                "sharepoint_id": raw.get("Id") or raw.get("ID"),
                "created_at": raw.get("Created"),
                "modified_at": raw.get("Modified"),
            }

            for key, value in raw.items():
                if key.startswith("@") or key in {"__metadata", "Author", "Editor"}:
                    continue
                if key in {"Id", "ID", "Created", "Modified"}:
                    continue
                if key in _SKIP_ITEM_KEYS:
                    continue
                if isinstance(value, (dict, list)):
                    continue
                if cls._sanitize_key(key) in _METADATA_KEYS:
                    continue
                column_name = cls._resolve_column_name(key, field_mapping)
                record[column_name] = value

            normalized_items.append(record)

        return normalized_items

    def save_cache(
        self,
        raw_items: list[dict[str, Any]],
        treated_items: list[dict[str, Any]],
    ) -> tuple[str, str]:
        os.makedirs(self.data_file_path, exist_ok=True)
        raw_path = os.path.join(self.data_file_path, "dacoes_raw.json")
        treated_path = os.path.join(self.data_file_path, "dacoes_tratado.json")

        with open(raw_path, "w", encoding="utf-8") as handle:
            json.dump(raw_items, handle, ensure_ascii=False, indent=2)

        with open(treated_path, "w", encoding="utf-8") as handle:
            json.dump(treated_items, handle, ensure_ascii=False, indent=2)

        return raw_path, treated_path

    def scrape(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            self.login()
            self.export_session_cookies()
            field_mapping = self.fetch_field_mapping()
            self.save_field_mapping(field_mapping)
            raw_items = self.fetch_list_items()
            treated_items = self.normalize_items(raw_items, field_mapping)
            self.save_cache(raw_items, treated_items)
            return raw_items, treated_items
        finally:
            self.quit()


def build_sharepoint_client_from_env(data_file_path: str) -> ClienteSharePointDacoes:
    user = os.getenv("DACOES")
    password = os.getenv("DACOES_PASS")
    if not user:
        raise ValueError("DACOES não configurado no .env.")
    if not password:
        raise ValueError("DACOES_PASS não configurado no .env.")
    return ClienteSharePointDacoes(
        user=user,
        password=password,
        data_file_path=data_file_path,
    )
