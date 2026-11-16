
#!/usr/bin/env python3

import os
import re
import psycopg2
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
import locale
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# =========================
# CONFIGURAÇÕES
# =========================
SPOOL_DIR = os.getenv("SPOOL_DIR")
CACHE_FILE = os.getenv("CACHE_FILE")
PAGE_LOG = os.getenv("PAGE_LOG")
USERS_FILE = os.getenv("USERS_FILE")
LOG_FILE = os.getenv("LOG_FILE")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}


# =========================
# LOGGING
# =========================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)

# =========================
# UTIL
# =========================
def unix_to_datetime(ts):
    try:
        ts = int(ts)
        if ts > 0:
            return datetime.fromtimestamp(
                ts,
                tz=timezone(timedelta(hours=-3))
            )
    except Exception as e:
        logging.error(f"Erro convertendo timestamp: {e}")

    return None


# =========================
# CARREGAR USUÁRIOS
# =========================
def carregar_usuarios():
    try:
        df = pd.read_excel(USERS_FILE)
        user_map = {}

        for _, row in df.iterrows():
            login = str(row["login_sistema"]).strip()

            user_map[login] = {
                "nome": str(row["nome_completo"]).strip(),
                "setor": str(row["setor"]).strip()
            }

        logging.info(f"Usuários carregados: {len(user_map)}")

        return user_map

    except Exception as e:
        logging.error(f"Erro ao carregar usuários: {e}")
        return {}


# =========================
# PARSE DO JOB.CACHE
# =========================
def parse_jobs():
    jobs = []

    if not os.path.exists(CACHE_FILE):
        logging.warning("Arquivo job.cache não encontrado.")
        return jobs

    try:
        with open(CACHE_FILE, "r", errors="ignore") as f:
            content = f.read().split("</Job>")

        for bloco in content:

            if "<Job" not in bloco:
                continue

            job_id = re.search(r"<Job (\d+)>", bloco)
            username = re.search(r"Username (.+)", bloco)
            created = re.search(r"Created (\d+)", bloco)

            if not job_id:
                continue

            jid = int(job_id.group(1))

            user = (
                username.group(1)
                .replace("LOCAL\\", "")
                .replace("\\", "")
                .strip()
                if username else "UNKNOWN"
            )

            created_at = (
                unix_to_datetime(created.group(1))
                if created else None
            )

            file_path = f"{SPOOL_DIR}/d{jid:05d}-001"

            jobs.append({
                "job_id": jid,
                "username": user,
                "created_at": created_at,
                "file_path": file_path
            })

        logging.info(f"Jobs encontrados no cache: {len(jobs)}")

    except Exception as e:
        logging.error(f"Erro ao processar job.cache: {e}")

    return jobs


# =========================
# CARREGAR PAGE_LOG
# =========================
def carregar_page_log():

    dados = {}

    if not os.path.exists(PAGE_LOG):
        logging.warning("Arquivo page_log não encontrado.")
        return dados

    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except:
        pass

    pattern = re.compile(
        r'^(\S+)\s+.*?\s+'
        r'(\d+)\s+'
        r'\[([0-9]{2}/[A-Za-z]{3}/[0-9]{4}:[0-9]{2}:[0-9]{2}:[0-9]{2})\s+[-+]\d{4}\]\s+'
        r'total\s+(\d+)\s+-\s+(.*)'
    )

    try:
        with open(PAGE_LOG, "r", errors="ignore") as f:

            for line in f:

                match = pattern.search(line)

                if not match:
                    continue

                job_id = int(match.group(2))

                # Mantém a primeira ocorrência
                if job_id in dados:
                    continue

                printer_name = match.group(1)
                pages = int(match.group(4))
                date_str = match.group(3)
                document_name = match.group(5).strip()

                document_name = re.sub(
                    r'\[.*?\]', '', document_name
                ).strip()

                document_name = re.sub(
                    r'\s+one-sided', '', document_name
                ).strip()

                try:
                    printed_at = datetime.strptime(
                        date_str,
                        "%d/%b/%Y:%H:%M:%S"
                    )

                    printed_at = printed_at.replace(
                        tzinfo=timezone(timedelta(hours=-3))
                    )

                except:
                    printed_at = None

                dados[job_id] = (
                    pages,
                    printer_name,
                    printed_at,
                    document_name
                )

        logging.info(
            f"Registros carregados do page_log: {len(dados)}"
        )

    except Exception as e:
        logging.error(f"Erro ao carregar page_log: {e}")

    return dados


# =========================
# CONSULTAR DADOS DO JOB
# =========================
def get_log_data(job_id, dados_page_log):

    return dados_page_log.get(
        job_id,
        (0, "UNKNOWN", None, "SEM_NOME")
    )


# =========================
# SALVAR NO BANCO
# =========================
def save_jobs_to_db(jobs, user_map):

    if not jobs:
        logging.info("Nenhum job para processar.")
        return

    dados_page_log = carregar_page_log()

    conn = None
    cur = None

    inseridos = 0

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        logging.info(
            f"Iniciando processamento de {len(jobs)} jobs."
        )

        for job in jobs:

            login = job["username"]

            if login in user_map:
                nome = user_map[login]["nome"]
                setor = user_map[login]["setor"]
            else:
                nome = login
                setor = "Desconhecido"

            pages, printer_name, printed_at, document_name = get_log_data(
                job["job_id"],
                dados_page_log
            )

            created_at = printed_at or job["created_at"]

            login_db = login.replace("\t", "").replace("\\", "")
            nome_db = nome.replace("\t", "").replace("\\", "")
            setor_db = setor.replace("\t", "").replace("\\", "")
            doc_db = document_name.replace("\t", "").replace("\\", "")

            try:
                cur.execute("""
                    INSERT INTO print_jobs
                    (
                        job_id,
                        username,
                        nome,
                        setor,
                        document_name,
                        file_path,
                        created_at,
                        pages,
                        printer_name
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO NOTHING
                """, (
                    job["job_id"],
                    login_db,
                    nome_db,
                    setor_db,
                    doc_db,
                    job["file_path"],
                    created_at,
                    pages,
                    printer_name
                ))

                if cur.rowcount > 0:
                    inseridos += 1

            except Exception as e:
                logging.error(
                    f"Erro ao inserir job {job['job_id']}: {e}"
                )

        conn.commit()

        logging.info(
            f"Processamento finalizado. "
            f"Jobs analisados: {len(jobs)} | "
            f"Novos registros inseridos: {inseridos}"
        )

    except Exception as e:
        if conn:
            conn.rollback()

        logging.error(
            f"Erro no processamento do banco: {e}"
        )

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    logging.info("=== Iniciando processamento do spool ===")

    user_map = carregar_usuarios()
    jobs = parse_jobs()

    save_jobs_to_db(jobs, user_map)

    logging.info("=== Processamento do spool encerrado ===")
