import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile
import unicodedata
import re


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_ZIP = 10 * 1024 * 1024  # 10 MB


# ============================================================
# NORMALIZAÇÃO DO TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# ============================================================
# IDENTIFICA O COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # PIX
    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # TRANSFERÊNCIA
    if (
        "COMPROVANTE DE TRANSFERENCIA" in texto
        or
        "COMPROVANTE TRANSFERENCIA" in texto
    ):
        return "TRANSFERENCIA"

    # TRANSAÇÃO BANCÁRIA
    if (
        "COMPROVANTE DE TRANSACAO BANCARIA" in texto
        or
        "COMPROVANTE TRANSACAO BANCARIA" in texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIA PDF COM UMA ÚNICA PÁGINA
# ============================================================

def criar_pdf_da_pagina(reader, numero_pagina):

    writer = PdfWriter()

    # IMPORTANTE:
    # adiciona SOMENTE a página encontrada
    writer.add_page(reader.pages[numero_pagina])

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# EXTRAI SOMENTE AS PÁGINAS DOS COMPROVANTES
# ============================================================

def extrair_comprovantes(arquivo):

    reader = PdfReader(arquivo)

    comprovantes = []

    for numero_pagina, pagina in enumerate(reader.pages):

        try:
            texto = pagina.extract_text() or ""

        except Exception:
            texto = ""

        tipo = identificar_comprovante(texto)

        # ====================================================
        # SE A PÁGINA É UM COMPROVANTE
        # ====================================================

        if tipo:

            comprovantes.append({
                "tipo": tipo,
                "pagina": numero_pagina
            })

    return reader, comprovantes


# ============================================================
# CRIA ZIPS DE ATÉ 10 MB
# ============================================================

def criar_zips_10mb(arquivos):

    zips = []

    arquivos_atual = []

    def gerar_zip(lista):

        buffer = BytesIO()

        with zipfile.ZipFile(
            buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6
        ) as zip_file:

            for nome, dados in lista:

                zip_file.writestr(
                    nome,
                    dados
                )

        return buffer.getvalue()

    for nome, dados in arquivos:

        # Testa o arquivo sozinho
        zip_individual = gerar_zip([
            (nome, dados)
        ])

        # Se sozinho já ultrapassa 10 MB
        if len(zip_individual) > LIMITE_ZIP:

            if arquivos_atual:

                zips.append(
                    gerar_zip(arquivos_atual)
                )

                arquivos_atual = []

            # Coloca sozinho
            zips.append(zip_individual)

            continue

        # Testa adicionar ao ZIP atual
        tentativa = arquivos_atual + [
            (nome, dados)
        ]

        zip_teste = gerar_zip(tentativa)

        # Cabe no ZIP
        if len(zip_teste) <= LIMITE_ZIP:

            arquivos_atual.append(
                (nome, dados)
            )

        else:

            # Fecha ZIP atual
            if arquivos_atual:

                zips.append(
                    gerar_zip(arquivos_atual)
                )

            # Começa outro
            arquivos_atual = [
                (nome, dados)
            ]

    # Último ZIP
    if arquivos_atual:

        zips.append(
            gerar_zip(arquivos_atual)
        )

    return zips


# ============================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Extrator de Comprovantes",
    page_icon="📄",
    layout="centered"
)


# ============================================================
# TÍTULO
# ============================================================

st.title("📄 Extrator de Comprovantes")

st.write(
    "O sistema irá identificar e extrair "
    "**somente a página do comprovante**."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# BOTÃO
# ============================================================

if arquivo is not None:

    if st.button(
        "🔎 Extrair comprovantes",
        type="primary"
    ):

        with st.spinner(
            "Procurando comprovantes..."
        ):

            try:

                reader, comprovantes = (
                    extrair_comprovantes(arquivo)
                )

                # ============================================
                # NENHUM COMPROVANTE
                # ============================================

                if not comprovantes:

                    st.error(
                        "Nenhum comprovante foi encontrado."
                    )

                    st.stop()

                # ============================================
                # CONTADORES
                # ============================================

                contadores = {
                    "PIX": 0,
                    "TRANSFERENCIA": 0,
                    "TRANSACAO_BANCARIA": 0
                }

                arquivos_saida = []

                # ============================================
                # EXTRAI CADA PÁGINA
                # ============================================

                for indice, comprovante in enumerate(
                    comprovantes,
                    start=1
                ):

                    tipo = comprovante["tipo"]

                    numero_pagina = (
                        comprovante["pagina"]
                    )

                    contadores[tipo] += 1

                    numero_tipo = (
                        contadores[tipo]
                    )

                    # ----------------------------------------
                    # SOMENTE UMA PÁGINA
                    # ----------------------------------------

                    pdf_bytes = criar_pdf_da_pagina(
                        reader,
                        numero_pagina
                    )

                    nome_pdf = (
                        f"{tipo}_{numero_tipo:04d}.pdf"
                    )

                    arquivos_saida.append(
                        (
                            nome_pdf,
                            pdf_bytes
                        )
                    )

                # ============================================
                # CRIA ZIPS
                # ============================================

                zips = criar_zips_10mb(
                    arquivos_saida
                )

                # ============================================
                # SALVA RESULTADO
                # ============================================

                st.session_state[
                    "comprovantes_zips"
                ] = zips

                st.session_state[
                    "total_comprovantes"
                ] = len(comprovantes)

                st.session_state[
                    "contadores"
                ] = contadores

            except Exception as e:

                st.error(
                    f"Erro ao processar o PDF: {e}"
                )


# ============================================================
# RESULTADOS
# ============================================================

if "total_comprovantes" in st.session_state:

    st.success(
        f"✅ {st.session_state['total_comprovantes']} "
        f"comprovante(s) encontrado(s)."
    )

    contadores = st.session_state[
        "contadores"
    ]

    # ========================================================
    # CONTADORES
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "PIX",
            contadores["PIX"]
        )

    with col2:

        st.metric(
            "Transferências",
            contadores["TRANSFERENCIA"]
        )

    with col3:

        st.metric(
            "Transações bancárias",
            contadores["TRANSACAO_BANCARIA"]
        )

    st.divider()

    # ========================================================
    # DOWNLOAD
    # ========================================================

    st.subheader(
        "📦 Comprovantes"
    )

    zips = st.session_state[
        "comprovantes_zips"
    ]

    for indice, zip_bytes in enumerate(
        zips,
        start=1
    ):

        tamanho_mb = (
            len(zip_bytes)
            / (1024 * 1024)
        )

        st.download_button(
            label=(
                f"⬇️ Baixar "
                f"COMPROVANTES_{indice:03d}.zip "
                f"({tamanho_mb:.2f} MB)"
            ),
            data=zip_bytes,
            file_name=(
                f"COMPROVANTES_{indice:03d}.zip"
            ),
            mime="application/zip",
            key=f"download_{indice}"
        )

    st.info(
        f"{len(zips)} ZIP(s) gerado(s). "
        "Os comprovantes são separados em arquivos "
        "PDF individuais e agrupados em lotes de até 10 MB."
    )
