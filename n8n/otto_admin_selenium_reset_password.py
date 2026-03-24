# %%
"""
Teste local: preencha as variáveis abaixo e rode o script (ex: python otto_admin_selenium_reset_password.py).
No n8n, deixe em branco para usar variáveis de ambiente OTTO_ADMIN_EMAIL, OTTO_ADMIN_PASSWORD, OTTO_TARGET_EMAIL.
"""
import json
import os
import sys
import time
import traceback

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- Preencha aqui para testar localmente (deixe vazio para usar env no n8n) ---
ADMIN_EMAIL = "fabriciovargas@melnick.com.br"  # ex: seu_usuario@empresa.com
ADMIN_PASSWORD = "@@Melnick026784"  # ex: sua_senha_do_admin
TARGET_EMAIL = "evelisepaiva@outlook.com"  # ex: usuario_que_tera_senha_alterada@dominio.com
HEADLESS = False  # True = sem janela (container); False = abre o Chrome para ver
# ---------------------------------------------------------------------------------


def _env_or_fail(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise ValueError(f"Variavel de ambiente ausente: {name}")
    return str(v)


def _xpath_literal(s: str) -> str:
    """
    Gera um literal de string para usar em XPath com segurança quando a string
    contém aspas simples ou duplas.
    """
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    # concat('foo',"'",'bar')
    return "concat(" + ",\"'\", ".join([f"'{p}'" for p in parts]) + ")"


def _click_by_xpath(driver, wait: WebDriverWait, xpath: str, step_name: str, result: dict) -> None:
    el = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    el.click()
    result["steps"][step_name] = True


def _type_by_xpath(driver, wait: WebDriverWait, xpath: str, text: str, step_name: str, result: dict) -> None:
    el = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    el.clear()
    el.send_keys(text)
    result["steps"][step_name] = True


def _collect_visible_messages(driver) -> list[str]:
    """
    Tenta capturar mensagens exibidas (toasts/alerts) na UI após ações.
    Isso serve para retornar tanto erros quanto sucessos no JSON.
    """
    candidates_xpath = [
        # MUI/ARIA alert (comum em Snackbar/Alert)
        "//*[@role='alert']",
        "//div[contains(@class,'MuiAlert-root') or contains(@class,'MuiSnackbar-root') or contains(@class,'Snackbar') or contains(@class,'Toast') or contains(@class,'alert') or contains(@class,'Notice')]",
        # fallback: textos que parecem notificações do sistema
        "//*[self::div or self::span or self::p][contains(translate(normalize-space(.),'NÃO','nao'),'nao') and contains(translate(normalize-space(.),'ATUALIZAR','atualizar'),'atualizar')]",
        "//*[self::div or self::span or self::p][contains(translate(normalize-space(.),'SUCESSO','sucesso'),'sucesso')]",
        "//*[self::div or self::span or self::p][contains(translate(normalize-space(.),'IMPORTANTE','importante'),'importante')]",
    ]

    out: list[str] = []
    for xp in candidates_xpath:
        els = driver.find_elements(By.XPATH, xp)
        for el in els:
            try:
                if not el.is_displayed():
                    continue
                txt = (el.text or "").strip()
                if not txt:
                    continue

                # evita capturar mensagens repetidas muito longas/estranhas
                if len(txt) > 300:
                    continue

                if txt not in out:
                    out.append(txt)
            except Exception:
                continue

    return out


def main() -> None:
    result = {
        "ok": False,
        "email": None,
        "steps": {},
        "error": None,
    }

    driver = None
    screenshot_path = None

    try:
        admin_email = (ADMIN_EMAIL or os.environ.get("OTTO_ADMIN_EMAIL") or "").strip()
        admin_password = (ADMIN_PASSWORD or os.environ.get("OTTO_ADMIN_PASSWORD") or "").strip()
        target_email = (
            (TARGET_EMAIL or os.environ.get("OTTO_TARGET_EMAIL") or os.environ.get("email") or "").strip()
        )
        if not admin_email:
            raise ValueError("Preencha ADMIN_EMAIL no código ou defina OTTO_ADMIN_EMAIL no ambiente.")
        if not admin_password:
            raise ValueError("Preencha ADMIN_PASSWORD no código ou defina OTTO_ADMIN_PASSWORD no ambiente.")
        if not target_email:
            raise ValueError("Preencha TARGET_EMAIL no código ou defina OTTO_TARGET_EMAIL no ambiente.")

        result["email"] = target_email

        chrome_options = Options()
        if HEADLESS:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)

        wait = WebDriverWait(driver, 25)

        # 1) Login
        driver.get("https://admin.beotto.com/")
        time.sleep(1.0)  # espera a página e o formulário MUI renderizarem

        _type_by_xpath(driver, wait, "//*[@id='email']", admin_email, "login_email_typed", result)
        time.sleep(0.5)  # deixa o campo de e-mail estabilizar antes de focar no de senha

        # Garante que o campo de senha está clicável antes de digitar (evita perder o valor)
        pass_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='password']")))
        pass_el.click()
        time.sleep(0.3)
        pass_el.clear()
        pass_el.send_keys(admin_password)
        result["steps"]["login_password_typed"] = True

        time.sleep(0.6)  # espera a senha “fixar” antes de clicar em Entrar

        entrar_xpath = (
            "//button[.//span[normalize-space()='Entrar']]"
            " | //button[contains(.,'Entrar')]"
            " | //span[normalize-space()='Entrar']/ancestor::button[1]"
        )
        _click_by_xpath(driver, wait, entrar_xpath, "login_clicked_entrar", result)

        # Se o clique não submeter o formulário, normalmente o campo de login (#email)
        # continua visível. Nesses casos, tentamos submeter via ENTER no campo de senha
        # e, como fallback, clicar via JS.
        try:
            wait_short = WebDriverWait(driver, 8)
            wait_short.until(lambda d: len(d.find_elements(By.XPATH, "//*[@id='email']")) == 0)
        except TimeoutException:
            # Fallback 1: ENTER no campo de senha
            try:
                pw_el = driver.find_element(By.XPATH, "//*[@id='password']")
                pw_el.send_keys(Keys.ENTER)
                time.sleep(1.0)
            except Exception:
                pass

            # Fallback 2: JS click no botão Entrar
            try:
                btns = driver.find_elements(By.XPATH, entrar_xpath)
                if btns:
                    driver.execute_script("arguments[0].click();", btns[0])
                    time.sleep(1.0)
            except Exception:
                pass

            # Última checagem: se #email ainda existe, falhou o login
            if driver.find_elements(By.XPATH, "//*[@id='email']"):
                raise TimeoutException("Falha ao fazer login: tela de login continua visível após clicar/submeter 'Entrar'.")

        # 2) Navegar direto pra tela de gerenciamento
        driver.get("https://admin.beotto.com/configuracoes/gerenciamento-de-usuarios")
        wait.until(lambda d: "/configuracoes/gerenciamento-de-usuarios" in d.current_url)
        result["steps"]["navigated_to_users_page"] = True

        time.sleep(5)  # espera a página de gerenciamento carregar antes de preencher o campo de pesquisa

        # 3) Buscar e-mail
        # Tenta placeholder 'Procure aquí/Procure aqui' (MUI). Fallback para inputs de search.
        search_xpath = (
            "//input[contains(@placeholder,'Procure') or contains(@placeholder,'procure') "
            "or contains(@aria-label,'Procure') or contains(@name,'search') or contains(@id,'search')]"
        )
        _type_by_xpath(driver, wait, search_xpath, target_email, "search_typed", result)

        # 4) Clicar no usuário que apareceu
        email_lit = _xpath_literal(target_email)
        user_row_xpath = (
            "//tbody[contains(@class,'MuiTableBody-root')]//tr[contains(@class,'MuiTableRow-root')]["
            f".//td[contains(normalize-space(.), {email_lit})] "
            f"or .//span[contains(normalize-space(.), {email_lit})] "
            f"or .//*[contains(normalize-space(.), {email_lit})]]"
        )

        # A tabela costuma aparecer após digitar no campo; esperamos o `<tr>` do e-mail alvo.
        wait.until(EC.presence_of_element_located((By.XPATH, user_row_xpath)))
        user_rows = driver.find_elements(By.XPATH, user_row_xpath)
        if not user_rows:
            raise TimeoutException("Nao encontrei a linha da tabela contendo o email alvo.")

        # A linha inteira é clicável (cursor pointer).
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", user_rows[0])
        user_rows[0].click()
        result["steps"]["user_row_clicked"] = True

        # Aguarda o modal abrir e confere se o e-mail do formulário é o TARGET_EMAIL
        time.sleep(1.0)  # espera o modal renderizar
        email_input_xpath = "//div[@role='dialog']//input[@name='email'] | //input[@name='email']"
        email_in_modal_el = wait.until(EC.presence_of_element_located((By.XPATH, email_input_xpath)))
        email_in_modal = (email_in_modal_el.get_attribute("value") or "").strip()
        if email_in_modal.lower() != target_email.strip().lower():
            raise ValueError(
                f"Email do modal nao confere com o alvo. Modal: {email_in_modal!r}, Alvo: {target_email.strip()!r}"
            )
        result["steps"]["email_modal_checked"] = True

        # 5) Na popup, clicar em 'nova'
        nova_xpath = (
            "(//div[@role='dialog']//*[self::button or self::span or self::div]"
            "[contains(translate(normalize-space(.),'NOVA','nova'),'nova')])[1]"
            " | (//*[self::button or self::span or self::div]"
            "[contains(translate(normalize-space(.),'NOVA','nova'),'nova')])[1]"
        )
        _click_by_xpath(driver, wait, nova_xpath, "nova_clicked", result)

        # 6) Preencher senha 'senha123' no campo de nova senha
        # Campo MUI: name="newPassword", type="text" (não é type="password" no DOM).
        new_password_xpath = (
            "//input[@name='newPassword' and not(@disabled)]"
            " | //input[@name='newPassword']"
        )
        new_pass_el = wait.until(EC.presence_of_element_located((By.XPATH, new_password_xpath)))
        # new_pass_el.clear()
        new_pass_el.send_keys("@@Melnick2026")
        result["steps"]["new_password_filled"] = True

        # 7) Clicar em Salvar
        salvar_xpath = (
            "//button[.//span[contains(normalize-space(.),'Salvar')]]"
            " | //button[contains(.,'Salvar')]"
        )
        _click_by_xpath(driver, wait, salvar_xpath, "salvar_clicked", result)

        # 8) Pequena espera para o backend finalizar e fechar modal/toast
        time.sleep(2.5)

        ui_messages = _collect_visible_messages(driver)
        result["ui_messages"] = ui_messages

        # Classificação simples para ajustar ok quando a página mostra erro em formato toast/alert.
        joined = " | ".join(ui_messages).lower()
        if "não foi possível" in joined or "nao foi possivel" in joined or "não foi possivel" in joined:
            result["ok"] = False
            result["error"] = ui_messages[-1] if ui_messages else "Falha reportada pela UI ao atualizar usuário."
        else:
            result["ok"] = True

    except Exception as e:
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()
        try:
            # tenta também capturar mensagens que por acaso já apareçam antes de estourar exceção
            result["ui_messages"] = _collect_visible_messages(driver) if driver is not None else []
        except Exception:
            result["ui_messages"] = []
        try:
            if driver is not None:
                screenshot_path = "/tmp/otto_admin_error.png"
                driver.save_screenshot(screenshot_path)
                result["screenshot"] = screenshot_path
        except Exception:
            pass
    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass

    # Garantir que só há tipos serializáveis em result (evita travar no json.dumps)
    def _serializable(obj):
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, dict):
            return {k: _serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_serializable(x) for x in obj]
        return str(obj)

    try:
        out = json.dumps(_serializable(result), ensure_ascii=False)
        print(out)
    except (TypeError, ValueError) as e:
        print(json.dumps({"ok": False, "error": f"Erro ao serializar resultado: {e}", "raw_error": str(result.get("error"))}))
    except UnicodeEncodeError:
        # No Windows o console às vezes não aceita UTF-8; usa ASCII com escape
        print(json.dumps(_serializable(result), ensure_ascii=True))
    sys.stdout.flush()


if __name__ == "__main__":
    main()

