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
ALIGN_CENTER = getattr(ft.Alignment, "CENTER", None) if hasattr(ft, "Alignment") else getattr(ft.alignment, "center", None)


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
    # Inicializa SQLite com tabelas e dados de exemplo (Civic LXS 1.8 e Yamaha MT-03)
    db.init_db()

    # Configurações Globais da Página (Mobile Frame + Material Design 3 + Dark #121212)
    page.title = "Garagem"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#121212"
    page.padding = 0
    page.window.width = 410
    page.window.height = 820
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
        "aba_atual": 0,  # 0 = Home, 1 = Histórico, 2 = Ficha Técnica
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

                # Verifica se a pessoa já tem um backup salvo no próprio Google Drive dela
                restaurado, msg_sync = auth_google.restaurar_backup_drive(db.DB_PATH)
                if not restaurado:
                    # Primeiro acesso da pessoa: cria a pasta 'Garagem App - Backup' no Drive dela
                    auth_google.sincronizar_backup_drive(db.DB_PATH)
                else:
                    veiculos = db.listar_veiculos()
                    estado["veiculo_ativo_id"] = veiculos[0]["id"] if veiculos else None

                navegar("/home")
                resumo_drive = "Backup restaurado do seu Drive!" if restaurado else "Backup ativo no seu Google Drive!"
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
                        "'credentials.json' (OAuth Desktop App) na pasta do projeto ou cole "
                        "suas credenciais do Google Cloud Console abaixo:",
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
        # Ícone principal oficial do sistema (Garagem App)
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

        # Ícone estilizado do Google para o botão pílula
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

        # Botão principal arredondado (estilo pílula, fundo #263238, altura 50)
        botao_google = ElevatedButton(
            height=50,
            width=270,
            on_click=login_google,
            style=ft.ButtonStyle(
                bgcolor="#263238",
                color="#FFFFFF",
                elevation=2,
                shape=ft. StadiumBorder(),
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

        # Conteúdo centralizado vertical e horizontalmente
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

        # Rodapé fixo na parte inferior
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
    # ROTA 2: /home (Painel, Seletor de Veículos, KM Rápido e Alertas Slim)
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

        coluna_alertas_slim = ft.Column(spacing=6)
        contador_alertas_badge = ft.Container(
            padding=Padding.symmetric(horizontal=8, vertical=2),
            border_radius=10,
            bgcolor="#263238",
            content=ft.Text("0", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        )

        container_corpo_principal = ft.Container(expand=True)

        # ---------------------------------------------------------------------
        # Funções Auxiliares e Modais da Home
        # ---------------------------------------------------------------------
        def icone_por_tipo(tipo: str) -> str:
            return Icons.TWO_WHEELER_ROUNDED if tipo == "moto" else Icons.DIRECTIONS_CAR_FILLED_ROUNDED

        def selecionar_veiculo(veiculo_id: int) -> None:
            estado["veiculo_ativo_id"] = veiculo_id
            atualizar_interface_home()

        def salvar_km_rapido(e: ft.ControlEvent = None) -> None:
            veiculo_id = estado["veiculo_ativo_id"]
            if not veiculo_id:
                return
            valor_limpo = (campo_km_atual.value or "").replace(".", "").replace(",", "").strip()
            if not valor_limpo.isdigit():
                mostrar_snackbar(page, "Informe um valor numérico válido para o KM.", "#EF5350")
                return

            novo_km = int(valor_limpo)
            db.atualizar_km_veiculo(veiculo_id, novo_km)
            atualizar_interface_home()
            auth_google.agendar_backup_automatico(db.DB_PATH)
            mostrar_snackbar(page, f"Odômetro atualizado para {novo_km:,} km!".replace(",", "."), "#2E7D32")

        campo_km_atual.on_submit = salvar_km_rapido
        icone_botao_km.on_click = salvar_km_rapido

        # Modal: + Adicionar Novo Veículo
        def abrir_modal_novo_veiculo(e: ft.ControlEvent) -> None:
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
            tf_placa = ft.TextField(
                label="Placa (opcional)",
                border_color="#37474F",
            )

            def confirmar_cadastro(ev: ft.ControlEvent) -> None:
                nome = (tf_nome.value or "").strip()
                km_str = (tf_km.value or "0").replace(".", "").strip()
                if not nome:
                    mostrar_snackbar(page, "Digite o nome do veículo.", "#EF5350")
                    return
                km_val = int(km_str) if km_str.isdigit() else 0
                novo_id = db.adicionar_veiculo(
                    nome=nome,
                    tipo=dd_tipo.value or "carro",
                    km_atual=km_val,
                    placa=(tf_placa.value or "").strip().upper(),
                )
                estado["veiculo_ativo_id"] = novo_id
                fechar_modal(page, modal_veiculo)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, f"Veículo '{nome}' adicionado com sucesso!", "#2E7D32")

            modal_veiculo = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Text("Novo Veículo", size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[tf_nome, dd_tipo, tf_km, tf_placa],
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

        # Modal: Concluir Manutenção (Dar Baixa Rápida)
        def abrir_modal_concluir(alerta: dict) -> None:
            tf_km_baixa = ft.TextField(
                label="KM em que foi realizada",
                value=str(alerta["veiculo_km_atual"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
                focused_border_color="#64B5F6",
            )
            tf_obs = ft.TextField(
                label="Observações / Peças utilizadas (opcional)",
                value=alerta.get("observacoes") or "",
                border_color="#37474F",
            )

            def confirmar_baixa(ev: ft.ControlEvent) -> None:
                km_str = (tf_km_baixa.value or "").replace(".", "").strip()
                if not km_str.isdigit():
                    mostrar_snackbar(page, "Informe um KM válido.", "#EF5350")
                    return
                km_realizado = int(km_str)
                db.concluir_preventiva(
                    preventiva_id=alerta["id"],
                    km_realizado=km_realizado,
                    observacoes=tf_obs.value or "",
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
                        ft.Text(
                            f"Intervalo configurado: a cada {alerta['intervalo_km']:,} km".replace(",", "."),
                            size=11,
                            color="#9E9E9E",
                        ),
                        tf_km_baixa,
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

        # Modal: Nova Preventiva (para a aba Ficha Técnica)
        def abrir_modal_nova_preventiva(veiculo: dict) -> None:
            tf_item = ft.TextField(
                label="Item (ex: Correia Dentada, Velas)",
                autofocus=True,
                border_color="#37474F",
            )
            tf_intervalo = ft.TextField(
                label="Intervalo de troca (KM)",
                value="10000",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#37474F",
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

            def salvar_item(ev: ft.ControlEvent) -> None:
                nome_item = (tf_item.value or "").strip()
                int_str = (tf_intervalo.value or "").replace(".", "").strip()
                ult_str = (tf_ultimo_km.value or "").replace(".", "").strip()
                if not nome_item or not int_str.isdigit() or not ult_str.isdigit():
                    mostrar_snackbar(page, "Preencha corretamente o item e as quilometragens.", "#EF5350")
                    return
                db.adicionar_preventiva(
                    veiculo_id=veiculo["id"],
                    item=nome_item,
                    intervalo_km=max(100, int(int_str)),
                    ultimo_km=int(ult_str),
                    observacoes=tf_obs.value or "",
                )
                fechar_modal(page, modal_prev)
                atualizar_interface_home()
                auth_google.agendar_backup_automatico(db.DB_PATH)
                mostrar_snackbar(page, f"Item '{nome_item}' adicionado ao plano!", "#2E7D32")

            modal_prev = ft.AlertDialog(
                modal=True,
                bgcolor="#1E1E1E",
                title=ft.Text(f"Novo Item • {veiculo['nome']}", size=16, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[tf_item, tf_intervalo, tf_ultimo_km, tf_obs],
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: fechar_modal(page, modal_prev)),
                    ElevatedButton(
                        "Adicionar",
                        bgcolor="#64B5F6",
                        color="#121212",
                        on_click=salvar_item,
                    ),
                ],
            )
            abrir_modal(page, modal_prev)

        # ---------------------------------------------------------------------
        # Construção dos Cards do Carrossel e Cards Slim de Alertas
        # ---------------------------------------------------------------------
        def criar_card_veiculo(veiculo: dict, ativo: bool) -> ft.Container:
            cor_borda = "#64B5F6" if ativo else "#2A2A2A"
            espessura_borda = 2.0 if ativo else 1.0
            cor_fundo = "#1B262D" if ativo else "#1C1C1C"
            cor_icone = "#64B5F6" if ativo else "#9E9E9E"

            return ft.Container(
                width=105,
                height=100,
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
                            controls=[
                                ft.Icon(icone_por_tipo(veiculo["tipo"]), color=cor_icone, size=24),
                                ft.Container(
                                    width=8,
                                    height=8,
                                    border_radius=4,
                                    bgcolor="#64B5F6" if ativo else "transparent",
                                ),
                            ],
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(
                                    veiculo["nome"],
                                    size=12,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
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
            """
            Card quadrado pontilhado '+ Adicionar novo veículo' posicionado
            sempre como último item à direita da fila.
            """
            # Simulação visual de borda pontilhada/tracejada limpa em Material 3
            return ft.Container(
                width=105,
                height=100,
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
                            ft.Icon(Icons.ADD_CIRCLE_OUTLINE_ROUNDED, color="#64B5F6", size=22),
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
            """
            Card compacto ('slim', altura reduzida, pouca margem interna) contendo:
            - Bolinha de cor do status (#EF5350 vencido ou #FFCA28 últimos 15%)
            - Ícone/nome do veículo + item (ex: 'Yamaha MT-03 - Lubrificar Relação')
            - Texto curto do status (ex: 'Vencido há 50 km' + barra de progresso fina)
            - Botão compacto 'Concluir' à direita que abre um modal rápido para dar baixa
            """
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
                        # Bolinha de cor do status
                        ft.Container(
                            width=10,
                            height=10,
                            border_radius=5,
                            bgcolor=cor_status,
                            tooltip="Vencido" if alerta["status"] == "vencido" else "Próximo de vencer (≤15%)",
                        ),
                        # Ícone + Nome do veículo + Item + Status curto + Barra de progresso fina
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
                                            f"Meta: {alerta['proximo_km']:,} km".replace(",", "."),
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
                        # Botão compacto "Concluir" à direita
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
        # Conteúdo das 3 Abas da Bottom Navigation Bar
        # ---------------------------------------------------------------------
        def construir_aba_painel_home() -> ft.Control:
            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
                controls=[
                    # Seletor de Veículos (Carrossel Horizontal)
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
                    # Atualização Rápida de KM
                    ft.Container(
                        bgcolor="#181818",
                        border_radius=10,
                        border=Border.all(1, "#252525"),
                        padding=Padding.symmetric(horizontal=10, vertical=8),
                        content=ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                            controls=[
                                ft.Icon(Icons.SPEED_ROUNDED, color="#64B5F6", size=20),
                                campo_km_atual,
                                icone_botao_km,
                            ],
                        ),
                    ),
                    # Central de Alertas Global (Estilo Slim)
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
            registros = db.listar_historico()
            itens = []
            for reg in registros:
                itens.append(
                    ft.Container(
                        bgcolor="#1C1C1C",
                        border_radius=10,
                        border=Border.all(1, "#292929"),
                        padding=Padding.symmetric(horizontal=12, vertical=9),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Icon(
                                            Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                            color="#66BB6A",
                                            size=18,
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                ft.Text(
                                                    f"{reg['veiculo_nome']} - {reg['item']}",
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#FFFFFF",
                                                ),
                                                ft.Text(
                                                    reg.get("observacoes") or "Manutenção concluída",
                                                    size=11,
                                                    color="#9E9E9E",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            f"{reg['km_realizado']:,} km".replace(",", "."),
                                            size=11,
                                            weight=ft.FontWeight.W_600,
                                            color="#64B5F6",
                                        ),
                                        ft.Text(
                                            reg["data_realizada"],
                                            size=10,
                                            color="#757575",
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
                        content=ft.Text("Nenhuma manutenção concluída ainda.", color="#9E9E9E", size=12),
                    )
                )

            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=8,
                controls=[
                    ft.Text(
                        "Histórico de Manutenções Realizadas",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color="#FFFFFF",
                    ),
                    *itens,
                ],
            )

        def construir_aba_ficha_tecnica() -> ft.Control:
            veiculo = db.obter_veiculo(estado["veiculo_ativo_id"]) if estado["veiculo_ativo_id"] else None
            if not veiculo:
                return ft.Text("Selecione um veículo primeiro.", color="#9E9E9E")

            preventivas = db.listar_preventivas_veiculo(veiculo["id"])
            cards_prev = []
            for p in preventivas:
                cards_prev.append(
                    ft.Container(
                        bgcolor="#1C1C1C",
                        border_radius=10,
                        border=Border.all(1, "#292929"),
                        padding=Padding.symmetric(horizontal=12, vertical=9),
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
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
                                    f"Intervalo: a cada {p['intervalo_km']:,} km • Última troca: {p['ultimo_km']:,} km".replace(
                                        ",", "."
                                    ),
                                    size=11,
                                    color="#9E9E9E",
                                ),
                                ft.Text(
                                    f"Especificação: {p.get('observacoes') or 'Padrão OEM'}",
                                    size=11,
                                    color="#64B5F6",
                                ),
                            ],
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
                                        f"Ficha Técnica • {veiculo['nome']}",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color="#FFFFFF",
                                    ),
                                    ft.Text(
                                        f"Odômetro atual: {veiculo['km_atual']:,} km".replace(",", "."),
                                        size=11,
                                        color="#9E9E9E",
                                    ),
                                ],
                            ),
                            ElevatedButton(
                                "+ Item",
                                bgcolor="#263238",
                                color="#64B5F6",
                                height=32,
                                on_click=lambda _: abrir_modal_nova_preventiva(veiculo),
                            ),
                        ],
                    ),
                    *cards_prev,
                ],
            )

        # ---------------------------------------------------------------------
        # Atualização Completa da Tela Home
        # ---------------------------------------------------------------------
        def atualizar_interface_home() -> None:
            veiculos = db.listar_veiculos()
            if veiculos and not any(v["id"] == estado["veiculo_ativo_id"] for v in veiculos):
                estado["veiculo_ativo_id"] = veiculos[0]["id"]

            # 1. Atualiza Carrossel de Veículos + Card Pontilhado à direita
            carrossel_veiculos.controls.clear()
            veiculo_selecionado = None
            for v in veiculos:
                ativo = v["id"] == estado["veiculo_ativo_id"]
                if ativo:
                    veiculo_selecionado = v
                carrossel_veiculos.controls.append(criar_card_veiculo(v, ativo))
            carrossel_veiculos.controls.append(criar_card_adicionar_veiculo())

            # 2. Atualiza KM Atual do veículo selecionado
            if veiculo_selecionado:
                campo_km_atual.value = str(veiculo_selecionado["km_atual"])
                campo_km_atual.label = f"KM Atual ({veiculo_selecionado['nome']})"

            # 3. Atualiza Central de Alertas Global (Todos os Veículos)
            alertas = db.listar_alertas_globais()
            contador_alertas_badge.content.value = str(len(alertas))
            contador_alertas_badge.bgcolor = "#EF5350" if any(a["status"] == "vencido" for a in alertas) else "#263238"

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
                                ft.Icon(Icons.VERIFIED_ROUNDED, color="#66BB6A", size=18),
                                ft.Text(
                                    "Todas as manutenções de todos os veículos estão em dia!",
                                    size=12,
                                    color="#A5D6A7",
                                ),
                            ],
                        ),
                    )
                )

            # 4. Renderiza a aba ativa
            if estado["aba_atual"] == 0:
                container_corpo_principal.content = construir_aba_painel_home()
            elif estado["aba_atual"] == 1:
                container_corpo_principal.content = construir_aba_historico()
            else:
                container_corpo_principal.content = construir_aba_ficha_tecnica()

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
                        ft.Icon(Icons.ACCOUNT_CIRCLE_ROUNDED, color="#64B5F6", size=24),
                        ft.Text("Sua Conta Google & Backup", size=16, weight=ft.FontWeight.BOLD),
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
                                            ft.Icon(Icons.CLOUD_DONE_OUTLINED, color="#64B5F6", size=16),
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
                    ft.TextButton("Fechar", on_click=lambda _: fechar_modal(page, modal_conta)),
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

        # Header Superior: Título "Garagem" + Ícone à esquerda | Avatar Google à direita
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
                    # Avatar / Ícone da conta Google logada à direita
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

        # Bottom Navigation Bar fixa com 3 abas: "Home", "Histórico" e "Ficha Técnica"
        def ao_mudar_aba(e: ft.ControlEvent) -> None:
            estado["aba_atual"] = e.control.selected_index
            atualizar_interface_home()

        DestinoNav = getattr(ft, "NavigationBarDestination", getattr(ft, "NavigationDestination", None))
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
            ],
        )

        # Popula os dados antes de retornar a View
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

    # Inicia na rota /login conforme solicitado no Prompt 1
    navegar("/login")


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=ASSETS_DIR)
    else:
        ft.app(target=main, assets_dir=ASSETS_DIR)
