import os
import threading
import flet as ft
import database as db
import auth_google

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")

# Compatibilidade entre versões do Flet (0.24+ e 1.x)
Icons = getattr(ft, "Icons", getattr(ft, "icons", None))
Colors = getattr(ft, "Colors", getattr(ft, "colors", None))
Border = getattr(ft, "Border", getattr(ft, "border", None))
Padding = getattr(ft, "Padding", getattr(ft, "padding", None))
ElevatedButton = getattr(ft, "ElevatedButton", getattr(ft, "Button", None))
ALIGN_CENTER = (
    getattr(ft.Alignment, "CENTER", None)
    if hasattr(ft, "Alignment")
    else getattr(ft.alignment, "center", None)
)


def formatar_moeda(valor: float) -> str:
    return f"R$ {float(valor or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_float_br(texto: str) -> float:
    limpo = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not limpo:
        return 0.0
    if "," in limpo and "." in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    try:
        return max(0.0, float(limpo))
    except ValueError:
        return 0.0


def abrir_modal(page: ft.Page, dialog: ft.AlertDialog) -> None:
    """Abre um AlertDialog de forma compatível com múltiplas versões do Flet."""
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
    elif hasattr(page, "open"):
        page.open(dialog)
    else:
        page.dialog = dialog
        dialog.open = True
        page.update()


def fechar_modal(page: ft.Page, dialog: ft.AlertDialog) -> None:
    """Fecha um AlertDialog de forma compatível com múltiplas versões do Flet."""
    if hasattr(page, "pop_dialog"):
        page.pop_dialog()
    elif hasattr(page, "close"):
        page.close(dialog)
    else:
        dialog.open = False
        page.update()


def mostrar_snackbar(page: ft.Page, mensagem: str, cor: str = "#263238") -> None:
    snack = ft.SnackBar(
        content=ft.Text(mensagem, color="#FFFFFF", size=13),
        bgcolor=cor,
        duration=2200,
    )
    if hasattr(page, "show_dialog"):
        page.show_dialog(snack)
    elif hasattr(page, "open"):
        page.open(snack)
    else:
        page.snack_bar = snack
        snack.open = True
        page.update()


def main(page: ft.Page) -> None:
    # Inicializa SQLite com tabelas, migrações automáticas e dados iniciais
    db.init_db()

    # Configurações Globais da Página (Mobile Frame + Material Design 3 + Dark #121212)
    page.title = "Garagem"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#121212"
    page.padding = 0
    page.window.width = 420
    page.window.height = 840
    page.window.min_width = 360
    page.window.min_height = 680
    if os.path.exists(ICON_ICO_PATH):
        page.window.icon = ICON_ICO_PATH
    page.theme = ft.Theme(
        use_material3=True,
        color_scheme_seed="#64B5F6",
        scaffold_bgcolor="#121212",
    )

    # Estado da sessão em memória (restaura token.json se já estiver autenticado)
    sessao_salva = auth_google.carregar_sessao_salva()
    veiculos_iniciais = db.listar_veiculos()
    estado = {
        "usuario": sessao_salva
        or {
            "nome": "Motorista Google",
            "email": "motorista@gmail.com",
            "foto": "",
            "logado": False,
        },
        "veiculo_ativo_id": veiculos_iniciais[0]["id"] if veiculos_iniciais else None,
        "aba_atual": 0,  # 0 = Home, 1 = Histórico, 2 = Ficha Técnica, 3 = Abastecer
        "filtro_historico_veiculo": False,  # False = Todos, True = Apenas veículo ativo
        "busca_historico": "",
    }

    # =========================================================================
    # AÇÃO DE LOGIN GOOGLE (OAuth 2.0 Real + Backup no Google Drive)
    # =========================================================================
    def iniciar_fluxo_oauth() -> None:
        mostrar_snackbar(
            page,
            "Abrindo navegador para autenticar sua Conta Google...",
            "#1976D2",
        )

        def _worker() -> None:
            try:
                dados_usuario = auth_google.realizar_login_google()
                estado["usuario"] = dados_usuario

                restaurado, _ = auth_google.restaurar_backup_drive(db.DB_PATH)
                if not restaurado:
                    auth_google.sincronizar_backup_drive(db.DB_PATH)
                else:
                    db.init_db()
                    veiculos = db.listar_veiculos()
                    estado["veiculo_ativo_id"] = veiculos[0]["id"] if veiculos else None

                navegar("/home")
                resumo_drive = (
                    "Backup restaurado do seu Drive!"
                    if restaurado
                    else "Backup ativo no seu Google Drive!"
                )
                mostrar_snackbar(
                    page,
                    f"Olá, {dados_usuario['nome']}! {resumo_drive}",
                    "#2E7D32",
                )
            except Exception as exc:
                mostrar_snackbar(page, f"Falha no login Google: {exc}", "#EF5350")

        threading.Thread(target=_worker, daemon=True).start()

    def abrir_modal_configurar_oauth(permitir_demo: bool = True) -> None:
        tf_client_id = ft.TextField(
            label="Google OAuth Client ID",
            hint_text="Ex: 123456-abc.apps.googleusercontent.com",
            border_color="#37474F",
            focused_border_color="#64B5F6",
            text_size=12,
        )
        tf_client_secret = ft.TextField(
            label="Google OAuth Client Secret",
            password=True,
            can_reveal_password=True,
            border_color="#37474F",
            focused_border_color="#64B5F6",
            text_size=12,
        )

        def salvar_e_logar(_: ft.ControlEvent) -> None:
            cid = (tf_client_id.value or "").strip()
            csecret = (tf_client_secret.value or "").strip()
            if not cid or not csecret:
                mostrar_snackbar(page, "Preencha o Client ID e o Client Secret.", "#EF5350")
                return
            auth_google.salvar_credenciais_manuais(cid, csecret)
            fechar_modal(page, modal_cfg)
            iniciar_fluxo_oauth()

        def entrar_modo_demo(_: ft.ControlEvent) -> None:
            fechar_modal(page, modal_cfg)
            estado["usuario"] = {
                "nome": "Motorista (Modo Local)",
                "email": "local@garagem.app",
                "foto": "",
                "logado": True,
            }
            navegar("/home")
            mostrar_snackbar(page, "Conectado em Modo Local (sem sincronização Drive).", "#263238")

        acoes = [
            ft.TextButton("Cancelar", on_click=lambda _: fechar_modal(page, modal_cfg)),
        ]
        if permitir_demo:
            acoes.append(
                ft.TextButton("Modo Local (Demo)", on_click=entrar_modo_demo),
            )
        acoes.append(
            ElevatedButton(
                "Salvar e Entrar",
                bgcolor="#64B5F6",
                color="#121212",
                on_click=salvar_e_logar,
            )
        )

        modal_cfg = ft.AlertDialog(
            modal=True,
            bgcolor="#1E1E1E",
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(Icons.LOCK_PERSON_ROUNDED, color="#64B5F6", size=22),
                    ft.Text("Configurar Login Google", size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    ft.Text(
                        "Para autenticar com sua conta real do Google, coloque o arquivo "
                        "'credentials.json' na pasta do projeto ou cole suas credenciais abaixo:",
                        size=12,
                        color="#B0BEC5",
                    ),
                    tf_client_id,
                    tf_client_secret,
                ],
            ),
            actions=acoes,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_modal(page, modal_cfg)

    def login_google(e: ft.ControlEvent) -> None:
        sessao_existente = auth_google.carregar_sessao_salva()
        if sessao_existente:
            estado["usuario"] = sessao_existente
            auth_google.agendar_backup_automatico(db.DB_PATH)
            navegar("/home")
            mostrar_snackbar(
                page,
                f"Bem-vindo de volta, {sessao_existente['nome']}!",
                "#2E7D32",
            )
            return

        if auth_google.possui_credenciais():
            iniciar_fluxo_oauth()
        else:
            abrir_modal_configurar_oauth(permitir_demo=True)

    # =========================================================================
    # ROTA 1: /login
    # =========================================================================
    def construir_view_login() -> ft.View:
        icone_garagem_stack = ft.Container(
            width=132,
            height=132,
            border_radius=26,
            bgcolor="#121212",
            alignment=ALIGN_CENTER,
            content=ft.Image(
                src=ICON_PNG_PATH,
                width=128,
                height=128,
                border_radius=24,
            ),
        )

        icone_google = ft.Container(
            width=26,
            height=26,
            border_radius=13,
            bgcolor="#FFFFFF",
            alignment=ALIGN_CENTER,
            content=ft.Text(
                "G",
                size=15,
                weight=ft.FontWeight.BOLD,
                color="#1976D2",
            ),
        )

        botao_google = ElevatedButton(
            height=50,
            width=270,
            on_click=login_google,
            style=ft.ButtonStyle(
                bgcolor="#263238",
                color="#FFFFFF",
                elevation=2,
                shape=ft.StadiumBorder(),
                padding=Padding.symmetric(horizontal=20),
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    icone_google,
                    ft.Text(
                        "Entrar com Google",
                        size=15,
                        weight=ft.FontWeight.W_600,
                        color="#FFFFFF",
                    ),
                ],
            ),
        )

        bloco_central = ft.Container(
            expand=True,
            alignment=ALIGN_CENTER,
            padding=Padding.symmetric(horizontal=28),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    icone_garagem_stack,
                    ft.Container(height=16),
                    ft.Text(
                        "Garagem",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        color="#FFFFFF",
                    ),
                    ft.Container(height=42),
                    botao_google,
                    ft.Container(height=12),
                    ft.Text(
                        "Acesse para salvar suas manutenções",
                        size=12,
                        color="#9E9E9E",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )

        rodape = ft.Container(
            padding=Padding.only(bottom=24, top=12),
            alignment=ALIGN_CENTER,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                controls=[
                    ft.Icon(Icons.CLOUD_DONE_OUTLINED, size=15, color="#9E9E9E"),
                    ft.Text(
                        "Backup automático no Google Drive",
                        size=12,
                        color="#9E9E9E",
                    ),
                ],
            ),
        )

        return ft.View(
            route="/login",
            bgcolor="#121212",
            padding=0,
            controls=[
                ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        bloco_central,
                        rodape,
                    ],
                )
            ],
        )

    # =========================================================================
    # ROTA 2: /home (Painel, Veículos, Alertas, Histórico, Ficha e Abastecimento)
    # =========================================================================
    def construir_view_home() -> ft.View:
        carrossel_veiculos = ft.Row(
            scroll=ft.ScrollMode.HIDDEN,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        campo_km_atual = ft.TextField(
            label="KM Atual",
            keyboard_type=ft.KeyboardType.NUMBER,
            height=44,
            text_size=14,
            content_padding=Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            border_color="#37474F",
            focused_border_color="#64B5F6",
            bgcolor="#1A1A1A",
            color="#FFFFFF",
            label_style=ft.TextStyle(color="#9E9E9E", size=12),
            expand=True,
        )

        icone_botao_km = ft.IconButton(
            icon=Icons.CHECK_CIRCLE_ROUNDED,
            icon_color="#64B5F6",
            bgcolor="#1E272C",
            tooltip="Salvar novo odômetro (KM)",
        )

        icone_botao_abastecer_rapido = ft.IconButton(
            icon=Icons.LOCAL_GAS_STATION_ROUNDED,
            icon_color="#FFCA28",
            bgcolor="#262216",
            tooltip="Registrar Abastecimento Rápido (km/L)",
        )

        coluna_alertas_slim = ft.Column(spacing=6)
        contador_alertas_badge = ft.Container(
            padding=Padding.symmetric(horizontal=8, vertical=2),
            border_radius=10,
            bgcolor="#263238",
            content=ft.Text("0", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        )

        container_corpo_principal = ft.Container(expand=True)

        # ---------------------------------------------------------------------
        # Funções Auxiliares e Modais (CRUD Completo + Finanças + Abastecimento)
        # ---------------------------------------------------------------------
        def icone_por_tipo(tipo: str) -> str:
            return (
                Icons.TWO_WHEELER_ROUNDED
                if tipo == "moto"
                else Icons.DIRECTIONS_CAR_FILLED_ROUNDED
            )

        def selecionar_veiculo(veiculo_id: int) -> None:
            estado["veiculo_ativo_id"] = veiculo_id
            atualizar_interface_home()

        def salvar_km_rapido(e: ft.ControlEvent = None) -> None:
            veiculo_id = estado["veiculo_ativo_id"]
            if not veiculo_id:
                return
            valor_limpo = (
                (campo_km_atual.value or "").replace(".", "").replace(",", "").strip()
            )
            if not valor_limpo.isdigit():
                mostrar_snackbar(
                    page, "Informe um valor numérico válido para o KM.", "#EF5350"
                )
                return

            novo_km = int(valor_limpo)
            db.atualizar_km_veiculo(veiculo_id, novo_km)
            atualizar_interface_home()
            auth_google.agendar_backup_automatico(db.DB_PATH)
            mostrar_snackbar(
                page,
                f"Odômetro atualizado para {novo_km:,} km!".replace(",", "."),
                "#2E7D32",
            )

        campo_km_atual.on_submit = salvar_km_rapido
        icone_botao_km.on_click = salvar_km_rapido

        # ---------------------------------------------------------------------
        # MODAL: Novo Veículo / Editar Veículo / Excluir Veículo (Fase 1)
        # ---------------------------------------------------------------------
        def abrir_modal_novo_veiculo(e: ft.ControlEvent = None) -> None:
            tf_nome = ft.TextField(
                label="Modelo do veículo (ex: Honda Fit 1.5)",
                autofocus=True,
                border_color="#37474F",
                focused_border_color="#64B5F6",
            )
            dd_tipo = ft.Dropdown(
                label="Categoria",
                value="carro",
                border_color="#37474F",
                options=[
                    ft.dropdown.Option("carro", "Carro"),
                    ft.dropdown.Option("moto", "Moto"),
                ],
            )
            tf_km = ft.TextField(
                label="Odômetro inicial (KM)",
                value="0",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
            )
            tf_ano = ft.TextField(
                label="Ano (ex: 2023)",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_placa = ft.TextField(
                label="Placa (opcional)",
                border_color="#37474F",
                expand=True,
            )

            def confirmar_cadastro(_: ft.ControlEvent) -> None:
                nome = (tf_nome.value or "").strip()
                km_str = (tf_km.value or "0").replace(".", "").strip()
                ano_str = (tf_ano.value or "").strip()
                if not nome:
                    mostrar_snackbar(page, "Digite o nome do veículo.", "#EF5350")
                    return
                km_val = int(km_str) if km_str.isdigit() else 0
                ano_val = int(ano_str) if ano_str.isdigit() else None
                novo_id = db.adicionar_veiculo(
                    nome=nome,
                    tipo=dd_tipo.value or "carro",
                    km_atual=km_val,
                    ano=ano_val,
                    placa=(tf_placa.value or "").strip().upper(),
                )
                estado["veiculo_ativo_id"] = novo_id
                fechar_modal(page, modal_veiculo)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(
                    page, f"Veículo '{nome}' adicionado com plano preventivo!", "#2E7D32"
                )

            modal_veiculo = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Text("Novo Veículo", size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_nome,
                        dd_tipo,
                        tf_km,
                        ft.Row(spacing=8, controls=[tf_ano, tf_placa]),
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar",
                        on_click=lambda _: fechar_modal(page, modal_veiculo),
                    ),
                    ElevatedButton(
                        "Salvar",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=confirmar_cadastro,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            abrir_modal(page, modal_veiculo)

        def abrir_modal_editar_veiculo(veiculo: dict) -> None:
            tf_nome = ft.TextField(
                label="Modelo do veículo",
                value=veiculo["nome"],
                border_color="#37474F",
                focused_border_color="#64B5F6",
            )
            dd_tipo = ft.Dropdown(
                label="Categoria",
                value=veiculo["tipo"],
                border_color="#37474F",
                options=[
                    ft.dropdown.Option("carro", "Carro"),
                    ft.dropdown.Option("moto", "Moto"),
                ],
            )
            tf_km = ft.TextField(
                label="Odômetro Atual (KM)",
                value=str(veiculo["km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
            )
            tf_ano = ft.TextField(
                label="Ano",
                value=str(veiculo["ano"] or ""),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_placa = ft.TextField(
                label="Placa",
                value=veiculo.get("placa") or "",
                border_color="#37474F",
                expand=True,
            )

            def salvar_edicao(_: ft.ControlEvent) -> None:
                nome = (tf_nome.value or "").strip()
                km_str = (tf_km.value or "0").replace(".", "").strip()
                ano_str = (tf_ano.value or "").strip()
                if not nome:
                    mostrar_snackbar(page, "O nome não pode ficar vazio.", "#EF5350")
                    return
                db.editar_veiculo(
                    veiculo_id=veiculo["id"],
                    nome=nome,
                    tipo=dd_tipo.value or "carro",
                    km_atual=int(km_str) if km_str.isdigit() else veiculo["km_atual"],
                    ano=int(ano_str) if ano_str.isdigit() else None,
                    placa=tf_placa.value or "",
                )
                fechar_modal(page, modal_edit)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, f"Veículo '{nome}' atualizado!", "#2E7D32")

            def excluir_este_veiculo(_: ft.ControlEvent) -> None:
                db.excluir_veiculo(veiculo["id"])
                restantes = db.listar_veiculos()
                estado["veiculo_ativo_id"] = restantes[0]["id"] if restantes else None
                fechar_modal(page, modal_edit)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(
                    page, f"Veículo '{veiculo['nome']}' removido.", "#263238"
                )

            modal_edit = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(Icons.SETTINGS_SUGGEST_ROUNDED, color="#64B5F6", size=22),
                        ft.Text("Editar Veículo", size=17, weight=ft.FontWeight.BOLD),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_nome,
                        dd_tipo,
                        tf_km,
                        ft.Row(spacing=8, controls=[tf_ano, tf_placa]),
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Excluir Veículo",
                        style=ft.ButtonStyle(color="#EF5350"),
                        on_click=excluir_este_veiculo,
                    ),
                    ft.Row(
                        tight=True,
                        spacing=6,
                        controls=[
                            ft.TextButton(
                                "Cancelar",
                                on_click=lambda _: fechar_modal(page, modal_edit),
                            ),
                            ElevatedButton(
                                "Salvar",
                                bgcolor="#64B5F6",
                                color="#121212",
                                on_click=salvar_edicao,
                            ),
                        ],
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            abrir_modal(page, modal_edit)

        # ---------------------------------------------------------------------
        # MODAL: Concluir Manutenção Preventiva com Valor R$ e Oficina (Fase 2)
        # ---------------------------------------------------------------------
        def abrir_modal_concluir(alerta: dict) -> None:
            tf_km_baixa = ft.TextField(
                label="KM em que foi realizada",
                value=str(alerta["veiculo_km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                focused_border_color="#64B5F6",
                expand=True,
            )
            tf_valor = ft.TextField(
                label="Valor R$ (opcional)",
                hint_text="Ex: 280,00",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                focused_border_color="#64B5F6",
                expand=True,
            )
            tf_oficina = ft.TextField(
                label="Oficina / Local (opcional)",
                hint_text="Ex: Auto Center / Em casa",
                border_color="#37474F",
            )
            tf_obs = ft.TextField(
                label="Observações / Peças utilizadas",
                value=alerta.get("observacoes") or "",
                border_color="#37474F",
            )

            def confirmar_baixa(_: ft.ControlEvent) -> None:
                km_str = (tf_km_baixa.value or "").replace(".", "").strip()
                if not km_str.isdigit():
                    mostrar_snackbar(page, "Informe um KM válido.", "#EF5350")
                    return
                km_realizado = int(km_str)
                valor_num = parse_float_br(tf_valor.value or "0")
                db.concluir_preventiva(
                    preventiva_id=alerta["id"],
                    km_realizado=km_realizado,
                    observacoes=tf_obs.value or "",
                    valor=valor_num,
                    oficina=tf_oficina.value or "",
                )
                fechar_modal(page, modal_baixa)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(
                    page,
                    f"Baixa registrada: {alerta['veiculo_nome']} - {alerta['item']}!",
                    "#2E7D32",
                )

            modal_baixa = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(Icons.TASK_ALT_ROUNDED, color="#64B5F6", size=22),
                        ft.Text("Concluir Manutenção", size=17, weight=ft.FontWeight.BOLD),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            f"{alerta['veiculo_nome']} • {alerta['item']}",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color="#64B5F6",
                        ),
                        ft.Row(spacing=8, controls=[tf_km_baixa, tf_valor]),
                        tf_oficina,
                        tf_obs,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar",
                        on_click=lambda _: fechar_modal(page, modal_baixa),
                    ),
                    ElevatedButton(
                        "Confirmar Baixa",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=confirmar_baixa,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            abrir_modal(page, modal_baixa)

        # ---------------------------------------------------------------------
        # MODAL: Nova / Editar Preventiva com Intervalo KM + Meses (Fases 1 e 3)
        # ---------------------------------------------------------------------
        def abrir_modal_nova_preventiva(veiculo: dict) -> None:
            tf_item = ft.TextField(
                label="Item (ex: Correia Dentada, Velas)",
                autofocus=True,
                border_color="#37474F",
            )
            tf_intervalo_km = ft.TextField(
                label="Intervalo (KM)",
                value="10000",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_intervalo_meses = ft.TextField(
                label="Prazo (Meses)",
                value="12",
                hint_text="0 = só KM",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_ultimo_km = ft.TextField(
                label="Último KM realizado",
                value=str(veiculo["km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
            )
            tf_obs = ft.TextField(
                label="Especificação técnica (ex: 5W30 API SP)",
                border_color="#37474F",
            )

            def salvar_item(_: ft.ControlEvent) -> None:
                nome_item = (tf_item.value or "").strip()
                int_str = (tf_intervalo_km.value or "").replace(".", "").strip()
                meses_str = (tf_intervalo_meses.value or "0").strip()
                ult_str = (tf_ultimo_km.value or "").replace(".", "").strip()
                if not nome_item or not int_str.isdigit() or not ult_str.isdigit():
                    mostrar_snackbar(
                        page,
                        "Preencha corretamente o item e as quilometragens.",
                        "#EF5350",
                    )
                    return
                db.adicionar_preventiva(
                    veiculo_id=veiculo["id"],
                    item=nome_item,
                    intervalo_km=max(100, int(int_str)),
                    ultimo_km=int(ult_str),
                    observacoes=tf_obs.value or "",
                    intervalo_meses=int(meses_str) if meses_str.isdigit() else 0,
                )
                fechar_modal(page, modal_prev)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(
                    page, f"Item '{nome_item}' adicionado ao plano!", "#2E7D32"
                )

            modal_prev = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Text(
                    f"Novo Item • {veiculo['nome']}", size=16, weight=ft.FontWeight.BOLD
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_item,
                        ft.Row(spacing=8, controls=[tf_intervalo_km, tf_intervalo_meses]),
                        tf_ultimo_km,
                        tf_obs,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda _: fechar_modal(page, modal_prev)
                    ),
                    ElevatedButton(
                        "Adicionar",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=salvar_item,
                    ),
                ],
            )
            abrir_modal(page, modal_prev)

        def abrir_modal_editar_preventiva(prev: dict) -> None:
            tf_item = ft.TextField(
                label="Item",
                value=prev["item"],
                border_color="#37474F",
            )
            tf_intervalo_km = ft.TextField(
                label="Intervalo (KM)",
                value=str(prev["intervalo_km"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_intervalo_meses = ft.TextField(
                label="Prazo (Meses)",
                value=str(prev.get("intervalo_meses") or 0),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_ultimo_km = ft.TextField(
                label="Último KM realizado",
                value=str(prev["ultimo_km"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
            )
            tf_obs = ft.TextField(
                label="Especificação técnica",
                value=prev.get("observacoes") or "",
                border_color="#37474F",
            )

            def salvar_edicao_prev(_: ft.ControlEvent) -> None:
                nome_item = (tf_item.value or "").strip()
                int_str = (tf_intervalo_km.value or "").replace(".", "").strip()
                meses_str = (tf_intervalo_meses.value or "0").strip()
                ult_str = (tf_ultimo_km.value or "").replace(".", "").strip()
                if not nome_item or not int_str.isdigit() or not ult_str.isdigit():
                    mostrar_snackbar(page, "Verifique os campos informados.", "#EF5350")
                    return
                db.editar_preventiva(
                    preventiva_id=prev["id"],
                    item=nome_item,
                    intervalo_km=int(int_str),
                    ultimo_km=int(ult_str),
                    observacoes=tf_obs.value or "",
                    intervalo_meses=int(meses_str) if meses_str.isdigit() else 0,
                )
                fechar_modal(page, modal_edit_prev)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, f"Item '{nome_item}' atualizado!", "#2E7D32")

            def remover_prev(_: ft.ControlEvent) -> None:
                db.excluir_preventiva(prev["id"])
                fechar_modal(page, modal_edit_prev)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, f"Item '{prev['item']}' removido.", "#263238")

            modal_edit_prev = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Text("Editar Item Preventivo", size=16, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_item,
                        ft.Row(spacing=8, controls=[tf_intervalo_km, tf_intervalo_meses]),
                        tf_ultimo_km,
                        tf_obs,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Excluir",
                        style=ft.ButtonStyle(color="#EF5350"),
                        on_click=remover_prev,
                    ),
                    ft.Row(
                        tight=True,
                        spacing=6,
                        controls=[
                            ft.TextButton(
                                "Cancelar",
                                on_click=lambda _: fechar_modal(page, modal_edit_prev),
                            ),
                            ElevatedButton(
                                "Salvar",
                                bgcolor="#64B5F6",
                                color="#121212",
                                on_click=salvar_edicao_prev,
                            ),
                        ],
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            abrir_modal(page, modal_edit_prev)

        # ---------------------------------------------------------------------
        # MODAL: Manutenção Corretiva / Avulsa (Fase 2)
        # ---------------------------------------------------------------------
        def abrir_modal_manutencao_avulsa(_: ft.ControlEvent = None) -> None:
            veiculo = (
                db.obter_veiculo(estado["veiculo_ativo_id"])
                if estado["veiculo_ativo_id"]
                else None
            )
            if not veiculo:
                mostrar_snackbar(page, "Cadastre ou selecione um veículo primeiro.", "#EF5350")
                return

            tf_servico = ft.TextField(
                label="Serviço ou Peça (ex: Troca de Bateria 60Ah)",
                autofocus=True,
                border_color="#37474F",
            )
            tf_km_serv = ft.TextField(
                label="KM Realizado",
                value=str(veiculo["km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_valor_serv = ft.TextField(
                label="Valor Gasto (R$)",
                hint_text="Ex: 450,00",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_oficina_serv = ft.TextField(
                label="Oficina / Loja (opcional)",
                border_color="#37474F",
            )
            tf_obs_serv = ft.TextField(
                label="Observações / Garantia",
                border_color="#37474F",
            )

            def salvar_avulsa(_: ft.ControlEvent) -> None:
                item_txt = (tf_servico.value or "").strip()
                km_str = (tf_km_serv.value or "").replace(".", "").strip()
                if not item_txt or not km_str.isdigit():
                    mostrar_snackbar(
                        page, "Informe a descrição do serviço e o KM.", "#EF5350"
                    )
                    return
                db.adicionar_manutencao_avulsa(
                    veiculo_id=veiculo["id"],
                    item=item_txt,
                    km_realizado=int(km_str),
                    valor=parse_float_br(tf_valor_serv.value or "0"),
                    oficina=tf_oficina_serv.value or "",
                    observacoes=tf_obs_serv.value or "",
                )
                fechar_modal(page, modal_avulsa)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(
                    page, f"Serviço '{item_txt}' registrado no histórico!", "#2E7D32"
                )

            modal_avulsa = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(Icons.HANDYMAN_ROUNDED, color="#FFCA28", size=20),
                        ft.Text(
                            f"Manutenção Avulsa • {veiculo['nome']}",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_servico,
                        ft.Row(spacing=8, controls=[tf_km_serv, tf_valor_serv]),
                        tf_oficina_serv,
                        tf_obs_serv,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda _: fechar_modal(page, modal_avulsa)
                    ),
                    ElevatedButton(
                        "Registrar",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=salvar_avulsa,
                    ),
                ],
            )
            abrir_modal(page, modal_avulsa)

        # ---------------------------------------------------------------------
        # MODAL: Registrar Abastecimento e Calcular Consumo km/L (Fase 4)
        # ---------------------------------------------------------------------
        def abrir_modal_abastecimento(_: ft.ControlEvent = None) -> None:
            veiculo = (
                db.obter_veiculo(estado["veiculo_ativo_id"])
                if estado["veiculo_ativo_id"]
                else None
            )
            if not veiculo:
                mostrar_snackbar(page, "Selecione um veículo primeiro.", "#EF5350")
                return

            tf_km_abast = ft.TextField(
                label=f"Novo KM no Odômetro (atual: {veiculo['km_atual']})",
                value=str(veiculo["km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                autofocus=True,
                border_color="#37474F",
            )
            tf_litros = ft.TextField(
                label="Litros (L)",
                hint_text="Ex: 38,5",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            tf_valor_total = ft.TextField(
                label="Valor Total (R$)",
                hint_text="Ex: 230,00",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                expand=True,
            )
            dd_combustivel = ft.Dropdown(
                label="Combustível",
                value="Gasolina",
                border_color="#37474F",
                options=[
                    ft.dropdown.Option("Gasolina", "Gasolina Comum / Aditivada"),
                    ft.dropdown.Option("Etanol", "Etanol"),
                    ft.dropdown.Option("Diesel", "Diesel"),
                    ft.dropdown.Option("GNV", "GNV"),
                ],
            )

            def confirmar_abastecimento(_: ft.ControlEvent) -> None:
                km_str = (tf_km_abast.value or "").replace(".", "").strip()
                litros_val = parse_float_br(tf_litros.value or "0")
                valor_val = parse_float_br(tf_valor_total.value or "0")

                if not km_str.isdigit() or litros_val <= 0:
                    mostrar_snackbar(
                        page, "Informe o odômetro (KM) e a quantidade de litros.", "#EF5350"
                    )
                    return

                res = db.registrar_abastecimento(
                    veiculo_id=veiculo["id"],
                    km_atual=int(km_str),
                    litros=litros_val,
                    valor_total=valor_val,
                    combustivel=dd_combustivel.value or "Gasolina",
                )
                fechar_modal(page, modal_abast)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                msg_media = (
                    f" • Consumo: {res['km_por_litro']} km/L!"
                    if res["km_por_litro"] > 0
                    else "!"
                )
                mostrar_snackbar(
                    page, f"Abastecimento salvo{msg_media}", "#2E7D32"
                )

            modal_abast = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(Icons.LOCAL_GAS_STATION_ROUNDED, color="#FFCA28", size=22),
                        ft.Text(
                            f"Abastecer • {veiculo['nome']}",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        tf_km_abast,
                        ft.Row(spacing=8, controls=[tf_litros, tf_valor_total]),
                        dd_combustivel,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda _: fechar_modal(page, modal_abast)
                    ),
                    ElevatedButton(
                        "Salvar Abastecimento",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=confirmar_abastecimento,
                    ),
                ],
            )
            abrir_modal(page, modal_abast)

        icone_botao_abastecer_rapido.on_click = abrir_modal_abastecimento

        # ---------------------------------------------------------------------
        # MODAL: Exportar Dossiê de Manutenção do Veículo (Fase 5)
        # ---------------------------------------------------------------------
        def abrir_modal_dossie(veiculo: dict) -> None:
            texto_dossie = db.gerar_dossie_texto(veiculo["id"])
            tf_preview = ft.TextField(
                value=texto_dossie,
                multiline=True,
                min_lines=8,
                max_lines=11,
                read_only=True,
                text_size=11,
                border_color="#37474F",
                bgcolor="#141414",
            )

            def abrir_html_pdf(_: ft.ControlEvent) -> None:
                try:
                    db.exportar_dossie_html(veiculo["id"])
                    fechar_modal(page, modal_dossie)
                    mostrar_snackbar(
                        page,
                        "Relatório aberto no navegador (use Imprimir / Salvar PDF)!",
                        "#2E7D32",
                    )
                except Exception as exc:
                    mostrar_snackbar(page, f"Erro ao gerar relatório: {exc}", "#EF5350")

            modal_dossie = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(Icons.DESCRIPTION_OUTLINED, color="#64B5F6", size=22),
                        ft.Text(
                            f"Dossiê • {veiculo['nome']}",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            "Resumo pronto para compartilhar no WhatsApp ou imprimir em PDF:",
                            size=12,
                            color="#B0BEC5",
                        ),
                        tf_preview,
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Fechar", on_click=lambda _: fechar_modal(page, modal_dossie)
                    ),
                    ElevatedButton(
                        "Abrir Relatório Web / PDF",
                        icon=Icons.PRINT_ROUNDED,
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=abrir_html_pdf,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            abrir_modal(page, modal_dossie)

        # ---------------------------------------------------------------------
        # Construção dos Cards do Carrossel e Cards Slim de Alertas
        # ---------------------------------------------------------------------
        def criar_card_veiculo(veiculo: dict, ativo: bool) -> ft.Container:
            cor_borda = "#64B5F6" if ativo else "#2A2A2A"
            espessura_borda = 2.0 if ativo else 1.0
            cor_fundo = "#1B262D" if ativo else "#1C1C1C"
            cor_icone = "#64B5F6" if ativo else "#9E9E9E"

            return ft.Container(
                width=116,
                height=102,
                border_radius=12,
                bgcolor=cor_fundo,
                border=Border.all(espessura_borda, cor_borda),
                padding=Padding.all(10),
                ink=True,
                on_click=lambda _, vid=veiculo["id"]: selecionar_veiculo(vid),
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    spacing=2,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(
                                    icone_por_tipo(veiculo["tipo"]),
                                    color=cor_icone,
                                    size=22,
                                ),
                                ft.Container(
                                    width=24,
                                    height=24,
                                    border_radius=12,
                                    alignment=ALIGN_CENTER,
                                    tooltip="Editar ou excluir veículo",
                                    on_click=lambda _, v=veiculo: abrir_modal_editar_veiculo(v),
                                    content=ft.Icon(
                                        Icons.MORE_VERT_ROUNDED,
                                        size=16,
                                        color="#64B5F6" if ativo else "#757575",
                                    ),
                                ),
                            ],
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(
                                    veiculo["nome"],
                                    size=12,
                                    weight=ft.FontWeight.BOLD
                                    if ativo
                                    else ft.FontWeight.W_500,
                                    color="#FFFFFF",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"{veiculo['km_atual']:,} km".replace(",", "."),
                                    size=10,
                                    color="#64B5F6" if ativo else "#9E9E9E",
                                ),
                            ],
                        ),
                    ],
                ),
            )

        def criar_card_adicionar_veiculo() -> ft.Container:
            return ft.Container(
                width=108,
                height=102,
                border_radius=12,
                bgcolor="#161616",
                border=Border.all(1.2, "#455A64"),
                padding=4,
                ink=True,
                on_click=abrir_modal_novo_veiculo,
                content=ft.Container(
                    border_radius=9,
                    border=Border.all(1, "#263238"),
                    padding=6,
                    alignment=ALIGN_CENTER,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Icon(
                                Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                                color="#64B5F6",
                                size=22,
                            ),
                            ft.Text(
                                "+ Adicionar\nnovo veículo",
                                size=10,
                                color="#B0BEC5",
                                weight=ft.FontWeight.W_500,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                ),
            )

        def criar_card_alerta_slim(alerta: dict) -> ft.Container:
            cor_status = alerta["cor"]

            return ft.Container(
                bgcolor="#1C1C1C",
                border_radius=10,
                border=Border.all(1, "#292929"),
                padding=Padding.symmetric(horizontal=10, vertical=8),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Container(
                            width=10,
                            height=10,
                            border_radius=5,
                            bgcolor=cor_status,
                            tooltip="Vencido"
                            if alerta["status"] == "vencido"
                            else "Próximo de vencer (≤15%)",
                        ),
                        ft.Column(
                            expand=True,
                            spacing=3,
                            controls=[
                                ft.Row(
                                    spacing=5,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(
                                            icone_por_tipo(alerta["veiculo_tipo"]),
                                            size=14,
                                            color="#B0BEC5",
                                        ),
                                        ft.Text(
                                            f"{alerta['veiculo_nome']} - {alerta['item']}",
                                            size=12,
                                            weight=ft.FontWeight.W_600,
                                            color="#FFFFFF",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True,
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text(
                                            alerta["texto_status"],
                                            size=11,
                                            weight=ft.FontWeight.W_500,
                                            color=cor_status,
                                        ),
                                        ft.Text(
                                            f"Meta: {alerta['proximo_km']:,} km".replace(
                                                ",", "."
                                            ),
                                            size=10,
                                            color="#757575",
                                        ),
                                    ],
                                ),
                                ft.ProgressBar(
                                    value=alerta["progresso"],
                                    height=3,
                                    color=cor_status,
                                    bgcolor="#2C2C2C",
                                    border_radius=2,
                                ),
                            ],
                        ),
                        ft.Container(
                            height=30,
                            border_radius=15,
                            bgcolor="#263238",
                            border=Border.all(1, "#37474F"),
                            padding=Padding.symmetric(horizontal=10, vertical=4),
                            alignment=ALIGN_CENTER,
                            ink=True,
                            on_click=lambda _, a=alerta: abrir_modal_concluir(a),
                            content=ft.Text(
                                "Concluir",
                                size=11,
                                weight=ft.FontWeight.W_600,
                                color="#64B5F6",
                            ),
                        ),
                    ],
                ),
            )

        # ---------------------------------------------------------------------
        # Conteúdo das 4 Abas da Bottom Navigation Bar
        # ---------------------------------------------------------------------
        def construir_aba_painel_home() -> ft.Control:
            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
                controls=[
                    ft.Column(
                        spacing=6,
                        controls=[
                            ft.Text(
                                "Escolhe veículo:",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color="#B0BEC5",
                            ),
                            carrossel_veiculos,
                        ],
                    ),
                    ft.Container(
                        bgcolor="#181818",
                        border_radius=10,
                        border=Border.all(1, "#252525"),
                        padding=Padding.symmetric(horizontal=10, vertical=8),
                        content=ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                            controls=[
                                ft.Icon(Icons.SPEED_ROUNDED, color="#64B5F6", size=20),
                                campo_km_atual,
                                icone_botao_km,
                                icone_botao_abastecer_rapido,
                            ],
                        ),
                    ),
                    ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Icon(
                                                Icons.WARNING_AMBER_ROUNDED,
                                                color="#FFCA28",
                                                size=18,
                                            ),
                                            ft.Text(
                                                "Alertas de Manutenção (Todos os Veículos)",
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color="#FFFFFF",
                                            ),
                                        ],
                                    ),
                                    contador_alertas_badge,
                                ],
                            ),
                            coluna_alertas_slim,
                        ],
                    ),
                ],
            )

        def construir_aba_historico() -> ft.Control:
            vid_filtro = (
                estado["veiculo_ativo_id"]
                if estado["filtro_historico_veiculo"]
                else None
            )
            registros = db.listar_historico(
                veiculo_id=vid_filtro, busca=estado["busca_historico"]
            )
            resumo_fin = db.obter_resumo_financeiro(veiculo_id=vid_filtro)

            def alternar_filtro(_: ft.ControlEvent) -> None:
                estado["filtro_historico_veiculo"] = not estado[
                    "filtro_historico_veiculo"
                ]
                atualizar_interface_home()

            def ao_buscar(e: ft.ControlEvent) -> None:
                estado["busca_historico"] = e.control.value or ""
                atualizar_interface_home()

            def remover_reg_historico(hid: int) -> None:
                db.excluir_historico(hid)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, "Registro removido do histórico.", "#263238")

            itens = []
            for reg in registros:
                eh_corretiva = reg.get("tipo_manutencao") == "corretiva"
                cor_icone = "#FFCA28" if eh_corretiva else "#66BB6A"
                icone_tipo = (
                    Icons.HANDYMAN_ROUNDED
                    if eh_corretiva
                    else Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                )
                valor_reg = float(reg.get("valor") or 0.0)
                oficina_reg = (reg.get("oficina") or "").strip()
                detalhe_sub = reg.get("observacoes") or "Manutenção concluída"
                if oficina_reg:
                    detalhe_sub = f"{oficina_reg} • {detalhe_sub}"

                itens.append(
                    ft.Container(
                        bgcolor="#1C1C1C",
                        border_radius=10,
                        border=Border.all(1, "#292929"),
                        padding=Padding.symmetric(horizontal=10, vertical=8),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    expand=True,
                                    controls=[
                                        ft.Icon(icone_tipo, color=cor_icone, size=18),
                                        ft.Column(
                                            spacing=2,
                                            expand=True,
                                            controls=[
                                                ft.Text(
                                                    f"{reg['veiculo_nome']} - {reg['item']}",
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#FFFFFF",
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Text(
                                                    detalhe_sub,
                                                    size=11,
                                                    color="#9E9E9E",
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=4,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Column(
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            spacing=1,
                                            controls=[
                                                ft.Text(
                                                    formatar_moeda(valor_reg)
                                                    if valor_reg > 0
                                                    else f"{reg['km_realizado']:,} km".replace(
                                                        ",", "."
                                                    ),
                                                    size=11,
                                                    weight=ft.FontWeight.W_600,
                                                    color="#66BB6A"
                                                    if valor_reg > 0
                                                    else "#64B5F6",
                                                ),
                                                ft.Text(
                                                    f"{reg['km_realizado']:,} km • {reg['data_realizada']}".replace(
                                                        ",", "."
                                                    )
                                                    if valor_reg > 0
                                                    else reg["data_realizada"],
                                                    size=10,
                                                    color="#757575",
                                                ),
                                            ],
                                        ),
                                        ft.IconButton(
                                            icon=Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=16,
                                            icon_color="#757575",
                                            tooltip="Excluir lançamento",
                                            on_click=lambda _, hid=reg["id"]: remover_reg_historico(
                                                hid
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

            if not itens:
                itens.append(
                    ft.Container(
                        padding=24,
                        alignment=ALIGN_CENTER,
                        content=ft.Text(
                            "Nenhuma manutenção encontrada para este filtro.",
                            color="#9E9E9E",
                            size=12,
                        ),
                    )
                )

            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Histórico & Custos",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                                color="#FFFFFF",
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Container(
                                        border_radius=14,
                                        bgcolor="#1B262D"
                                        if estado["filtro_historico_veiculo"]
                                        else "#222222",
                                        border=Border.all(
                                            1,
                                            "#64B5F6"
                                            if estado["filtro_historico_veiculo"]
                                            else "#333333",
                                        ),
                                        padding=Padding.symmetric(
                                            horizontal=10, vertical=5
                                        ),
                                        ink=True,
                                        on_click=alternar_filtro,
                                        content=ft.Text(
                                            "Só Veículo Ativo"
                                            if estado["filtro_historico_veiculo"]
                                            else "Todos Veículos",
                                            size=11,
                                            color="#64B5F6"
                                            if estado["filtro_historico_veiculo"]
                                            else "#B0BEC5",
                                        ),
                                    ),
                                    ElevatedButton(
                                        "+ Avulsa",
                                        bgcolor="#263238",
                                        color="#FFCA28",
                                        height=30,
                                        on_click=abrir_modal_manutencao_avulsa,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Resumo Financeiro Compacto
                    ft.Container(
                        bgcolor="#182026",
                        border_radius=10,
                        border=Border.all(1, "#263238"),
                        padding=Padding.symmetric(horizontal=12, vertical=8),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text(
                                            "Investido em Manutenção",
                                            size=10,
                                            color="#9E9E9E",
                                        ),
                                        ft.Text(
                                            formatar_moeda(
                                                resumo_fin["total_manutencao"]
                                            ),
                                            size=13,
                                            weight=ft.FontWeight.BOLD,
                                            color="#66BB6A",
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    spacing=1,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text(
                                            "Serviços Realizados",
                                            size=10,
                                            color="#9E9E9E",
                                        ),
                                        ft.Text(
                                            f"{resumo_fin['qtd_servicos']} registros",
                                            size=12,
                                            weight=ft.FontWeight.W_600,
                                            color="#64B5F6",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.TextField(
                        hint_text="Buscar peça, serviço ou oficina...",
                        value=estado["busca_historico"],
                        height=38,
                        text_size=12,
                        content_padding=Padding.symmetric(horizontal=12, vertical=6),
                        border_radius=8,
                        border_color="#2E2E2E",
                        bgcolor="#181818",
                        on_submit=ao_buscar,
                    ),
                    *itens,
                ],
            )

        def construir_aba_ficha_tecnica() -> ft.Control:
            veiculo = (
                db.obter_veiculo(estado["veiculo_ativo_id"])
                if estado["veiculo_ativo_id"]
                else None
            )
            if not veiculo:
                return ft.Text("Selecione um veículo primeiro.", color="#9E9E9E")

            preventivas = db.listar_preventivas_veiculo(veiculo["id"])
            cards_prev = []
            for p in preventivas:
                meses_info = (
                    f" ou {p['intervalo_meses']}m"
                    if p.get("intervalo_meses") and int(p["intervalo_meses"]) > 0
                    else ""
                )
                cards_prev.append(
                    ft.Container(
                        bgcolor="#1C1C1C",
                        border_radius=10,
                        border=Border.all(1, "#292929"),
                        padding=Padding.symmetric(horizontal=12, vertical=9),
                        content=ft.Column(
                            spacing=5,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
                                            expand=True,
                                            controls=[
                                                ft.Container(
                                                    width=8,
                                                    height=8,
                                                    border_radius=4,
                                                    bgcolor=p["cor"],
                                                ),
                                                ft.Text(
                                                    p["item"],
                                                    size=13,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#FFFFFF",
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                    expand=True,
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            p["texto_status"],
                                            size=11,
                                            color=p["cor"],
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ],
                                ),
                                ft.Text(
                                    f"Intervalo: {p['intervalo_km']:,} km{meses_info} • Última: {p['ultimo_km']:,} km".replace(
                                        ",", "."
                                    ),
                                    size=11,
                                    color="#9E9E9E",
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text(
                                            f"Espec.: {p.get('observacoes') or 'Padrão OEM'}",
                                            size=11,
                                            color="#64B5F6",
                                            expand=True,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=4,
                                            controls=[
                                                ft.Container(
                                                    border_radius=12,
                                                    bgcolor="#263238",
                                                    padding=Padding.symmetric(
                                                        horizontal=8, vertical=3
                                                    ),
                                                    ink=True,
                                                    tooltip="Dar baixa nesta preventiva agora",
                                                    on_click=lambda _, item_p=p: abrir_modal_concluir(
                                                        item_p
                                                    ),
                                                    content=ft.Text(
                                                        "Concluir",
                                                        size=10,
                                                        color="#64B5F6",
                                                        weight=ft.FontWeight.W_600,
                                                    ),
                                                ),
                                                ft.Container(
                                                    border_radius=12,
                                                    bgcolor="#222222",
                                                    padding=Padding.symmetric(
                                                        horizontal=7, vertical=3
                                                    ),
                                                    ink=True,
                                                    tooltip="Editar ou excluir item",
                                                    on_click=lambda _, item_p=p: abrir_modal_editar_preventiva(
                                                        item_p
                                                    ),
                                                    content=ft.Icon(
                                                        Icons.EDIT_OUTLINED,
                                                        size=13,
                                                        color="#B0BEC5",
                                                    ),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

            placa_str = f" • Placa {veiculo['placa']}" if veiculo.get("placa") else ""
            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=1,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        f"Ficha Técnica • {veiculo['nome']}",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color="#FFFFFF",
                                    ),
                                    ft.Text(
                                        f"Odômetro: {veiculo['km_atual']:,} km{placa_str}".replace(
                                            ",", "."
                                        ),
                                        size=11,
                                        color="#9E9E9E",
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ElevatedButton(
                                        "Dossiê",
                                        icon=Icons.SHARE_ROUNDED,
                                        bgcolor="#1C252B",
                                        color="#B0BEC5",
                                        height=32,
                                        on_click=lambda _: abrir_modal_dossie(veiculo),
                                    ),
                                    ElevatedButton(
                                        "+ Item",
                                        bgcolor="#263238",
                                        color="#64B5F6",
                                        height=32,
                                        on_click=lambda _: abrir_modal_nova_preventiva(
                                            veiculo
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    *cards_prev,
                ],
            )

        def construir_aba_abastecimento() -> ft.Control:
            veiculo = (
                db.obter_veiculo(estado["veiculo_ativo_id"])
                if estado["veiculo_ativo_id"]
                else None
            )
            if not veiculo:
                return ft.Text("Selecione um veículo primeiro.", color="#9E9E9E")

            resumo = db.obter_resumo_consumo(veiculo["id"])
            registros = db.listar_abastecimentos(veiculo["id"])

            def remover_abast(aid: int) -> None:
                db.excluir_abastecimento(aid)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, "Abastecimento removido.", "#263238")

            cards_abast = []
            for r in registros:
                media_txt = (
                    f"{r['km_por_litro']} km/L"
                    if r.get("km_por_litro", 0) > 0
                    else "1º registro / base"
                )
                cards_abast.append(
                    ft.Container(
                        bgcolor="#1C1C1C",
                        border_radius=10,
                        border=Border.all(1, "#292929"),
                        padding=Padding.symmetric(horizontal=12, vertical=8),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Icon(
                                            Icons.LOCAL_GAS_STATION_ROUNDED,
                                            color="#FFCA28",
                                            size=18,
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                ft.Text(
                                                    f"{r['combustivel']} • {r['litros']} L",
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#FFFFFF",
                                                ),
                                                ft.Text(
                                                    f"Odômetro: {r['km_atual']:,} km • {r['data_abastecimento']}".replace(
                                                        ",", "."
                                                    ),
                                                    size=10,
                                                    color="#9E9E9E",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=4,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Column(
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            spacing=1,
                                            controls=[
                                                ft.Text(
                                                    formatar_moeda(r["valor_total"]),
                                                    size=11,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#66BB6A",
                                                ),
                                                ft.Text(
                                                    media_txt,
                                                    size=10,
                                                    weight=ft.FontWeight.W_600,
                                                    color="#64B5F6",
                                                ),
                                            ],
                                        ),
                                        ft.IconButton(
                                            icon=Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=16,
                                            icon_color="#757575",
                                            on_click=lambda _, aid=r["id"]: remover_abast(
                                                aid
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

            if not cards_abast:
                cards_abast.append(
                    ft.Container(
                        padding=20,
                        alignment=ALIGN_CENTER,
                        content=ft.Text(
                            "Nenhum abastecimento registrado para este veículo.",
                            size=12,
                            color="#9E9E9E",
                        ),
                    )
                )

            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=1,
                                controls=[
                                    ft.Text(
                                        f"Consumo & Combustível • {veiculo['nome']}",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color="#FFFFFF",
                                    ),
                                    ft.Text(
                                        f"Total acumulado: {resumo['total_litros']} L ({formatar_moeda(resumo['total_gasto'])})",
                                        size=11,
                                        color="#9E9E9E",
                                    ),
                                ],
                            ),
                            ElevatedButton(
                                "+ Abastecer",
                                bgcolor="#263238",
                                color="#FFCA28",
                                height=32,
                                on_click=abrir_modal_abastecimento,
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor="#182026",
                        border_radius=10,
                        border=Border.all(1, "#263238"),
                        padding=Padding.symmetric(horizontal=12, vertical=10),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_AROUND,
                            controls=[
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            "Média Geral", size=10, color="#9E9E9E"
                                        ),
                                        ft.Text(
                                            f"{resumo['media_km_l']} km/L"
                                            if resumo["media_km_l"] > 0
                                            else "- km/L",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color="#64B5F6",
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            "Último Consumo", size=10, color="#9E9E9E"
                                        ),
                                        ft.Text(
                                            f"{resumo['ultimo_km_l']} km/L"
                                            if resumo["ultimo_km_l"] > 0
                                            else "- km/L",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color="#FFCA28",
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            "Preço Médio/L", size=10, color="#9E9E9E"
                                        ),
                                        ft.Text(
                                            formatar_moeda(resumo["preco_medio_litro"]),
                                            size=13,
                                            weight=ft.FontWeight.BOLD,
                                            color="#66BB6A",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    *cards_abast,
                ],
            )

        # ---------------------------------------------------------------------
        # Atualização Completa da Tela Home
        # ---------------------------------------------------------------------
        def atualizar_interface_home() -> None:
            veiculos = db.listar_veiculos()
            if veiculos and not any(
                v["id"] == estado["veiculo_ativo_id"] for v in veiculos
            ):
                estado["veiculo_ativo_id"] = veiculos[0]["id"]

            carrossel_veiculos.controls.clear()
            veiculo_selecionado = None
            for v in veiculos:
                ativo = v["id"] == estado["veiculo_ativo_id"]
                if ativo:
                    veiculo_selecionado = v
                carrossel_veiculos.controls.append(criar_card_veiculo(v, ativo))
            carrossel_veiculos.controls.append(criar_card_adicionar_veiculo())

            if veiculo_selecionado:
                campo_km_atual.value = str(veiculo_selecionado["km_atual"])
                campo_km_atual.label = f"KM Atual ({veiculo_selecionado['nome']})"

            alertas = db.listar_alertas_globais()
            contador_alertas_badge.content.value = str(len(alertas))
            contador_alertas_badge.bgcolor = (
                "#EF5350"
                if any(a["status"] == "vencido" for a in alertas)
                else "#263238"
            )

            coluna_alertas_slim.controls.clear()
            if alertas:
                for alerta in alertas:
                    coluna_alertas_slim.controls.append(criar_card_alerta_slim(alerta))
            else:
                coluna_alertas_slim.controls.append(
                    ft.Container(
                        bgcolor="#18221A",
                        border_radius=10,
                        border=Border.all(1, "#2E7D32"),
                        padding=12,
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(
                                    Icons.VERIFIED_ROUNDED, color="#66BB6A", size=18
                                ),
                                ft.Text(
                                    "Todas as manutenções de todos os veículos estão em dia!",
                                    size=12,
                                    color="#A5D6A7",
                                ),
                            ],
                        ),
                    )
                )

            if estado["aba_atual"] == 0:
                container_corpo_principal.content = construir_aba_painel_home()
            elif estado["aba_atual"] == 1:
                container_corpo_principal.content = construir_aba_historico()
            elif estado["aba_atual"] == 2:
                container_corpo_principal.content = construir_aba_ficha_tecnica()
            else:
                container_corpo_principal.content = construir_aba_abastecimento()

            page.update()

        def abrir_modal_conta_google(_: ft.ControlEvent = None) -> None:
            usr = estado["usuario"]

            def acao_sincronizar(_: ft.ControlEvent) -> None:
                ok, msg = auth_google.sincronizar_backup_drive(db.DB_PATH)
                fechar_modal(page, modal_conta)
                mostrar_snackbar(page, msg, "#2E7D32" if ok else "#EF5350")

            def acao_restaurar(_: ft.ControlEvent) -> None:
                ok, msg = auth_google.restaurar_backup_drive(db.DB_PATH)
                fechar_modal(page, modal_conta)
                if ok:
                    db.init_db()
                    veiculos = db.listar_veiculos()
                    estado["veiculo_ativo_id"] = veiculos[0]["id"] if veiculos else None
                    atualizar_interface_home()
                mostrar_snackbar(page, msg, "#2E7D32" if ok else "#EF5350")

            def acao_logout(_: ft.ControlEvent) -> None:
                auth_google.fazer_logout()
                estado["usuario"] = {
                    "nome": "Motorista Google",
                    "email": "motorista@gmail.com",
                    "foto": "",
                    "logado": False,
                }
                fechar_modal(page, modal_conta)
                navegar("/login")

            modal_conta = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(
                            Icons.ACCOUNT_CIRCLE_ROUNDED, color="#64B5F6", size=24
                        ),
                        ft.Text(
                            "Sua Conta Google & Backup",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            usr.get("nome") or "Motorista Google",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color="#FFFFFF",
                        ),
                        ft.Text(
                            usr.get("email") or "",
                            size=12,
                            color="#9E9E9E",
                        ),
                        ft.Container(
                            bgcolor="#161E24",
                            border_radius=8,
                            border=Border.all(1, "#263238"),
                            padding=Padding.all(10),
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Icon(
                                                Icons.CLOUD_DONE_OUTLINED,
                                                color="#64B5F6",
                                                size=16,
                                            ),
                                            ft.Text(
                                                "Pasta no seu Drive: Garagem App - Backup",
                                                size=11,
                                                weight=ft.FontWeight.W_600,
                                                color="#64B5F6",
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        auth_google.ultimo_status_backup,
                                        size=11,
                                        color="#B0BEC5",
                                    ),
                                ],
                            ),
                        ),
                        ElevatedButton(
                            "Salvar Backup Agora no meu Google Drive",
                            icon=Icons.CLOUD_UPLOAD_OUTLINED,
                            bgcolor="#263238",
                            color="#64B5F6",
                            on_click=acao_sincronizar,
                        ),
                        ElevatedButton(
                            "Restaurar Backup do meu Google Drive",
                            icon=Icons.CLOUD_DOWNLOAD_OUTLINED,
                            bgcolor="#1C252B",
                            color="#B0BEC5",
                            on_click=acao_restaurar,
                        ),
                    ],
                ),
                actions=[
                    ft.TextButton(
                        "Fechar", on_click=lambda _: fechar_modal(page, modal_conta)
                    ),
                    ElevatedButton(
                        "Trocar Conta / Sair",
                        bgcolor="#EF5350",
                        color="#FFFFFF",
                        on_click=acao_logout,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            abrir_modal(page, modal_conta)

        foto_usuario = estado["usuario"].get("foto") or ""
        avatar_google = ft.CircleAvatar(
            radius=17,
            bgcolor="#263238",
            foreground_image_src=foto_usuario if foto_usuario else None,
            content=ft.Stack(
                controls=[
                    ft.Container(
                        alignment=ALIGN_CENTER,
                        content=ft.Icon(
                            Icons.ACCOUNT_CIRCLE_ROUNDED,
                            color="#64B5F6",
                            size=30,
                        ),
                    ),
                    ft.Container(
                        right=0,
                        bottom=0,
                        width=10,
                        height=10,
                        border_radius=5,
                        bgcolor="#66BB6A",
                        border=Border.all(1.5, "#121212"),
                    ),
                ]
            ),
        )

        header_home = ft.Container(
            bgcolor="#161616",
            padding=Padding.symmetric(horizontal=16, vertical=12),
            border=Border.only(bottom=ft.BorderSide(1, "#242424")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Image(
                                src=ICON_PNG_PATH,
                                width=36,
                                height=36,
                                border_radius=8,
                            ),
                            ft.Text(
                                "Garagem",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color="#FFFFFF",
                            ),
                        ],
                    ),
                    ft.Container(
                        on_click=abrir_modal_conta_google,
                        tooltip=f"{estado['usuario'].get('nome')} ({estado['usuario'].get('email')})",
                        border_radius=20,
                        ink=True,
                        content=avatar_google,
                    ),
                ],
            ),
        )

        def ao_mudar_aba(e: ft.ControlEvent) -> None:
            estado["aba_atual"] = e.control.selected_index
            atualizar_interface_home()

        DestinoNav = getattr(
            ft, "NavigationBarDestination", getattr(ft, "NavigationDestination", None)
        )
        barra_navegacao = ft.NavigationBar(
            selected_index=estado["aba_atual"],
            bgcolor="#181818",
            indicator_color="#263238",
            height=64,
            on_change=ao_mudar_aba,
            destinations=[
                DestinoNav(
                    icon=Icons.HOME_OUTLINED,
                    selected_icon=Icons.HOME_ROUNDED,
                    label="Home",
                ),
                DestinoNav(
                    icon=Icons.HISTORY_OUTLINED,
                    selected_icon=Icons.HISTORY_ROUNDED,
                    label="Histórico",
                ),
                DestinoNav(
                    icon=Icons.ASSIGNMENT_OUTLINED,
                    selected_icon=Icons.ASSIGNMENT_ROUNDED,
                    label="Ficha Técnica",
                ),
                DestinoNav(
                    icon=Icons.LOCAL_GAS_STATION_OUTLINED,
                    selected_icon=Icons.LOCAL_GAS_STATION_ROUNDED,
                    label="Abastecer",
                ),
            ],
        )

        atualizar_interface_home()

        return ft.View(
            route="/home",
            bgcolor="#121212",
            padding=0,
            navigation_bar=barra_navegacao,
            controls=[
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        header_home,
                        ft.Container(
                            expand=True,
                            padding=Padding.symmetric(horizontal=16, vertical=12),
                            content=container_corpo_principal,
                        ),
                    ],
                )
            ],
        )

    # =========================================================================
    # ROTEAMENTO (page.on_route_change)
    # =========================================================================
    def route_change(e: ft.RouteChangeEvent = None) -> None:
        page.views.clear()
        if page.route == "/home":
            page.views.append(construir_view_home())
        else:
            page.views.append(construir_view_login())
        page.update()

    def navegar(rota: str) -> None:
        page.route = rota
        if hasattr(page, "go"):
            page.go(rota)
        else:
            route_change()

    def view_pop(e: ft.ViewPopEvent = None) -> None:
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            navegar(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    navegar("/login")


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=ASSETS_DIR)
    else:
        ft.app(target=main, assets_dir=ASSETS_DIR)
