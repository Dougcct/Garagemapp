import base64
import datetime
import hashlib
import http.server
import json
import os
import secrets
import shutil
import socket
import threading
import time
import urllib.parse
import webbrowser
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_DRIVE_UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/drive/v3/files"
GOOGLE_DRIVE_FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"

NOME_PASTA_DRIVE = "Garagem App - Backup"
NOME_ARQUIVO_BACKUP = "garagem_backup.db"

# O escopo 'drive.file' permite criar/atualizar/restaurar a pasta e o arquivo de backup
# diretamente no Google Drive da pessoa logada, sem exigir verificação restrita do Google.
SCOPES_PADRAO = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
]

# Controle de debounce para backup automático em segundo plano
_timer_backup: Optional[threading.Timer] = None
_lock_backup = threading.Lock()
ultimo_status_backup: str = "Aguardando sincronização"


def possui_credenciais() -> bool:
    """Verifica se o arquivo credentials.json do app ou variáveis de ambiente existem."""
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        return True
    return os.path.exists(CREDENTIALS_PATH)


def salvar_credenciais_manuais(client_id: str, client_secret: str) -> None:
    """Salva o Client ID e Client Secret do projeto OAuth em credentials.json."""
    dados = {
        "installed": {
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "auth_uri": GOOGLE_AUTH_ENDPOINT,
            "token_uri": GOOGLE_TOKEN_ENDPOINT,
            "redirect_uris": ["http://localhost", "http://127.0.0.1"],
        }
    }
    with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def ler_credenciais() -> Tuple[str, str, Optional[int]]:
    """
    Retorna (client_id, client_secret, porta_fixa_opcional) a partir de
    variáveis de ambiente ou do arquivo credentials.json do aplicativo.
    """
    env_id = os.getenv("GOOGLE_CLIENT_ID")
    env_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if env_id and env_secret:
        return env_id.strip(), env_secret.strip(), None

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            "Arquivo 'credentials.json' do aplicativo não encontrado."
        )

    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    bloco = raw.get("installed") or raw.get("web") or raw
    client_id = bloco.get("client_id", "").strip()
    client_secret = bloco.get("client_secret", "").strip()

    if not client_id or not client_secret:
        raise ValueError(
            "O arquivo 'credentials.json' não contém 'client_id' e 'client_secret' válidos."
        )

    porta_fixa = None
    if "web" in raw:
        for uri in bloco.get("redirect_uris", []):
            parsed = urllib.parse.urlparse(uri)
            if parsed.hostname in ("localhost", "127.0.0.1") and parsed.port:
                porta_fixa = parsed.port
                break

    return client_id, client_secret, porta_fixa


def _encontrar_porta_livre(porta_preferida: Optional[int] = None) -> int:
    if porta_preferida:
        return porta_preferida
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _gerar_pkce() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def carregar_sessao_salva() -> Optional[Dict[str, Any]]:
    """Carrega a sessão da pessoa logada em token.json e renova o access_token automaticamente."""
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)

        expira_em = dados.get("expires_at", 0)
        refresh_token = dados.get("refresh_token")

        if time.time() >= expira_em - 60 and refresh_token and possui_credenciais():
            client_id, client_secret, _ = ler_credenciais()
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.status_code == 200:
                    novo_token = resp.json()
                    dados["access_token"] = novo_token["access_token"]
                    dados["expires_at"] = time.time() + int(novo_token.get("expires_in", 3600))
                    with open(TOKEN_PATH, "w", encoding="utf-8") as f_out:
                        json.dump(dados, f_out, indent=2, ensure_ascii=False)

        usuario = dados.get("usuario")
        if usuario and dados.get("access_token"):
            return {
                "nome": usuario.get("name") or usuario.get("nome") or "Motorista Google",
                "email": usuario.get("email") or "",
                "foto": usuario.get("picture") or usuario.get("foto") or "",
                "sub": usuario.get("sub") or "",
                "access_token": dados["access_token"],
                "logado": True,
            }
    except Exception:
        return None
    return None


def fazer_logout() -> None:
    """Desconecta a conta Google atual removendo o token local."""
    if os.path.exists(TOKEN_PATH):
        try:
            os.remove(TOKEN_PATH)
        except OSError:
            pass


def realizar_login_google(timeout: int = 120) -> Dict[str, Any]:
    """
    Abre o navegador para o usuário entrar com a própria Conta Google e autorizar
    o backup no seu próprio Google Drive.
    """
    client_id, client_secret, porta_fixa = ler_credenciais()
    porta = _encontrar_porta_livre(porta_fixa)
    redirect_uri = f"http://127.0.0.1:{porta}"

    state_esperado = secrets.token_urlsafe(24)
    code_verifier, code_challenge = _gerar_pkce()
    resultado_callback: Dict[str, Optional[str]] = {"code": None, "error": None, "state": None}

    class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            resultado_callback["code"] = params.get("code", [None])[0]
            resultado_callback["error"] = params.get("error", [None])[0]
            resultado_callback["state"] = params.get("state", [None])[0]

            sucesso = resultado_callback["code"] is not None and resultado_callback["error"] is None
            titulo = "Conta Google Conectada!" if sucesso else "Falha na autenticação"
            cor = "#64B5F6" if sucesso else "#EF5350"
            mensagem = (
                "Seu Google Drive foi vinculado ao app Garagem para backup automático. "
                "Você já pode fechar esta janela e voltar ao aplicativo."
                if sucesso
                else f"Não foi possível concluir o login ({resultado_callback['error']})."
            )

            html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Garagem - Login Google</title>
<style>
  body {{
    background-color: #121212;
    color: #FFFFFF;
    font-family: 'Segoe UI', Roboto, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    margin: 0;
  }}
  .card {{
    background-color: #1E1E1E;
    border: 1px solid #263238;
    border-radius: 16px;
    padding: 32px;
    max-width: 420px;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }}
  h2 {{ color: {cor}; margin-top: 0; }}
  p {{ color: #B0BEC5; font-size: 14px; line-height: 1.5; }}
</style>
</head>
<body>
  <div class="card">
    <h2>{titulo}</h2>
    <p>{mensagem}</p>
  </div>
  <script>setTimeout(function(){{ window.close(); }}, 2500);</script>
</body>
</html>"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", porta), _OAuthCallbackHandler)
    servidor.timeout = timeout

    params_auth = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES_PADRAO),
        "state": state_esperado,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url_autorizacao = f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params_auth)}"

    webbrowser.open(url_autorizacao)

    try:
        servidor.handle_request()
    finally:
        servidor.server_close()

    if resultado_callback["error"]:
        raise RuntimeError(f"Autorização negada ou cancelada: {resultado_callback['error']}")

    if not resultado_callback["code"]:
        raise TimeoutError("Tempo limite esgotado aguardando o login no navegador.")

    if resultado_callback["state"] != state_esperado:
        raise RuntimeError("Estado OAuth inválido (falha de verificação CSRF).")

    with httpx.Client(timeout=20.0) as client:
        resp_token = client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": resultado_callback["code"],
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if resp_token.status_code != 200:
            raise RuntimeError(f"Erro ao obter token OAuth: {resp_token.text}")

        token_data = resp_token.json()
        access_token = token_data["access_token"]

        resp_user = client.get(
            GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp_user.status_code != 200:
            raise RuntimeError(f"Erro ao buscar perfil do usuário: {resp_user.text}")

        user_info = resp_user.json()

    dados_persistencia = {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": time.time() + int(token_data.get("expires_in", 3600)),
        "usuario": user_info,
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(dados_persistencia, f, indent=2, ensure_ascii=False)

    return {
        "nome": user_info.get("name") or "Motorista Google",
        "email": user_info.get("email") or "",
        "foto": user_info.get("picture") or "",
        "sub": user_info.get("sub") or "",
        "access_token": access_token,
        "logado": True,
    }


def _obter_ou_criar_pasta_drive(client: httpx.Client, headers: Dict[str, str]) -> str:
    """Localiza ou cria a pasta 'Garagem App - Backup' no Google Drive do usuário."""
    query = (
        f"name = '{NOME_PASTA_DRIVE}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    resp = client.get(
        GOOGLE_DRIVE_FILES_ENDPOINT,
        headers=headers,
        params={"q": query, "fields": "files(id, name)"},
    )
    if resp.status_code == 200:
        pastas = resp.json().get("files", [])
        if pastas:
            return pastas[0]["id"]

    # Cria a pasta no Drive do usuário
    resp_criar = client.post(
        GOOGLE_DRIVE_FILES_ENDPOINT,
        headers={**headers, "Content-Type": "application/json"},
        json={
            "name": NOME_PASTA_DRIVE,
            "mimeType": "application/vnd.google-apps.folder",
        },
    )
    if resp_criar.status_code in (200, 201):
        return resp_criar.json()["id"]
    raise RuntimeError(f"Não foi possível criar pasta no Google Drive ({resp_criar.status_code}).")


def _buscar_arquivo_backup_drive(
    client: httpx.Client, headers: Dict[str, str], pasta_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Busca o arquivo garagem_backup.db no Google Drive do usuário logado."""
    filtro_pai = f" and '{pasta_id}' in parents" if pasta_id else ""
    query = f"name = '{NOME_ARQUIVO_BACKUP}'{filtro_pai} and trashed = false"
    resp = client.get(
        GOOGLE_DRIVE_FILES_ENDPOINT,
        headers=headers,
        params={
            "q": query,
            "orderBy": "modifiedTime desc",
            "fields": "files(id, name, modifiedTime, size)",
        },
    )
    if resp.status_code == 200:
        arquivos = resp.json().get("files", [])
        if arquivos:
            return arquivos[0]
    return None


def sincronizar_backup_drive(caminho_db: str) -> Tuple[bool, str]:
    """
    Salva/atualiza o banco SQLite (garagem.db) diretamente na pasta
    'Garagem App - Backup' dentro do próprio Google Drive do usuário logado.
    """
    global ultimo_status_backup
    sessao = carregar_sessao_salva()
    if not sessao or not sessao.get("access_token"):
        return False, "Faça login com sua conta Google para sincronizar no Drive."

    if not os.path.exists(caminho_db):
        return False, "Banco de dados local ainda não existe."

    headers = {"Authorization": f"Bearer {sessao['access_token']}"}

    with _lock_backup:
        try:
            with httpx.Client(timeout=30.0) as client:
                pasta_id = _obter_ou_criar_pasta_drive(client, headers)
                arquivo_existente = _buscar_arquivo_backup_drive(client, headers, pasta_id)

                with open(caminho_db, "rb") as f_db:
                    conteudo_db = f_db.read()

                if arquivo_existente:
                    file_id = arquivo_existente["id"]
                    resp_up = client.patch(
                        f"{GOOGLE_DRIVE_UPLOAD_ENDPOINT}/{file_id}?uploadType=media",
                        headers={**headers, "Content-Type": "application/x-sqlite3"},
                        content=conteudo_db,
                    )
                else:
                    boundary = "===garagem_backup_boundary==="
                    metadados = json.dumps(
                        {"name": NOME_ARQUIVO_BACKUP, "parents": [pasta_id]}
                    )
                    corpo = (
                        f"--{boundary}\r\n"
                        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
                        f"{metadados}\r\n"
                        f"--{boundary}\r\n"
                        "Content-Type: application/x-sqlite3\r\n\r\n"
                    ).encode("utf-8") + conteudo_db + f"\r\n--{boundary}--\r\n".encode("utf-8")

                    resp_up = client.post(
                        f"{GOOGLE_DRIVE_UPLOAD_ENDPOINT}?uploadType=multipart",
                        headers={
                            **headers,
                            "Content-Type": f"multipart/related; boundary={boundary}",
                        },
                        content=corpo,
                    )

                if resp_up.status_code in (200, 201):
                    horario = datetime.datetime.now().strftime("%H:%M:%S")
                    ultimo_status_backup = f"Sincronizado no seu Google Drive às {horario}"
                    return True, ultimo_status_backup
                return False, f"Falha ao salvar no Google Drive ({resp_up.status_code})."
        except Exception as exc:
            return False, f"Erro ao sincronizar com Google Drive: {exc}"


def restaurar_backup_drive(caminho_db: str) -> Tuple[bool, str]:
    """
    Verifica se o usuário possui um backup salvo em seu próprio Google Drive e,
    caso exista, baixa e restaura o arquivo garagem.db localmente.
    """
    global ultimo_status_backup
    sessao = carregar_sessao_salva()
    if not sessao or not sessao.get("access_token"):
        return False, "Usuário não autenticado no Google."

    headers = {"Authorization": f"Bearer {sessao['access_token']}"}

    with _lock_backup:
        try:
            with httpx.Client(timeout=30.0) as client:
                arquivo = _buscar_arquivo_backup_drive(client, headers)
                if not arquivo:
                    return False, "Nenhum backup anterior encontrado no seu Google Drive."

                file_id = arquivo["id"]
                resp_down = client.get(
                    f"{GOOGLE_DRIVE_FILES_ENDPOINT}/{file_id}?alt=media",
                    headers=headers,
                )
                if resp_down.status_code != 200 or not resp_down.content:
                    return False, f"Erro ao baixar backup do Drive ({resp_down.status_code})."

                # Cria cópia de segurança temporária antes de substituir
                caminho_tmp = f"{caminho_db}.bak"
                if os.path.exists(caminho_db):
                    shutil.copy2(caminho_db, caminho_tmp)

                with open(caminho_db, "wb") as f_out:
                    f_out.write(resp_down.content)

                horario = datetime.datetime.now().strftime("%H:%M:%S")
                ultimo_status_backup = f"Backup restaurado do seu Google Drive às {horario}"
                return True, ultimo_status_backup
        except Exception as exc:
            return False, f"Erro ao restaurar backup: {exc}"


def agendar_backup_automatico(
    caminho_db: str, ao_concluir: Optional[Callable[[bool, str], None]] = None
) -> None:
    """
    Agenda o envio automático do banco de dados para o Google Drive da pessoa logada
    1.5s após qualquer alteração (evita múltiplos uploads simultâneos).
    """
    global _timer_backup
    sessao = carregar_sessao_salva()
    if not sessao or not sessao.get("access_token"):
        return

    if _timer_backup is not None:
        _timer_backup.cancel()

    def _executar() -> None:
        ok, msg = sincronizar_backup_drive(caminho_db)
        if ao_concluir:
            try:
                ao_concluir(ok, msg)
            except Exception:
                pass

    _timer_backup = threading.Timer(1.5, _executar)
    _timer_backup.daemon = True
    _timer_backup.start()
