
import streamlit as st
import psycopg2
import pandas as pd
import os


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Painel de Impressões",
    page_icon="🖨️",
    layout="wide"
)

ITENS_POR_PAGINA = 50


# ============================================================
# FORMATAÇÃO
# ============================================================

def formatar_data(data):

    data = pd.to_datetime(data, errors="coerce")

    if pd.isna(data):
        return "-"

    return data.strftime("%d/%m/%Y %H:%M")


# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar_banco():

    return psycopg2.connect(
        host="localhost",
        port="5432",
        dbname="prints",
        user="felipe",
        password="123456"
    )


def buscar_impressoes():

    conn = None
    cursor = None

    try:

        conn = conectar_banco()
        cursor = conn.cursor()

        query = """
            SELECT
                job_id,
                username,
                nome,
                setor,
                document_name,
                file_path,
                created_at,
                pages,
                printer_name
            FROM print_jobs
            ORDER BY created_at DESC
        """

        cursor.execute(query)

        registros = cursor.fetchall()

        colunas = [
            descricao[0]
            for descricao in cursor.description
        ]

        return pd.DataFrame(
            registros,
            columns=colunas
        )

    except Exception as erro:

        st.error(
            f"Erro ao consultar o banco de dados: {erro}"
        )

        return pd.DataFrame()

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DOWNLOAD DO PDF
# ============================================================

def preparar_download_pdf(caminho, job_id, nome_documento):

    if not caminho:

        st.error(
            "O caminho do arquivo não foi informado."
        )

        return

    caminho = str(caminho)

    if not caminho.lower().endswith(".pdf"):
        caminho += ".pdf"

    if not os.path.exists(caminho):

        st.error(
            f"Arquivo não encontrado: {caminho}"
        )

        return

    try:

        with open(caminho, "rb") as arquivo:

            pdf = arquivo.read()

        nome_arquivo = str(nome_documento)

        if not nome_arquivo.lower().endswith(".pdf"):
            nome_arquivo += ".pdf"

        st.download_button(
            label="⬇ Baixar",
            data=pdf,
            file_name=nome_arquivo,
            mime="application/pdf",
            key=f"download_pdf_{job_id}"
        )

    except Exception as erro:

        st.error(
            f"Erro ao preparar o PDF: {erro}"
        )


# ============================================================
# RESETAR PAGINAÇÃO
# ============================================================

def resetar_pagina():

    st.session_state.pagina_atual = 1


# ============================================================
# TÍTULO
# ============================================================

st.title("🖨️ Painel de Impressões")


# ============================================================
# BUSCAR DADOS
# ============================================================

df = buscar_impressoes()


if df.empty:

    st.info(
        "Nenhuma impressão encontrada."
    )

    st.stop()


# ============================================================
# PREPARAR DADOS
# ============================================================

df["created_at"] = pd.to_datetime(
    df["created_at"],
    errors="coerce"
).dt.tz_localize(None)

df["pages"] = pd.to_numeric(
    df["pages"],
    errors="coerce"
).fillna(0)


# ============================================================
# FILTROS DOS GRÁFICOS
# ============================================================

st.subheader("📊 Filtros dos indicadores")

col_data1, col_data2, col_setor, col_usuario, col_impressora = st.columns(
    [1.2, 1.2, 1.2, 1.2, 1.2]
)


# ============================================================
# FILTRO DATA INICIAL
# ============================================================

data_minima = df["created_at"].min()

data_maxima = df["created_at"].max()

if pd.isna(data_minima):
    data_minima = pd.Timestamp.today()

if pd.isna(data_maxima):
    data_maxima = pd.Timestamp.today()


with col_data1:

    data_inicial = st.date_input(
        "Data inicial",
        value=data_minima.date(),
        min_value=data_minima.date(),
        max_value=data_maxima.date(),
        key="data_inicial"
    )


# ============================================================
# FILTRO DATA FINAL
# ============================================================

with col_data2:

    data_final = st.date_input(
        "Data final",
        value=data_maxima.date(),
        min_value=data_minima.date(),
        max_value=data_maxima.date(),
        key="data_final"
    )


# ============================================================
# FILTRO SETOR DOS GRÁFICOS
# ============================================================

with col_setor:

    setores_grafico = sorted(
        df["setor"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    setor_grafico = st.selectbox(
        "Setor",
        ["Todos"] + setores_grafico,
        key="grafico_setor"
    )


# ============================================================
# FILTRO USUÁRIO DOS GRÁFICOS
# ============================================================

with col_usuario:

    usuarios_grafico = sorted(
        df["nome"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    usuario_grafico = st.selectbox(
        "Usuário",
        ["Todos"] + usuarios_grafico,
        key="grafico_usuario"
    )


# ============================================================
# FILTRO IMPRESSORA DOS GRÁFICOS
# ============================================================

with col_impressora:

    impressoras_grafico = sorted(
        df["printer_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    impressora_grafico = st.selectbox(
        "Impressora",
        ["Todas"] + impressoras_grafico,
        key="grafico_impressora"
    )


# ============================================================
# APLICAR FILTROS DOS GRÁFICOS
# ============================================================

df_graficos = df.copy()


data_inicial_timestamp = pd.Timestamp(data_inicial)

data_final_timestamp = (
    pd.Timestamp(data_final)
    + pd.Timedelta(days=1)
    - pd.Timedelta(seconds=1)
)


df_graficos = df_graficos[
    (df_graficos["created_at"] >= data_inicial_timestamp)
    &
    (df_graficos["created_at"] <= data_final_timestamp)
]


if setor_grafico != "Todos":

    df_graficos = df_graficos[
        df_graficos["setor"]
        .astype(str)
        .eq(setor_grafico)
    ]


if usuario_grafico != "Todos":

    df_graficos = df_graficos[
        df_graficos["nome"]
        .astype(str)
        .eq(usuario_grafico)
    ]


if impressora_grafico != "Todas":

    df_graficos = df_graficos[
        df_graficos["printer_name"]
        .astype(str)
        .eq(impressora_grafico)
    ]


# ============================================================
# INDICADORES
# ============================================================

total_impressoes = len(df_graficos)

total_paginas = int(
    df_graficos["pages"].sum()
)

total_usuarios = (
    df_graficos["nome"]
    .dropna()
    .astype(str)
    .nunique()
)

if total_impressoes > 0:

    media_paginas = (
        total_paginas / total_impressoes
    )

else:

    media_paginas = 0


st.subheader("📈 Indicadores")


ind1, ind2, ind3, ind4 = st.columns(4)


with ind1:

    st.metric(
        "Impressões",
        f"{total_impressoes:,}".replace(",", ".")
    )


with ind2:

    st.metric(
        "Páginas",
        f"{total_paginas:,}".replace(",", ".")
    )


with ind3:

    st.metric(
        "Usuários",
        f"{total_usuarios:,}".replace(",", ".")
    )


with ind4:

    st.metric(
        "Média páginas / impressão",
        f"{media_paginas:.2f}"
    )


# ============================================================
# GRÁFICO 1 - RANKING DE USUÁRIOS
# ============================================================

st.subheader("🏆 Ranking de usuários")

if not df_graficos.empty:

    ranking_usuarios = (
        df_graficos
        .groupby("nome", dropna=False)
        .agg(
            Impressões=("job_id", "count"),
            Páginas=("pages", "sum")
        )
        .nlargest(10, "Páginas")
    )

    ranking_usuarios.index = (
        ranking_usuarios.index
        .fillna("Sem usuário")
        .astype(str)
    )

    ranking_usuarios = (
        ranking_usuarios
        .reset_index()
        .sort_values("Páginas", ascending=False)
    )

    ordem_usuarios = ranking_usuarios["nome"].tolist()

    import altair as alt

    grafico_ranking = (
        alt.Chart(ranking_usuarios)
        .mark_bar()
        .encode(
            x=alt.X(
                "Páginas:Q",
                title="Páginas"
            ),
            y=alt.Y(
                "nome:N",
                title="",
                sort=ordem_usuarios
            ),
            tooltip=[
                alt.Tooltip("nome:N", title="Usuário"),
                alt.Tooltip("Páginas:Q", title="Páginas"),
                alt.Tooltip("Impressões:Q", title="Impressões")
            ]
        )
        .properties(
            height=350
        )
    )

    st.altair_chart(
        grafico_ranking,
        use_container_width=True
    )

else:

    st.info(
        "Nenhum dado encontrado para os filtros selecionados."
    )

# ============================================================
# GRÁFICO 2 - PÁGINAS AO LONGO DO TEMPO
# ============================================================

st.subheader("📅 Páginas impressas ao longo do tempo")

if not df_graficos.empty:

    paginas_tempo = (
        df_graficos
        .set_index("created_at")
        .resample("D")["pages"]
        .sum()
        .rename("Páginas")
        .reset_index()
    )

    grafico_tempo = (
        alt.Chart(paginas_tempo)
        .mark_line()
        .encode(
            x=alt.X(
                "created_at:T",
                title="Data"
            ),
            y=alt.Y(
                "Páginas:Q",
                title="Páginas"
            ),
            tooltip=[
                alt.Tooltip(
                    "created_at:T",
                    title="Data",
                    format="%d/%m/%Y"
                ),
                alt.Tooltip(
                    "Páginas:Q",
                    title="Páginas"
                )
            ]
        )
        .properties(
            height=350
        )
    )

    st.altair_chart(
        grafico_tempo,
        use_container_width=True
    )

else:

    st.info(
        "Nenhum dado encontrado para o período selecionado."
    )


# ============================================================
# GRÁFICOS 3 E 4
# ============================================================

col_grafico3, col_grafico4 = st.columns(2)


# ============================================================
# GRÁFICO 3 - IMPRESSÕES POR SETOR
# ============================================================

with col_grafico3:

    st.subheader("🏢 Impressões por setor")

    if not df_graficos.empty:

        por_setor = (
            df_graficos
            .assign(
                setor=df_graficos["setor"]
                .fillna("Sem setor")
                .astype(str)
            )
            .groupby("setor")["job_id"]
            .count()
            .sort_values(ascending=False)
            .reset_index(name="Impressões")
        )

        grafico_setor = (
            alt.Chart(por_setor)
            .mark_bar()
            .encode(
                x=alt.X(
                    "setor:N",
                    title="",
                    axis=alt.Axis(
                        labelAngle=0
                    )
                ),
                y=alt.Y(
                    "Impressões:Q",
                    title="Impressões"
                ),
                tooltip=[
                    alt.Tooltip(
                        "setor:N",
                        title="Setor"
                    ),
                    alt.Tooltip(
                        "Impressões:Q",
                        title="Impressões"
                    )
                ]
            )
            .properties(
                height=350
            )
        )

        st.altair_chart(
            grafico_setor,
            use_container_width=True
        )

    else:

        st.info(
            "Nenhum dado encontrado."
        )


# ============================================================
# GRÁFICO 4 - PÁGINAS POR IMPRESSORA
# ============================================================

with col_grafico4:

    st.subheader("🖨️ Páginas por impressora")

    if not df_graficos.empty:

        por_impressora = (
            df_graficos
            .assign(
                printer_name=df_graficos["printer_name"]
                .fillna("Sem impressora")
                .astype(str)
            )
            .groupby("printer_name")["pages"]
            .sum()
            .sort_values(ascending=False)
            .reset_index(name="Páginas")
        )

        grafico_impressora = (
            alt.Chart(por_impressora)
            .mark_bar()
            .encode(
                x=alt.X(
                    "printer_name:N",
                    title="",
                    axis=alt.Axis(
                        labelAngle=0
                    )
                ),
                y=alt.Y(
                    "Páginas:Q",
                    title="Páginas"
                ),
                tooltip=[
                    alt.Tooltip(
                        "printer_name:N",
                        title="Impressora"
                    ),
                    alt.Tooltip(
                        "Páginas:Q",
                        title="Páginas"
                    )
                ]
            )
            .properties(
                height=350
            )
        )

        st.altair_chart(
            grafico_impressora,
            use_container_width=True
        )

    else:

        st.info(
            "Nenhum dado encontrado."
        )

# ============================================================
# SEPARADOR
# ============================================================

st.divider()


# ============================================================
# TABELA / DOWNLOADS
# ============================================================

st.subheader("📄 Histórico de impressões")


# ============================================================
# FILTROS DA TABELA
# ============================================================

col_filtro1, col_filtro2, col_filtro3 = st.columns(3)


# ============================================================
# FILTRO USUÁRIO
# ============================================================

with col_filtro1:

    usuarios = sorted(
        df["nome"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    usuario_selecionado = st.selectbox(
        "Usuário",
        ["Todos"] + usuarios,
        key="filtro_usuario",
        on_change=resetar_pagina
    )


# ============================================================
# FILTRO SETOR
# ============================================================

with col_filtro2:

    setores = sorted(
        df["setor"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    setor_selecionado = st.selectbox(
        "Setor",
        ["Todos"] + setores,
        key="filtro_setor",
        on_change=resetar_pagina
    )


# ============================================================
# FILTRO IMPRESSORA
# ============================================================

with col_filtro3:

    impressoras = sorted(
        df["printer_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    impressora_selecionada = st.selectbox(
        "Impressora",
        ["Todas"] + impressoras,
        key="filtro_impressora",
        on_change=resetar_pagina
    )


# ============================================================
# APLICAR FILTROS DA TABELA
# ============================================================

df_filtrado = df.copy()


if usuario_selecionado != "Todos":

    df_filtrado = df_filtrado[
        df_filtrado["nome"]
        .astype(str)
        .eq(usuario_selecionado)
    ]


if setor_selecionado != "Todos":

    df_filtrado = df_filtrado[
        df_filtrado["setor"]
        .astype(str)
        .eq(setor_selecionado)
    ]


if impressora_selecionada != "Todas":

    df_filtrado = df_filtrado[
        df_filtrado["printer_name"]
        .astype(str)
        .eq(impressora_selecionada)
    ]


# ============================================================
# PAGINAÇÃO
# ============================================================

total_registros = len(df_filtrado)


if total_registros == 0:

    total_paginas = 1

else:

    total_paginas = (
        total_registros + ITENS_POR_PAGINA - 1
    ) // ITENS_POR_PAGINA


if "pagina_atual" not in st.session_state:

    st.session_state.pagina_atual = 1


if st.session_state.pagina_atual > total_paginas:

    st.session_state.pagina_atual = total_paginas


pagina_atual = st.session_state.pagina_atual


inicio = (
    pagina_atual - 1
) * ITENS_POR_PAGINA


fim = inicio + ITENS_POR_PAGINA


df_pagina = df_filtrado.iloc[inicio:fim]


# ============================================================
# INFORMAÇÕES
# ============================================================

st.write(
    f"**Total de impressões:** {total_registros}"
)


if total_registros > 0:

    st.write(
        f"Exibindo **{inicio + 1} até "
        f"{min(fim, total_registros)}**"
    )

else:

    st.info(
        "Nenhuma impressão encontrada "
        "com os filtros selecionados."
    )


# ============================================================
# CABEÇALHO DA TABELA
# ============================================================

if not df_pagina.empty:

    (
        col_nome,
        col_setor,
        col_documento,
        col_paginas,
        col_impressora,
        col_data,
        col_ver
    ) = st.columns(
        [
            1.2,
            1,
            2,
            0.7,
            1.2,
            1.5,
            0.8
        ]
    )


    with col_nome:
        st.markdown("**Nome**")


    with col_setor:
        st.markdown("**Setor**")


    with col_documento:
        st.markdown("**Documento**")


    with col_paginas:
        st.markdown("**Páginas**")


    with col_impressora:
        st.markdown("**Impressora**")


    with col_data:
        st.markdown("**Data**")


    with col_ver:
        st.markdown("**PDF**")


    st.divider()


# ============================================================
# REGISTROS
# ============================================================

for _, registro in df_pagina.iterrows():

    (
        col_nome,
        col_setor,
        col_documento,
        col_paginas,
        col_impressora,
        col_data,
        col_ver
    ) = st.columns(
        [
            1.2,
            1,
            2,
            0.7,
            1.2,
            1.5,
            0.8
        ]
    )


    # --------------------------------------------------------
    # NOME
    # --------------------------------------------------------

    with col_nome:

        valor = registro["nome"]

        st.write(
            valor
            if pd.notna(valor)
            else "-"
        )


    # --------------------------------------------------------
    # SETOR
    # --------------------------------------------------------

    with col_setor:

        valor = registro["setor"]

        st.write(
            valor
            if pd.notna(valor)
            else "-"
        )


    # --------------------------------------------------------
    # DOCUMENTO
    # --------------------------------------------------------

    with col_documento:

        valor = registro["document_name"]

        st.write(
            valor
            if pd.notna(valor)
            else "-"
        )


    # --------------------------------------------------------
    # PÁGINAS
    # --------------------------------------------------------

    with col_paginas:

        valor = registro["pages"]

        st.write(
            valor
            if pd.notna(valor)
            else "-"
        )


    # --------------------------------------------------------
    # IMPRESSORA
    # --------------------------------------------------------

    with col_impressora:

        valor = registro["printer_name"]

        st.write(
            valor
            if pd.notna(valor)
            else "-"
        )


    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    with col_data:

        st.write(
            formatar_data(
                registro["created_at"]
            )
        )


    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    with col_ver:

        preparar_download_pdf(
            registro["file_path"],
            registro["job_id"],
            registro["document_name"]
        )


# ============================================================
# PAGINAÇÃO
# ============================================================

if total_registros > 0:

    st.divider()

    col_anterior, col_pagina, col_proxima = st.columns(
        [1, 2, 1]
    )


    # --------------------------------------------------------
    # BOTÃO ANTERIOR
    # --------------------------------------------------------

    with col_anterior:

        if st.button(
            "← Anterior",
            key="botao_anterior",
            disabled=pagina_atual <= 1,
            use_container_width=True
        ):

            st.session_state.pagina_atual -= 1

            st.rerun()


    # --------------------------------------------------------
    # PÁGINA ATUAL
    # --------------------------------------------------------

    with col_pagina:

        st.markdown(
            f"""
            <div style="
                text-align: center;
                padding-top: 8px;
                font-size: 16px;
            ">
                <strong>
                    Página {pagina_atual} de {total_paginas}
                </strong>
            </div>
            """,
            unsafe_allow_html=True
        )


    # --------------------------------------------------------
    # BOTÃO PRÓXIMA
    # --------------------------------------------------------

    with col_proxima:

        if st.button(
            "Próxima →",
            key="botao_proxima",
            disabled=pagina_atual >= total_paginas,
            use_container_width=True
        ):

            st.session_state.pagina_atual += 1

            st.rerun()

