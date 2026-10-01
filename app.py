import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import unicodedata
import re


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


# ============================================================
# NORMALIZAÇÃO DO TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICA O COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # --------------------------------------------------------
    # 1 - PIX
    # --------------------------------------------------------

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # --------------------------------------------------------
    # 2 - TRANSFERÊNCIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # 3 - TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIA PDF COM AS PÁGINAS RECEBIDAS
# ============================================================

def gerar_pdf(reader, paginas):

    writer = PdfWriter()

    for pagina in paginas:

        writer.add_page(
            reader.pages[pagina]
        )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# AGRUPA PÁGINAS ATÉ 10 MB
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo
):

    arquivos = []

    paginas_atual = []

    numero_arquivo = 1

    for numero_pagina in paginas:

        # ----------------------------------------------------
        # Testa adicionar a página atual
        # ----------------------------------------------------

        tentativa = paginas_atual + [
            numero_pagina
        ]

        pdf_teste = gerar_pdf(
            reader,
            tentativa
        )

        tamanho_teste = len(
            pdf_teste
        )

        # ----------------------------------------------------
        # A página cabe no PDF atual
        # ----------------------------------------------------

        if tamanho_teste <= LIMITE_BYTES:

            paginas_atual.append(
                numero_pagina
            )

        # ----------------------------------------------------
        # Passou de 10 MB
        # ----------------------------------------------------

        else:

            # -----------------------------------------------
            # Salva o PDF atual
            # -----------------------------------------------

            if paginas_atual:

                pdf_final = gerar_pdf(
                    reader,
                    paginas_atual
                )

                nome = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}.pdf"
                )

                arquivos.append(
                    (
                        nome,
                        pdf_final
                    )
                )

                numero_arquivo += 1

            # -----------------------------------------------
            # Começa novo PDF
            # -----------------------------------------------

            paginas_atual = [
                numero_pagina
            ]

            # -----------------------------------------------
            # Se uma única página já tiver mais de 10 MB,
            # ela será mantida sozinha.
            # -----------------------------------------------

            if len(pdf_teste) > LIMITE_BYTES:

                pdf_grande = gerar_pdf(
                    reader,
                    [numero_pagina]
                )

                nome = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}.pdf"
                )

                arquivos.append(
                    (
                        nome,
                        pdf_grande
                    )
                )

                numero_arquivo += 1

                paginas_atual = []

    # --------------------------------------------------------
    # Salva o último PDF
    # --------------------------------------------------------

    if paginas_atual:

        pdf_final = gerar_pdf(
            reader,
            paginas_atual
        )

        nome = (
            f"{prefixo}_"
            f"{numero_arquivo:03d}.pdf"
        )

        arquivos.append(
            (
                nome,
                pdf_final
            )
        )

    return arquivos


# ============================================================
# PROCESSA O PDF
# ============================================================

def processar_pdf(arquivo):

    reader = PdfReader(arquivo)

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {
        "PIX": 0,
        "TRANSFERENCIA": 0,
        "TRANSACAO_BANCARIA": 0
    }

    # ========================================================
    # PERCORRE TODAS AS PÁGINAS
    # ========================================================

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        tipo = identificar_comprovante(
            texto
        )

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] += 1

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

    # ========================================================
    # GERA PDFs DE COMPROVANTES
    # ========================================================

    arquivos_comprovantes = agrupar_paginas(
        reader,
        paginas_comprovantes,
        "COMPROVANTES"
    )

    # ========================================================
    # GERA PDFs SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = agrupar_paginas(
        reader,
        paginas_sem_comprovantes,
        "SEM_COMPROVANTES"
    )

    return (
        arquivos_comprovantes,
        arquivos_sem_comprovantes,
        contadores
    )


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Agrupador de Comprovantes",
    page_icon="📄",
    layout="centered"
)


st.title(
    "📄 Agrupador de Comprovantes"
)

st.write(
    "O sistema separa as páginas de comprovantes das "
    "demais páginas e agrupa cada grupo em PDFs de até 10 MB."
)


# ============================================================
# NOMENCLATURAS
# ============================================================

with st.expander(
    "🔎 Nomenclaturas identificadas"
):

    st.write(
        "1. COMPROVANTE PIX"
    )

    st.write(
        "2. COMPROVANTE DE TRANSFERENCIA"
    )

    st.write(
        "3. COMPROVANTE DE TRANSACAO BANCARIA"
    )


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    if st.button(
        "🔎 Processar PDF",
        type="primary"
    ):

        with st.spinner(
            "Processando e agrupando as páginas..."
        ):

            try:

                (
                    arquivos_comprovantes,
                    arquivos_sem_comprovantes,
                    contadores
                ) = processar_pdf(
                    arquivo
                )

                # --------------------------------------------
                # SALVA RESULTADOS
                # --------------------------------------------

                st.session_state[
                    "processado"
                ] = True

                st.session_state[
                    "arquivos_comprovantes"
                ] = arquivos_comprovantes

                st.session_state[
                    "arquivos_sem_comprovantes"
                ] = arquivos_sem_comprovantes

                st.session_state[
                    "contadores"
                ] = contadores

                st.session_state[
                    "total_comprovantes"
                ] = sum(
                    contadores.values()
                )

            except Exception as erro:

                st.error(
                    f"Erro ao processar o PDF: {erro}"
                )


# ============================================================
# RESULTADO
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    st.success(
        "✅ Processamento concluído!"
    )

    # ========================================================
    # RESUMO
    # ========================================================

    contadores = st.session_state[
        "contadores"
    ]

    total_comprovantes = (
        st.session_state[
            "total_comprovantes"
        ]
    )

    arquivos_comprovantes = (
        st.session_state[
            "arquivos_comprovantes"
        ]
    )

    arquivos_sem_comprovantes = (
        st.session_state[
            "arquivos_sem_comprovantes"
        ]
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Total de comprovantes",
            total_comprovantes
        )

    with col2:

        st.metric(
            "Arquivos de comprovantes",
            len(arquivos_comprovantes)
        )

    with col3:

        st.metric(
            "Arquivos sem comprovantes",
            len(arquivos_sem_comprovantes)
        )

    # ========================================================
    # TIPOS
    # ========================================================

    st.subheader(
        "📋 Comprovantes encontrados"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "PIX",
            contadores["PIX"]
        )

    with col2:

        st.metric(
            "Transferência",
            contadores["TRANSFERENCIA"]
        )

    with col3:

        st.metric(
            "Transação bancária",
            contadores[
                "TRANSACAO_BANCARIA"
            ]
        )

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 PDFs com comprovantes"
    )

    if arquivos_comprovantes:

        for nome, dados in (
            arquivos_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"comp_{nome}"
            )

    else:

        st.warning(
            "Nenhum comprovante encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 PDFs sem comprovantes"
    )

    if arquivos_sem_comprovantes:

        for nome, dados in (
            arquivos_sem_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"sem_{nome}"
            )

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
