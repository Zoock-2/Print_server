
#!/usr/bin/env python3

import os
import logging
import psycopg2
from dotenv import load_dotenv
from pypdf import PdfReader
from datetime import datetime, timezone, timedelta

load_dotenv()
# =========================
# CONFIGURAÇÕES
# =========================

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

LOG_FILE = "/home/suporte/impressora/correcao_registros.log"

FUSO_HORARIO = timezone(timedelta(hours=-3))


# =========================
# LOGGING
# =========================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =========================
# EXTRAIR METADADOS DO PDF
# =========================


def extrair_metadados_pdf(file_path):

    if not file_path:
        return None, None

    # Tenta localizar o arquivo com e sem extensão
    if not os.path.isfile(file_path):

        if os.path.isfile(file_path + ".pdf"):
            file_path = file_path + ".pdf"

        else:
            logging.warning(
                f"Arquivo não encontrado: {file_path} "
                f"nem {file_path}.pdf"
            )
            return None, None

    try:
        reader = PdfReader(file_path, strict=False)

        # Quantidade de páginas
        pages = len(reader.pages)

        # Metadados
        metadata = reader.metadata

        created_at = None

        if metadata:
            created_at = metadata.creation_date

            if not created_at:
                created_at = metadata.modification_date

        if created_at:

            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=FUSO_HORARIO
                )

            created_at = created_at.astimezone(FUSO_HORARIO)

        return created_at, pages

    except Exception as e:

        logging.error(
            f"Erro lendo PDF {file_path}: {e}"
        )

        return None, None


# =========================
# CORRIGIR REGISTROS
# =========================

def corrigir_registros():

    conn = None
    cur = None

    try:

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        logging.info("=== INICIANDO CORREÇÃO ===")

        # Buscar somente registros específicos
        cur.execute("""
            SELECT job_id, file_path
            FROM print_jobs
            WHERE created_at IS NULL
              AND document_name = 'SEM_NOME'
              AND pages = 0
            ORDER BY job_id
        """)

        registros = cur.fetchall()

        total = len(registros)

        logging.info(
            f"Registros encontrados para correção: {total}"
        )

        print(f"\nRegistros encontrados: {total}\n")

        corrigidos = 0
        ignorados = 0
        erros = 0

        for job_id, file_path in registros:

            print(f"Processando Job {job_id}...")

            # Extrair informações do PDF
            created_at, pages = extrair_metadados_pdf(
                file_path
            )

            # Exigir os dois dados para atualizar
            if created_at is None or pages is None:

                logging.warning(
                    f"Job {job_id} ignorado: "
                    "não foi possível obter data ou páginas."
                )

                print("  Não foi possível obter os metadados.")
                ignorados += 1
                continue

            try:

                cur.execute("""
                    UPDATE print_jobs
                    SET created_at = %s,
                        pages = %s
                    WHERE job_id = %s
                      AND created_at IS NULL
                      AND document_name = 'SEM_NOME'
                      AND pages = 0
                """, (
                    created_at,
                    pages,
                    job_id
                ))

                if cur.rowcount == 1:

                    corrigidos += 1

                    logging.info(
                        f"Job {job_id} corrigido: "
                        f"Data={created_at}, Páginas={pages}"
                    )

                    print(
                        f"  Corrigido: {created_at} | "
                        f"{pages} páginas"
                    )

                else:

                    ignorados += 1

                    print("  Registro não atualizado.")

            except Exception as e:

                erros += 1

                logging.error(
                    f"Erro atualizando Job {job_id}: {e}"
                )

                print(f"  Erro: {e}")

        # Salvar alterações
        conn.commit()

        print("\n========== RESULTADO ==========")
        print(f"Encontrados: {total}")
        print(f"Corrigidos:  {corrigidos}")
        print(f"Ignorados:   {ignorados}")
        print(f"Erros:       {erros}")
        print("================================")

        logging.info(
            f"Finalizado. Encontrados={total}, "
            f"Corrigidos={corrigidos}, "
            f"Ignorados={ignorados}, Erros={erros}"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        logging.exception(
            f"Erro geral na correção: {e}"
        )

        print(f"Erro geral: {e}")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    corrigir_registros()
