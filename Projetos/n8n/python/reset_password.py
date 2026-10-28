# %%
import json
import os
import secrets
import string
import time
import traceback
import importlib.util

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def gerar_senha(tamanho: int = 6) -> str:
    # Evita caracteres que podem causar problemas em UI/cópia (aspas, crases, barras, espaços).
    # Mantém boa entropia com letras + dígitos + símbolos "seguros".
    safe_punct = "!@#$%*_-+=?"
    caracteres = string.ascii_letters + string.digits + safe_punct
    tamanho = max(8, min(int(tamanho), 64))
    return "".join(secrets.choice(caracteres) for _ in range(tamanho))


def _load_env_from_dotenv() -> bool:
    """
    Carrega variáveis de um arquivo .env (se existir) para o processo.
    Não depende de python-dotenv.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    env_in_n8n_dir = os.path.abspath(os.path.join(here, "..", ".env"))          # N8N/.env
    env_in_workspace_root = os.path.abspath(os.path.join(here, "..", "..", ".env"))  # .env na raiz

    candidates = [
        env_in_n8n_dir,
        env_in_workspace_root,
        ".env",
        "N8N/.env",
        "/app/.env",
        "/workspace/.env",
        "/workspace/N8N/.env",
        "/home/node/.env",
        "/opt/.env",
    ]

    loaded = False
    for p in candidates:
        try:
            if not os.path.isfile(p):
                continue
        except Exception:
            continue

        try:
            with open(p, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            loaded = True
        except Exception:
            # se um .env falhar, tenta outro candidato
            pass
    return loaded


def _serializable(obj):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serializable(x) for x in obj]
    return str(obj)


def _locate_and_load_helpers_module():
    """
    Reusa helpers do script original `otto_admin_selenium_reset_password.py`
    (ex: _xpath_literal, _click_by_xpath, _type_by_xpath, _collect_visible_messages).
    """
    helper_candidates = [
        "n8n/otto_admin_selenium_reset_password.py",
        "./n8n/otto_admin_selenium_reset_password.py",
        "otto_admin_selenium_reset_password.py",
        "./otto_admin_selenium_reset_password.py",
        "/app/n8n/otto_admin_selenium_reset_password.py",
        "/workspace/n8n/otto_admin_selenium_reset_password.py",
        "/home/node/n8n/otto_admin_selenium_reset_password.py",
    ]

    helper_path = None
    for p in helper_candidates:
        if os.path.isfile(p):
            helper_path = p
            break

    if not helper_path:
        raise FileNotFoundError(
            "Nao encontrei `otto_admin_selenium_reset_password.py` para reutilizar helpers. "
            "Verifique o mount/working directory do container."
        )

    spec = importlib.util.spec_from_file_location("otto_admin_helpers", helper_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _xpath_literal(s: str) -> str:
    # Pequeno fallback caso helpers falhem; mantém compatibilidade.
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    return "concat(" + ",\"'\", ".join([f"'{p}'" for p in parts]) + ")"


def main(admin_email: str | None = None, admin_password: str | None = None, target_email: str | None = None) -> dict:
    new_password = gerar_senha()
    result = {
        "ok": False,
        "email": None,
        "steps": {},
        "error": None,
        "ui_messages": [],
        "message": None,
        "new_password": None,
    }

    driver = None
    try:
        _load_env_from_dotenv()

        admin_email = (admin_email or os.environ.get("OTTO_ADMIN_EMAIL") or "").strip()
        admin_password = (admin_password or os.environ.get("OTTO_ADMIN_PASSWORD") or "").strip()
        target_email = (target_email or os.environ.get("OTTO_TARGET_EMAIL") or os.environ.get("email") or "").strip()
        # target_email = "evelisepaiva@outlook.com"
        if not admin_email:
            raise ValueError("Variavel `OTTO_ADMIN_EMAIL` ausente (via env).")
        if not admin_password:
            raise ValueError("Variavel `OTTO_ADMIN_PASSWORD` ausente (via env).")
        if not target_email:
            raise ValueError("Variavel `OTTO_TARGET_EMAIL` ausente (passada do HTTP n8n).")

        result["email"] = target_email

        # Tenta reutilizar helpers externos; se nao existirem, usa fallback minimo local.
        helpers = None
        try:
            helpers = _locate_and_load_helpers_module()
        except Exception:
            helpers = None

        xpath_literal_fn = getattr(helpers, "_xpath_literal", _xpath_literal) if helpers else _xpath_literal
        click_fn = getattr(helpers, "_click_by_xpath", None) if helpers else None
        type_fn = getattr(helpers, "_type_by_xpath", None) if helpers else None
        collect_msgs_fn = getattr(helpers, "_collect_visible_messages", None) if helpers else None

        if not click_fn:
            def click_fn(d, w, xpath: str, step_name: str, out: dict) -> None:
                el = w.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                el.click()
                out["steps"][step_name] = True

        if not type_fn:
            def type_fn(d, w, xpath: str, value: str, step_name: str, out: dict) -> None:
                el = w.until(EC.presence_of_element_located((By.XPATH, xpath)))
                el.clear()
                el.send_keys(value)
                out["steps"][step_name] = True

        if not collect_msgs_fn:
            def collect_msgs_fn(d) -> list[str]:
                # Captura mensagens comuns em UIs (ex.: alerts/snackbars).
                candidates = d.find_elements(
                    By.XPATH,
                    "//*[(@role='alert' or contains(@class,'MuiAlert-message') or contains(@class,'Toastify__toast-body'))]",
                )
                msgs = []
                for c in candidates:
                    txt = (c.text or "").strip()
                    if txt:
                        msgs.append(txt)
                # fallback: tenta ler tambem elementos tipicos do MUI
                if not msgs:
                    candidates = d.find_elements(By.XPATH, "//p[contains(@class,'MuiTypography-root')]")
                    for c in candidates[:5]:
                        txt = (c.text or "").strip()
                        if txt:
                            msgs.append(txt)
                return msgs

        chrome_options = Options()
        # Tenta usar binários do ambiente quando informados (útil em containers),
        # senão deixa o Selenium Manager resolver automaticamente (Windows/macOS/Linux).
        chrome_binary = (os.environ.get("CHROME_BINARY") or "").strip()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        elif os.path.isfile("/usr/bin/chromium"):
            chrome_options.binary_location = "/usr/bin/chromium"

        # Docker/CI nao tem display: sem --headless o Chromium encerra na hora
        # (SessionNotCreatedException: Chrome instance exited).
        # Para depurar com janela local: CHROME_HEADLESS=0
        _hl = (os.environ.get("CHROME_HEADLESS") or "1").strip().lower()
        if _hl not in ("0", "false", "no"):
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        )

        chromedriver_path = (os.environ.get("CHROMEDRIVER_PATH") or "").strip()
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        elif os.path.isfile("/usr/bin/chromedriver"):
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Selenium Manager (Selenium 4.6+) baixa/resolve o driver automaticamente
            driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(90)
        wait = WebDriverWait(driver, 25)

        # 1) Login
        driver.get("https://admin.beotto.com/")
        time.sleep(1.0)

        type_fn(driver, wait, "//*[@id='email']", admin_email, "login_email_typed", result)
        time.sleep(0.5)

        pass_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='password']")))
        pass_el.click()
        time.sleep(0.3)
        pass_el.clear()
        pass_el.send_keys(admin_password)
        result["steps"]["login_password_typed"] = True
        time.sleep(0.6)

        entrar_xpath = (
            "//button[.//span[normalize-space()='Entrar']]"
            " | //button[contains(.,'Entrar')]"
            " | //span[normalize-space()='Entrar']/ancestor::button[1]"
        )
        click_fn(driver, wait, entrar_xpath, "login_clicked_entrar", result)

        # Verifica se login realmente aconteceu; se falhou, tenta submit via ENTER.
        try:
            wait_short = WebDriverWait(driver, 8)
            wait_short.until(lambda d: len(d.find_elements(By.XPATH, "//*[@id='email']")) == 0)
        except TimeoutException:
            pw_el = driver.find_element(By.XPATH, "//*[@id='password']")
            pw_el.send_keys(Keys.ENTER)
            time.sleep(1.0)
            if driver.find_elements(By.XPATH, "//*[@id='email']"):
                raise TimeoutException("Falha ao fazer login: tela de login continua visível.")

        # 2) Navegar para gerenciamento
        driver.get("https://admin.beotto.com/configuracoes/gerenciamento-de-usuarios")
        wait.until(lambda d: "/configuracoes/gerenciamento-de-usuarios" in d.current_url)
        result["steps"]["navigated_to_users_page"] = True

        time.sleep(5)  # espera a página renderizar antes de digitar no campo

        # 3) Buscar e-mail
        search_xpath = (
            "//input[contains(@placeholder,'Procure') or contains(@placeholder,'procure') "
            "or contains(@aria-label,'Procure') or contains(@name,'search') or contains(@id,'search')]"
        )
        type_fn(driver, wait, search_xpath, target_email, "search_typed", result)

        # 4) Clicar na linha do usuário (tr dentro do tbody)
        email_lit = xpath_literal_fn(target_email)
        user_row_xpath = (
            "//tbody[contains(@class,'MuiTableBody-root')]//tr[contains(@class,'MuiTableRow-root')]["
            f".//td[contains(normalize-space(.), {email_lit})] "
            f"or .//span[contains(normalize-space(.), {email_lit})] "
            f"or .//*[contains(normalize-space(.), {email_lit})]]"
        )

        wait.until(EC.presence_of_element_located((By.XPATH, user_row_xpath)))
        user_rows = driver.find_elements(By.XPATH, user_row_xpath)
        if not user_rows:
            raise TimeoutException("Nao encontrei a linha da tabela contendo o email alvo.")

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", user_rows[0])
        user_rows[0].click()
        result["steps"]["user_row_clicked"] = True

        # Aguarda modal e valida se o e-mail no formulário é o alvo do n8n
        time.sleep(1.0)
        email_input_xpath = "//div[@role='dialog']//input[@name='email'] | //input[@name='email']"
        email_in_modal_el = wait.until(EC.presence_of_element_located((By.XPATH, email_input_xpath)))
        email_in_modal = (email_in_modal_el.get_attribute("value") or "").strip()
        if email_in_modal.lower() != target_email.lower():
            raise ValueError(
                f"Email do modal nao confere com o alvo. Modal: {email_in_modal!r}, Alvo: {target_email!r}"
            )
        result["steps"]["email_modal_checked"] = True

        # 5) Clicar em 'nova'
        nova_xpath = (
            "(//div[@role='dialog']//*[self::button or self::span or self::div]"
            "[contains(translate(normalize-space(.),'NOVA','nova'),'nova')])[1]"
            " | (//*[self::button or self::span or self::div]"
            "[contains(translate(normalize-space(.),'NOVA','nova'),'nova')])[1]"
        )
        click_fn(driver, wait, nova_xpath, "nova_clicked", result)

        # 6) Preencher senha
        new_password_xpath = "//input[@name='newPassword' and not(@disabled)] | //input[@name='newPassword']"
        new_pass_el = wait.until(EC.presence_of_element_located((By.XPATH, new_password_xpath)))
        new_pass_el.clear()
        new_pass_el.send_keys(new_password)
        result["steps"]["new_password_filled"] = True

        # 7) Clicar em Salvar
        salvar_xpath = (
            "//button[.//span[contains(normalize-space(.),'Salvar')]]"
            " | //button[contains(.,'Salvar')]"
        )
        click_fn(driver, wait, salvar_xpath, "salvar_clicked", result)

        # 8) Captura mensagens da UI e decide ok
        time.sleep(2.5)
        ui_messages = collect_msgs_fn(driver)
        result["ui_messages"] = ui_messages

        joined = " | ".join(ui_messages).lower()
        if "não foi possível" in joined or "nao foi possivel" in joined or "não foi possivel" in joined:
            result["ok"] = False
            result["error"] = ui_messages[-1] if ui_messages else "Falha reportada pela UI ao atualizar usuário."
            result["message"] = f"Não foi possível redefinir a senha para {target_email}. Motivo: {result['error']}"
        else:
            result["ok"] = True
            result["new_password"] = new_password
            result["message"] = f"Senha redefinida com sucesso para {target_email}. Nova senha: {new_password}"

    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()
        result["message"] = f"Falha ao redefinir a senha para {result.get('email') or target_email or 'o usuário'}. Erro: {result['error']}"
        try:
            if driver is not None:
                screenshot_path = "/tmp/otto_admin_error.png"
                driver.save_screenshot(screenshot_path)
                result["screenshot"] = screenshot_path
        except Exception:
            pass
        try:
            if driver is not None:
                result["ui_messages"] = _serializable(collect_msgs_fn(driver)) if collect_msgs_fn else []
        except Exception:
            pass

    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass

    return _serializable(result)


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))

