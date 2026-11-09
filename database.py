import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garagem.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Inicializa as tabelas veiculos, preventivas e historico com dados de exemplo."""
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
                FOREIGN KEY (veiculo_id) REFERENCES veiculos (id) ON DELETE CASCADE
            )
            """
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
        # Vencido há 50 km (venceu em 18200)
        (mt03_id, "Lubrificar Relação", 500, 17700, "2026-10-25", "Spray Motul C4 Chain Lube"),
        # Próximo de vencer: faltam 350 km (7% de 5000 <= 15%)
        (mt03_id, "Troca de Óleo e Filtro", 5000, 13600, "2026-06-15", "Yamalube 10W40 Semissintético"),
        # Em dia
        (mt03_id, "Fluido de Freio DOT 4", 10000, 15000, "2026-07-10", "Verificar nível e coloração"),
        # Civic LXS 1.8 (KM atual: 84500)
        # Vencido há 300 km (venceu em 84200)
        (civic_id, "Filtro de Ar do Motor", 15000, 69200, "2025-12-10", "Elemento filtrante OEM"),
        # Próximo de vencer: faltam 1000 km (10% de 10000 <= 15%)
        (civic_id, "Óleo do Motor 5W30 + Filtro", 10000, 75500, "2026-04-20", "Óleo 100% Sintético API SP"),
        # Em dia
        (civic_id, "Fluido de Transmissão ATF", 40000, 60000, "2025-05-01", "Honda ATF DW-1"),
    ]

    cursor.executemany(
        """
        INSERT INTO preventivas (veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        preventivas_seed,
    )

    historico_seed = [
        (mt03_id, 1, "Lubrificar Relação", 17700, "25/10/2026", "Limpeza com querosene e aplicação C4"),
        (civic_id, 5, "Óleo do Motor 5W30 + Filtro", 75500, "20/04/2026", "Troca preventiva no prazo"),
    ]
    cursor.executemany(
        """
        INSERT INTO historico (veiculo_id, preventiva_id, item, km_realizado, data_realizada, observacoes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        historico_seed,
    )


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
            (nome.strip(), tipo, km_atual, ano, placa),
        )
        veiculo_id = cursor.lastrowid
        if criar_preventivas_padrao:
            hoje = datetime.now().strftime("%Y-%m-%d")
            if tipo == "moto":
                padroes = [
                    (veiculo_id, "Lubrificar Relação", 500, km_atual, hoje, "Lubrificação periódica"),
                    (veiculo_id, "Troca de Óleo e Filtro", 5000, km_atual, hoje, "Óleo recomendado pelo fabricante"),
                ]
            else:
                padroes = [
                    (veiculo_id, "Óleo do Motor + Filtro", 10000, km_atual, hoje, "Óleo recomendado pelo fabricante"),
                    (veiculo_id, "Filtro de Ar e Alinhamento", 10000, km_atual, hoje, "Revisão periódica"),
                ]
            cursor.executemany(
                """
                INSERT INTO preventivas (veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                padroes,
            )
        conn.commit()
        return veiculo_id


def atualizar_km_veiculo(veiculo_id: int, novo_km: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE veiculos SET km_atual = ? WHERE id = ?",
            (novo_km, veiculo_id),
        )
        conn.commit()


def calcular_status_preventiva(
    km_atual: int, ultimo_km: int, intervalo_km: int
) -> Dict[str, Any]:
    """
    Calcula o status da manutenção preventiva:
    - 'vencido' (Vermelho #EF5350): km_restante <= 0
    - 'alerta' (Amarelo #FFCA28): 0 < km_restante <= 15% de intervalo_km
    - 'ok' (Verde #66BB6A): km_restante > 15% de intervalo_km
    """
    proximo_km = ultimo_km + intervalo_km
    km_rodado = max(0, km_atual - ultimo_km)
    km_restante = proximo_km - km_atual
    progresso = min(1.0, max(0.0, km_rodado / intervalo_km)) if intervalo_km > 0 else 1.0
    limite_alerta = intervalo_km * 0.15

    if km_restante <= 0:
        atraso = abs(km_restante)
        status = "vencido"
        cor = "#EF5350"
        texto_status = f"Vencido há {atraso:,} km".replace(",", ".") if atraso > 0 else "Venceu agora (0 km)"
        prioridade = 0
    elif km_restante <= limite_alerta:
        status = "alerta"
        cor = "#FFCA28"
        texto_status = f"Faltam {km_restante:,} km ({int((km_restante / intervalo_km) * 100)}%)".replace(",", ".")
        prioridade = 1
    else:
        status = "ok"
        cor = "#66BB6A"
        texto_status = f"Restam {km_restante:,} km".replace(",", ".")
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
    Retorna apenas as manutenções vencidas (#EF5350) ou próximas de vencer nos
    últimos 15% do intervalo (#FFCA28) de todos os veículos juntos.
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
        )
        if calc["status"] in ("vencido", "alerta"):
            item_dict.update(calc)
            alertas.append(item_dict)

    # Ordena primeiro os vencidos (maior atraso primeiro) e depois os em alerta (menor km restante)
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
            )
        )
        resultado.append(d)
    return resultado


def adicionar_preventiva(
    veiculo_id: int,
    item: str,
    intervalo_km: int,
    ultimo_km: int,
    observacoes: str = "",
) -> int:
    hoje = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO preventivas (veiculo_id, item, intervalo_km, ultimo_km, ultima_data, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (veiculo_id, item.strip(), intervalo_km, ultimo_km, hoje, observacoes.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def concluir_preventiva(
    preventiva_id: int,
    km_realizado: int,
    observacoes: str = "",
) -> None:
    """
    Dá baixa na manutenção preventiva:
    1. Atualiza ultimo_km e ultima_data na tabela preventivas.
    2. Se km_realizado > km_atual do veículo, sincroniza o km_atual do veículo.
    3. Registra no histórico de manutenções.
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
            INSERT INTO historico (veiculo_id, preventiva_id, item, km_realizado, data_realizada, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                veiculo_id,
                preventiva_id,
                item,
                km_realizado,
                data_br,
                observacoes.strip() or "Manutenção preventiva concluída",
            ),
        )
        conn.commit()


def listar_historico(veiculo_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if veiculo_id:
            rows = conn.execute(
                """
                SELECT h.*, v.nome AS veiculo_nome, v.tipo AS veiculo_tipo
                FROM historico h
                JOIN veiculos v ON v.id = h.veiculo_id
                WHERE h.veiculo_id = ?
                ORDER BY h.id DESC
                """,
                (veiculo_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.*, v.nome AS veiculo_nome, v.tipo AS veiculo_tipo
                FROM historico h
                JOIN veiculos v ON v.id = h.veiculo_id
                ORDER BY h.id DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]
