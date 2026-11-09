import os
import sqlite3
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "garagem.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _colunas_tabela(cursor: sqlite3.Cursor, tabela: str) -> List[str]:
    rows = cursor.execute(f"PRAGMA table_info({tabela})").fetchall()
    return [r["name"] for r in rows]


def init_db() -> None:
    """
    Inicializa as tabelas veiculos, preventivas, historico e abastecimentos,
    executando migrações automáticas sem perda de dados existentes.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS veiculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'carro',
                km_atual INTEGER NOT NULL DEFAULT 0,
                ano INTEGER,
                placa TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS preventivas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veiculo_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                intervalo_km INTEGER NOT NULL,
                ultimo_km INTEGER NOT NULL,
                ultima_data TEXT,
                observacoes TEXT,
                intervalo_meses INTEGER DEFAULT 0,
                FOREIGN KEY (veiculo_id) REFERENCES veiculos (id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veiculo_id INTEGER NOT NULL,
                preventiva_id INTEGER,
                item TEXT NOT NULL,
                km_realizado INTEGER NOT NULL,
                data_realizada TEXT NOT NULL,
                observacoes TEXT,
                valor REAL DEFAULT 0.0,
                oficina TEXT DEFAULT '',
                tipo_manutencao TEXT DEFAULT 'preventiva',
                FOREIGN KEY (veiculo_id) REFERENCES veiculos (id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS abastecimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veiculo_id INTEGER NOT NULL,
                km_atual INTEGER NOT NULL,
                litros REAL NOT NULL,
                valor_total REAL NOT NULL,
                combustivel TEXT NOT NULL DEFAULT 'Gasolina',
                km_por_litro REAL DEFAULT 0.0,
                data_abastecimento TEXT NOT NULL,
                FOREIGN KEY (veiculo_id) REFERENCES veiculos (id) ON DELETE CASCADE
            )
            """
        )

        # Migrações automáticas para bancos já criados anteriormente
        cols_prev = _colunas_tabela(cursor, "preventivas")
        if "intervalo_meses" not in cols_prev:
            cursor.execute("ALTER TABLE preventivas ADD COLUMN intervalo_meses INTEGER DEFAULT 0")

        cols_hist = _colunas_tabela(cursor, "historico")
        if "valor" not in cols_hist:
            cursor.execute("ALTER TABLE historico ADD COLUMN valor REAL DEFAULT 0.0")
        if "oficina" not in cols_hist:
            cursor.execute("ALTER TABLE historico ADD COLUMN oficina TEXT DEFAULT ''")
        if "tipo_manutencao" not in cols_hist:
            cursor.execute(
                "ALTER TABLE historico ADD COLUMN tipo_manutencao TEXT DEFAULT 'preventiva'"
            )

        # Verifica se já existem veículos cadastrados
        cursor.execute("SELECT COUNT(*) as total FROM veiculos")
        if cursor.fetchone()["total"] == 0:
            _seed_initial_data(cursor)

        conn.commit()


def _seed_initial_data(cursor: sqlite3.Cursor) -> None:
    # 1. Civic LXS 1.8
    cursor.execute(
        """
        INSERT INTO veiculos (nome, tipo, km_atual, ano, placa)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Civic LXS 1.8", "carro", 84500, 2011, "HND-1800"),
    )
    civic_id = cursor.lastrowid

    # 2. Yamaha MT-03
    cursor.execute(
        """
        INSERT INTO veiculos (nome, tipo, km_atual, ano, placa)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Yamaha MT-03", "moto", 18250, 2022, "YMH-0321"),
    )
    mt03_id = cursor.lastrowid

    preventivas_seed = [
        # Yamaha MT-03 (KM atual: 18250)
        (mt03_id, "Lubrificar Relação", 500, 17700, "2026-10-25", "Spray Motul C4 Chain Lube", 1),
        (mt03_id, "Troca de Óleo e Filtro", 5000, 13600, "2026-06-15", "Yamalube 10W40 Semissintético", 6),
        (mt03_id, "Fluido de Freio DOT 4", 10000, 15000, "2026-07-10", "Verificar nível e coloração", 12),
        # Civic LXS 1.8 (KM atual: 84500)
        (civic_id, "Filtro de Ar do Motor", 15000, 69200, "2025-12-10", "Elemento filtrante OEM", 12),
        (civic_id, "Óleo do Motor 5W30 + Filtro", 10000, 75500, "2026-04-20", "Óleo 100% Sintético API SP", 6),
        (civic_id, "Fluido de Transmissão ATF", 40000, 60000, "2025-05-01", "Honda ATF DW-1", 24),
    ]

    cursor.executemany(
        """
        INSERT INTO preventivas (
            veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes, intervalo_meses
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        preventivas_seed,
    )

    historico_seed = [
        (
            mt03_id,
            1,
            "Lubrificar Relação",
            17700,
            "25/10/2026",
            "Limpeza com querosene e aplicação C4",
            45.0,
            "Garagem Casa",
            "preventiva",
        ),
        (
            civic_id,
            5,
            "Óleo do Motor 5W30 + Filtro",
            75500,
            "20/04/2026",
            "Troca preventiva no prazo (4L 5W30 + Filtro OEM)",
            320.0,
            "Auto Center Nippon",
            "preventiva",
        ),
    ]
    cursor.executemany(
        """
        INSERT INTO historico (
            veiculo_id, preventiva_id, item, km_realizado, data_realizada,
            observacoes, valor, oficina, tipo_manutencao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        historico_seed,
    )


# =============================================================================
# GESTÃO DE VEÍCULOS (CRUD COMPLETO)
# =============================================================================
def listar_veiculos() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM veiculos ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def obter_veiculo(veiculo_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()
        return dict(row) if row else None


def adicionar_veiculo(
    nome: str,
    tipo: str = "carro",
    km_atual: int = 0,
    ano: Optional[int] = None,
    placa: Optional[str] = None,
    criar_preventivas_padrao: bool = True,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO veiculos (nome, tipo, km_atual, ano, placa)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nome.strip(), tipo, km_atual, ano, (placa or "").strip().upper()),
        )
        veiculo_id = cursor.lastrowid
        if criar_preventivas_padrao:
            hoje = datetime.now().strftime("%Y-%m-%d")
            if tipo == "moto":
                padroes = [
                    (veiculo_id, "Lubrificar Relação", 500, km_atual, hoje, "Spray Chain Lube", 1),
                    (veiculo_id, "Troca de Óleo e Filtro", 5000, km_atual, hoje, "10W40 Semissintético", 6),
                    (veiculo_id, "Fluido de Freio DOT 4", 10000, km_atual, hoje, "Sangria completa", 12),
                    (veiculo_id, "Filtro de Ar e Vela", 15000, km_atual, hoje, "Inspeção e troca", 18),
                ]
            else:
                padroes = [
                    (veiculo_id, "Óleo do Motor + Filtro", 10000, km_atual, hoje, "Sintético recomendado OEM", 6),
                    (veiculo_id, "Filtro de Ar e Combustível", 15000, km_atual, hoje, "Substituição preventiva", 12),
                    (veiculo_id, "Alinhamento e Rodízio de Pneus", 10000, km_atual, hoje, "Balanceamento das 4 rodas", 6),
                    (veiculo_id, "Fluido de Freio DOT 4", 20000, km_atual, hoje, "Troca completa no reservatório", 12),
                    (veiculo_id, "Líquido de Arrefecimento", 30000, km_atual, hoje, "Aditivo orgânico na proporção OEM", 24),
                ]
            cursor.executemany(
                """
                INSERT INTO preventivas (
                    veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes, intervalo_meses
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                padroes,
            )
        conn.commit()
        return veiculo_id


def editar_veiculo(
    veiculo_id: int,
    nome: str,
    tipo: str,
    km_atual: int,
    ano: Optional[int] = None,
    placa: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE veiculos
            SET nome = ?, tipo = ?, km_atual = ?, ano = ?, placa = ?
            WHERE id = ?
            """,
            (nome.strip(), tipo, km_atual, ano, placa.strip().upper(), veiculo_id),
        )
        conn.commit()


def excluir_veiculo(veiculo_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM veiculos WHERE id = ?", (veiculo_id,))
        conn.commit()


def atualizar_km_veiculo(veiculo_id: int, novo_km: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE veiculos SET km_atual = ? WHERE id = ?",
            (novo_km, veiculo_id),
        )
        conn.commit()


# =============================================================================
# CÁLCULO HÍBRIDO DE PREVENTIVAS (KM + TEMPO EM MESES)
# =============================================================================
def calcular_status_preventiva(
    km_atual: int,
    ultimo_km: int,
    intervalo_km: int,
    ultima_data: Optional[str] = None,
    intervalo_meses: Optional[int] = 0,
) -> Dict[str, Any]:
    """
    Calcula o status da manutenção preventiva considerando:
    1. Quilometragem (KM restante vs intervalo_km)
    2. Tempo decorrido (dias desde ultima_data vs intervalo_meses * 30), caso intervalo_meses > 0
    Prevalece o critério que estiver mais próximo do vencimento.
    """
    proximo_km = ultimo_km + intervalo_km
    km_rodado = max(0, km_atual - ultimo_km)
    km_restante = proximo_km - km_atual
    progresso_km = min(1.0, max(0.0, km_rodado / intervalo_km)) if intervalo_km > 0 else 1.0
    limite_alerta_km = intervalo_km * 0.15

    # Cálculo opcional por tempo (meses)
    dias_restantes: Optional[int] = None
    progresso_tempo: float = 0.0
    venceu_por_tempo = False
    alerta_por_tempo = False
    info_tempo_curta = ""

    meses_cfg = int(intervalo_meses or 0)
    if meses_cfg > 0 and ultima_data:
        try:
            dt_ult = datetime.strptime(ultima_data[:10], "%Y-%m-%d")
            dias_totais = max(1, meses_cfg * 30)
            dias_passados = max(0, (datetime.now() - dt_ult).days)
            dias_restantes = dias_totais - dias_passados
            progresso_tempo = min(1.0, max(0.0, dias_passados / dias_totais))
            if dias_restantes <= 0:
                venceu_por_tempo = True
                info_tempo_curta = f" • Vencido há {abs(dias_restantes)}d"
            elif dias_restantes <= max(15, int(dias_totais * 0.15)):
                alerta_por_tempo = True
                info_tempo_curta = f" • Restam {dias_restantes}d"
            else:
                meses_rest = max(1, round(dias_restantes / 30))
                info_tempo_curta = f" • ~{meses_rest}m"
        except ValueError:
            pass

    progresso = max(progresso_km, progresso_tempo)

    if km_restante <= 0:
        atraso = abs(km_restante)
        status = "vencido"
        cor = "#EF5350"
        texto_status = (
            f"Vencido há {atraso:,} km".replace(",", ".")
            if atraso > 0
            else "Venceu agora (0 km)"
        )
        prioridade = 0
    elif venceu_por_tempo:
        status = "vencido"
        cor = "#EF5350"
        texto_status = f"Prazo de {meses_cfg}m vencido (faltam {km_restante:,} km)".replace(",", ".")
        prioridade = 0
    elif km_restante <= limite_alerta_km:
        status = "alerta"
        cor = "#FFCA28"
        pct = int((km_restante / intervalo_km) * 100) if intervalo_km > 0 else 0
        texto_status = f"Faltam {km_restante:,} km ({pct}%){info_tempo_curta}".replace(",", ".")
        prioridade = 1
    elif alerta_por_tempo and dias_restantes is not None:
        status = "alerta"
        cor = "#FFCA28"
        texto_status = f"Vence em {dias_restantes} dias • Faltam {km_restante:,} km".replace(",", ".")
        prioridade = 1
    else:
        status = "ok"
        cor = "#66BB6A"
        texto_status = f"Restam {km_restante:,} km{info_tempo_curta}".replace(",", ".")
        prioridade = 2

    return {
        "proximo_km": proximo_km,
        "km_rodado": km_rodado,
        "km_restante": km_restante,
        "progresso": progresso,
        "status": status,
        "cor": cor,
        "texto_status": texto_status,
        "prioridade": prioridade,
    }


def listar_alertas_globais() -> List[Dict[str, Any]]:
    """
    Retorna as manutenções vencidas (#EF5350) ou próximas de vencer nos
    últimos 15% de KM ou Tempo (#FFCA28) de todos os veículos juntos.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.veiculo_id,
                p.item,
                p.intervalo_km,
                p.ultimo_km,
                p.ultima_data,
                p.observacoes,
                p.intervalo_meses,
                v.nome AS veiculo_nome,
                v.tipo AS veiculo_tipo,
                v.km_atual AS veiculo_km_atual
            FROM preventivas p
            JOIN veiculos v ON v.id = p.veiculo_id
            """
        ).fetchall()

    alertas: List[Dict[str, Any]] = []
    for r in rows:
        item_dict = dict(r)
        calc = calcular_status_preventiva(
            km_atual=item_dict["veiculo_km_atual"],
            ultimo_km=item_dict["ultimo_km"],
            intervalo_km=item_dict["intervalo_km"],
            ultima_data=item_dict.get("ultima_data"),
            intervalo_meses=item_dict.get("intervalo_meses", 0),
        )
        if calc["status"] in ("vencido", "alerta"):
            item_dict.update(calc)
            alertas.append(item_dict)

    alertas.sort(key=lambda x: (x["prioridade"], x["km_restante"]))
    return alertas


def listar_preventivas_veiculo(veiculo_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                p.*,
                v.nome AS veiculo_nome,
                v.tipo AS veiculo_tipo,
                v.km_atual AS veiculo_km_atual
            FROM preventivas p
            JOIN veiculos v ON v.id = p.veiculo_id
            WHERE p.veiculo_id = ?
            ORDER BY p.id ASC
            """,
            (veiculo_id,),
        ).fetchall()

    resultado = []
    for r in rows:
        d = dict(r)
        d.update(
            calcular_status_preventiva(
                km_atual=d["veiculo_km_atual"],
                ultimo_km=d["ultimo_km"],
                intervalo_km=d["intervalo_km"],
                ultima_data=d.get("ultima_data"),
                intervalo_meses=d.get("intervalo_meses", 0),
            )
        )
        resultado.append(d)
    # Ordena na Ficha Técnica: vencidos e alertas primeiro, depois os em dia
    resultado.sort(key=lambda x: (x["prioridade"], x["km_restante"]))
    return resultado


def adicionar_preventiva(
    veiculo_id: int,
    item: str,
    intervalo_km: int,
    ultimo_km: int,
    observacoes: str = "",
    intervalo_meses: int = 0,
) -> int:
    hoje = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO preventivas (
                veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes, intervalo_meses
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                veiculo_id,
                item.strip(),
                intervalo_km,
                ultimo_km,
                hoje,
                observacoes.strip(),
                max(0, int(intervalo_meses or 0)),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def editar_preventiva(
    preventiva_id: int,
    item: str,
    intervalo_km: int,
    ultimo_km: int,
    observacoes: str = "",
    intervalo_meses: int = 0,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE preventivas
            SET item = ?, intervalo_km = ?, ultimo_km = ?, observacoes = ?, intervalo_meses = ?
            WHERE id = ?
            """,
            (
                item.strip(),
                max(100, int(intervalo_km)),
                max(0, int(ultimo_km)),
                observacoes.strip(),
                max(0, int(intervalo_meses or 0)),
                preventiva_id,
            ),
        )
        conn.commit()


def excluir_preventiva(preventiva_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM preventivas WHERE id = ?", (preventiva_id,))
        conn.commit()


def concluir_preventiva(
    preventiva_id: int,
    km_realizado: int,
    observacoes: str = "",
    valor: float = 0.0,
    oficina: str = "",
) -> None:
    """
    Dá baixa na manutenção preventiva:
    1. Atualiza ultimo_km e ultima_data na tabela preventivas.
    2. Se km_realizado > km_atual do veículo, sincroniza o km_atual do veículo.
    3. Registra no histórico de manutenções com valor (R$) e oficina.
    """
    data_iso = datetime.now().strftime("%Y-%m-%d")
    data_br = datetime.now().strftime("%d/%m/%Y")

    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT p.id, p.veiculo_id, p.item, v.km_atual
            FROM preventivas p
            JOIN veiculos v ON v.id = p.veiculo_id
            WHERE p.id = ?
            """,
            (preventiva_id,),
        ).fetchone()

        if not row:
            return

        veiculo_id = row["veiculo_id"]
        item = row["item"]
        km_atual_veiculo = row["km_atual"]

        cursor.execute(
            """
            UPDATE preventivas
            SET ultimo_km = ?, ultima_data = ?
            WHERE id = ?
            """,
            (km_realizado, data_iso, preventiva_id),
        )

        if km_realizado > km_atual_veiculo:
            cursor.execute(
                "UPDATE veiculos SET km_atual = ? WHERE id = ?",
                (km_realizado, veiculo_id),
            )

        cursor.execute(
            """
            INSERT INTO historico (
                veiculo_id, preventiva_id, item, km_realizado, data_realizada,
                observacoes, valor, oficina, tipo_manutencao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'preventiva')
            """,
            (
                veiculo_id,
                preventiva_id,
                item,
                km_realizado,
                data_br,
                observacoes.strip() or "Manutenção preventiva concluída",
                max(0.0, float(valor or 0.0)),
                oficina.strip(),
            ),
        )
        conn.commit()


# =============================================================================
# HISTÓRICO FINANCEIRO E MANUTENÇÕES AVULSAS / CORRETIVAS
# =============================================================================
def adicionar_manutencao_avulsa(
    veiculo_id: int,
    item: str,
    km_realizado: int,
    valor: float = 0.0,
    oficina: str = "",
    observacoes: str = "",
    tipo_manutencao: str = "corretiva",
) -> int:
    data_br = datetime.now().strftime("%d/%m/%Y")
    with get_connection() as conn:
        cursor = conn.cursor()
        veiculo = cursor.execute(
            "SELECT km_atual FROM veiculos WHERE id = ?", (veiculo_id,)
        ).fetchone()
        if veiculo and km_realizado > veiculo["km_atual"]:
            cursor.execute(
                "UPDATE veiculos SET km_atual = ? WHERE id = ?",
                (km_realizado, veiculo_id),
            )

        cursor.execute(
            """
            INSERT INTO historico (
                veiculo_id, preventiva_id, item, km_realizado, data_realizada,
                observacoes, valor, oficina, tipo_manutencao
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                veiculo_id,
                item.strip(),
                km_realizado,
                data_br,
                observacoes.strip() or "Manutenção avulsa / corretiva",
                max(0.0, float(valor or 0.0)),
                oficina.strip(),
                tipo_manutencao,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def excluir_historico(historico_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM historico WHERE id = ?", (historico_id,))
        conn.commit()


def listar_historico(
    veiculo_id: Optional[int] = None, busca: str = ""
) -> List[Dict[str, Any]]:
    termo = f"%{busca.strip()}%" if busca.strip() else None
    with get_connection() as conn:
        query = """
            SELECT h.*, v.nome AS veiculo_nome, v.tipo AS veiculo_tipo
            FROM historico h
            JOIN veiculos v ON v.id = h.veiculo_id
            WHERE 1=1
        """
        params: List[Any] = []
        if veiculo_id:
            query += " AND h.veiculo_id = ?"
            params.append(veiculo_id)
        if termo:
            query += " AND (h.item LIKE ? OR h.observacoes LIKE ? OR h.oficina LIKE ? OR v.nome LIKE ?)"
            params.extend([termo, termo, termo, termo])
        query += " ORDER BY h.id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def obter_resumo_financeiro(veiculo_id: Optional[int] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        if veiculo_id:
            row_h = conn.execute(
                """
                SELECT COUNT(*) AS qtd, COALESCE(SUM(valor), 0.0) AS total_manut
                FROM historico WHERE veiculo_id = ?
                """,
                (veiculo_id,),
            ).fetchone()
            row_a = conn.execute(
                """
                SELECT COALESCE(SUM(valor_total), 0.0) AS total_comb
                FROM abastecimentos WHERE veiculo_id = ?
                """,
                (veiculo_id,),
            ).fetchone()
        else:
            row_h = conn.execute(
                "SELECT COUNT(*) AS qtd, COALESCE(SUM(valor), 0.0) AS total_manut FROM historico"
            ).fetchone()
            row_a = conn.execute(
                "SELECT COALESCE(SUM(valor_total), 0.0) AS total_comb FROM abastecimentos"
            ).fetchone()

        total_manut = float(row_h["total_manut"] or 0.0)
        total_comb = float(row_a["total_comb"] or 0.0)
        return {
            "qtd_servicos": int(row_h["qtd"] or 0),
            "total_manutencao": total_manut,
            "total_combustivel": total_comb,
            "custo_total": total_manut + total_comb,
        }


# =============================================================================
# ABASTECIMENTOS E CÁLCULO DE CONSUMO (km/L e R$/km)
# =============================================================================
def registrar_abastecimento(
    veiculo_id: int,
    km_atual: int,
    litros: float,
    valor_total: float,
    combustivel: str = "Gasolina",
) -> Dict[str, Any]:
    """
    Registra um abastecimento, calcula o consumo (km/L) comparando com o
    último abastecimento (ou com o km_atual anterior do veículo) e sincroniza o odômetro.
    """
    data_br = datetime.now().strftime("%d/%m/%Y %H:%M")
    litros = max(0.1, float(litros))
    valor_total = max(0.0, float(valor_total))

    with get_connection() as conn:
        cursor = conn.cursor()
        veiculo = cursor.execute(
            "SELECT km_atual FROM veiculos WHERE id = ?", (veiculo_id,)
        ).fetchone()
        ultimo_abast = cursor.execute(
            """
            SELECT km_atual FROM abastecimentos
            WHERE veiculo_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (veiculo_id,),
        ).fetchone()

        km_base = None
        if ultimo_abast and km_atual > ultimo_abast["km_atual"]:
            km_base = ultimo_abast["km_atual"]
        elif veiculo and km_atual > veiculo["km_atual"]:
            km_base = veiculo["km_atual"]

        km_por_litro = 0.0
        if km_base is not None and (km_atual - km_base) > 0:
            km_por_litro = round((km_atual - km_base) / litros, 2)

        cursor.execute(
            """
            INSERT INTO abastecimentos (
                veiculo_id, km_atual, litros, valor_total, combustivel, km_por_litro, data_abastecimento
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (veiculo_id, km_atual, litros, valor_total, combustivel, km_por_litro, data_br),
        )

        if veiculo and km_atual > veiculo["km_atual"]:
            cursor.execute(
                "UPDATE veiculos SET km_atual = ? WHERE id = ?",
                (km_atual, veiculo_id),
            )

        conn.commit()
        return {"km_por_litro": km_por_litro, "km_rodado": (km_atual - km_base) if km_base else 0}


def listar_abastecimentos(veiculo_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if veiculo_id:
            rows = conn.execute(
                """
                SELECT a.*, v.nome AS veiculo_nome, v.tipo AS veiculo_tipo
                FROM abastecimentos a
                JOIN veiculos v ON v.id = a.veiculo_id
                WHERE a.veiculo_id = ?
                ORDER BY a.id DESC
                """,
                (veiculo_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT a.*, v.nome AS veiculo_nome, v.tipo AS veiculo_tipo
                FROM abastecimentos a
                JOIN veiculos v ON v.id = a.veiculo_id
                ORDER BY a.id DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]


def excluir_abastecimento(abastecimento_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM abastecimentos WHERE id = ?", (abastecimento_id,))
        conn.commit()


def obter_resumo_consumo(veiculo_id: int) -> Dict[str, Any]:
    registros = listar_abastecimentos(veiculo_id)
    if not registros:
        return {
            "media_km_l": 0.0,
            "ultimo_km_l": 0.0,
            "total_litros": 0.0,
            "total_gasto": 0.0,
            "preco_medio_litro": 0.0,
            "qtd_abastecimentos": 0,
        }

    consumos_validos = [r["km_por_litro"] for r in registros if r["km_por_litro"] > 0]
    media_km_l = round(sum(consumos_validos) / len(consumos_validos), 2) if consumos_validos else 0.0
    ultimo_km_l = registros[0]["km_por_litro"]
    total_litros = round(sum(r["litros"] for r in registros), 1)
    total_gasto = round(sum(r["valor_total"] for r in registros), 2)
    preco_medio = round(total_gasto / total_litros, 2) if total_litros > 0 else 0.0

    return {
        "media_km_l": media_km_l,
        "ultimo_km_l": ultimo_km_l,
        "total_litros": total_litros,
        "total_gasto": total_gasto,
        "preco_medio_litro": preco_medio,
        "qtd_abastecimentos": len(registros),
    }


# =============================================================================
# DOSSIÊ DO VEÍCULO (EXPORTAÇÃO PARA WHATSAPP E RELATÓRIO HTML/PDF)
# =============================================================================
def gerar_dossie_texto(veiculo_id: int) -> str:
    veiculo = obter_veiculo(veiculo_id)
    if not veiculo:
        return "Veículo não encontrado."

    preventivas = listar_preventivas_veiculo(veiculo_id)
    historico = listar_historico(veiculo_id)
    resumo_fin = obter_resumo_financeiro(veiculo_id)
    resumo_cons = obter_resumo_consumo(veiculo_id)

    placa_txt = f" • Placa: {veiculo['placa']}" if veiculo.get("placa") else ""
    ano_txt = f" ({veiculo['ano']})" if veiculo.get("ano") else ""
    km_fmt = f"{veiculo['km_atual']:,}".replace(",", ".")

    linhas = [
        f"📋 *DOSSIÊ DE MANUTENÇÃO — {veiculo['nome'].upper()}{ano_txt}*",
        f"🛣️ Odômetro Atual: {km_fmt} km{placa_txt}",
        f"💰 Total em Revisões Registradas: R$ {resumo_fin['total_manutencao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    ]
    if resumo_cons["media_km_l"] > 0:
        linhas.append(f"⛽ Consumo Médio Registrado: {resumo_cons['media_km_l']} km/L")

    linhas.append("\n🔧 *STATUS DO PLANO PREVENTIVO:*")
    for p in preventivas:
        icone = "🟢" if p["status"] == "ok" else ("🟡" if p["status"] == "alerta" else "🔴")
        ult_fmt = f"{p['ultimo_km']:,}".replace(",", ".")
        prox_fmt = f"{p['proximo_km']:,}".replace(",", ".")
        linhas.append(
            f"{icone} *{p['item']}*: última em {ult_fmt} km (próxima: {prox_fmt} km) — _{p.get('observacoes') or 'OEM'}_"
        )

    linhas.append("\n📜 *HISTÓRICO DE SERVIÇOS REALIZADOS:*")
    if historico:
        for h in historico[:15]:
            km_h = f"{h['km_realizado']:,}".replace(",", ".")
            val_txt = f" • R$ {h['valor']:.2f}" if h.get("valor", 0) > 0 else ""
            ofic_txt = f" ({h['oficina']})" if h.get("oficina") else ""
            linhas.append(
                f"✔️ {h['data_realizada']} aos {km_h} km: *{h['item']}*{ofic_txt}{val_txt}"
            )
    else:
        linhas.append("- Nenhuma manutenção registrada no histórico.")

    linhas.append(f"\n_Gerado pelo aplicativo Garagem em {datetime.now().strftime('%d/%m/%Y %H:%M')}_")
    return "\n".join(linhas)


def exportar_dossie_html(veiculo_id: int) -> str:
    """Gera um arquivo HTML elegante pronto para impressão/PDF e abre no navegador."""
    veiculo = obter_veiculo(veiculo_id)
    if not veiculo:
        raise ValueError("Veículo não encontrado.")

    preventivas = listar_preventivas_veiculo(veiculo_id)
    historico = listar_historico(veiculo_id)
    resumo_fin = obter_resumo_financeiro(veiculo_id)
    resumo_cons = obter_resumo_consumo(veiculo_id)

    linhas_prev_html = ""
    for p in preventivas:
        badge_cor = "#2E7D32" if p["status"] == "ok" else ("#F57F17" if p["status"] == "alerta" else "#C62828")
        linhas_prev_html += f"""
        <tr>
          <td><strong>{p['item']}</strong><br><small>{p.get('observacoes') or 'Padrão OEM'}</small></td>
          <td>a cada {p['intervalo_km']:,} km</td>
          <td>{p['ultimo_km']:,} km</td>
          <td>{p['proximo_km']:,} km</td>
          <td><span class="status" style="background:{badge_cor}">{p['texto_status']}</span></td>
        </tr>
        """.replace(",", ".")

    linhas_hist_html = ""
    for h in historico:
        valor_fmt = f"R$ {h.get('valor', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas_hist_html += f"""
        <tr>
          <td>{h['data_realizada']}</td>
          <td>{h['km_realizado']:,} km</td>
          <td><strong>{h['item']}</strong><br><small>{h.get('observacoes') or ''}</small></td>
          <td>{h.get('oficina') or '-'}</td>
          <td>{valor_fmt}</td>
        </tr>
        """.replace(",", ".")

    if not linhas_hist_html:
        linhas_hist_html = "<tr><td colspan='5'>Nenhum serviço registrado até o momento.</td></tr>"

    total_manut_fmt = f"R$ {resumo_fin['total_manutencao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    km_atual_fmt = f"{veiculo['km_atual']:,}".replace(",", ".")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Dossiê de Manutenção — {veiculo['nome']}</title>
<style>
  body {{ font-family: 'Segoe UI', Roboto, sans-serif; background: #f4f6f8; color: #1c1c1c; margin: 0; padding: 32px; }}
  .sheet {{ max-width: 860px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 18px rgba(0,0,0,0.08); }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #263238; padding-bottom: 16px; margin-bottom: 24px; }}
  h1 {{ margin: 0; color: #1976D2; font-size: 24px; }}
  h2 {{ color: #263238; font-size: 17px; margin-top: 28px; border-left: 4px solid #1976D2; padding-left: 10px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }}
  .kpi span {{ display: block; font-size: 11px; color: #64748b; text-transform: uppercase; }}
  .kpi strong {{ font-size: 16px; color: #0f172a; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
  th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px 8px; text-align: left; }}
  th {{ background: #f1f5f9; color: #334155; font-weight: 600; }}
  .status {{ color: #fff; padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .btn-print {{ background: #1976D2; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: bold; }}
  @media print {{ .no-print {{ display: none; }} body {{ background: #fff; padding: 0; }} .sheet {{ box-shadow: none; }} }}
</style>
</head>
<body>
  <div class="sheet">
    <div class="header">
      <div>
        <h1>Dossiê de Manutenção Veicular</h1>
        <p style="margin:4px 0 0 0; color:#475569;">
          <strong>{veiculo['nome']}</strong> • Placa: {veiculo.get('placa') or 'Não informada'} • Ano: {veiculo.get('ano') or '-'}
        </p>
      </div>
      <button class="btn-print no-print" onclick="window.print()">Imprimir / Salvar PDF</button>
    </div>

    <div class="kpis">
      <div class="kpi"><span>Odômetro Atual</span><strong>{km_atual_fmt} km</strong></div>
      <div class="kpi"><span>Serviços Realizados</span><strong>{resumo_fin['qtd_servicos']}</strong></div>
      <div class="kpi"><span>Investido em Manutenção</span><strong>{total_manut_fmt}</strong></div>
      <div class="kpi"><span>Consumo Médio</span><strong>{resumo_cons['media_km_l'] or '-'} km/L</strong></div>
    </div>

    <h2>Plano de Manutenção Preventiva</h2>
    <table>
      <thead>
        <tr><th>Componente / Especificação</th><th>Intervalo</th><th>Última Troca</th><th>Próxima Meta</th><th>Status Atual</th></tr>
      </thead>
      <tbody>{linhas_prev_html}</tbody>
    </table>

    <h2>Histórico Completo de Revisões e Serviços</h2>
    <table>
      <thead>
        <tr><th>Data</th><th>Odômetro</th><th>Serviço / Observações</th><th>Oficina / Local</th><th>Valor</th></tr>
      </thead>
      <tbody>{linhas_hist_html}</tbody>
    </table>

    <p style="margin-top:28px; font-size:11px; color:#94a3b8; text-align:center;">
      Relatório emitido pelo sistema Garagem App em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
    </p>
  </div>
</body>
</html>"""

    caminho_relatorio = os.path.join(BASE_DIR, f"dossie_veiculo_{veiculo['id']}.html")
    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        f.write(html)

    webbrowser.open(f"file:///{caminho_relatorio.replace(os.sep, '/')}")
    return caminho_relatorio
